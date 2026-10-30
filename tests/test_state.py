from pathlib import Path
import json
import pytest

from wiim_lastfm.models import Track
from wiim_lastfm.state import ScrobbleState


def test_state_records_and_detects_recent_scrobble(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Duster", "The Motion Picture", "Stratosphere", 240_000)

    state.record_scrobble(track, started_at=1_000)

    assert state.has_recent_scrobble(track, started_at=1_030) is True


def test_state_allows_same_track_outside_duplicate_window(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json", duplicate_window_seconds=90)
    track = Track("Duster", "The Motion Picture", "Stratosphere", 240_000)

    state.record_scrobble(track, started_at=1_000)

    assert state.has_recent_scrobble(track, started_at=1_200) is False


def test_state_detects_consecutive_duplicate_scrobble(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Florist", "Shadow Bloom", "Jellywish", 240_000)

    state.record_scrobble(track, started_at=1_000, now=1_120)

    assert state.has_consecutive_scrobble(track, now=1_180) is True


def test_state_allows_same_track_after_intervening_track(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    first = Track("Florist", "Shadow Bloom", "Jellywish", 240_000)
    second = Track("Florist", "Still", "Jellywish", 240_000)

    state.record_scrobble(first, started_at=1_000, now=1_120)
    state.record_scrobble(second, started_at=1_240, now=1_360)

    assert state.has_consecutive_scrobble(first, now=1_420) is False


def test_state_blocks_consecutive_same_track_indefinitely(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Florist", "Shadow Bloom", "Jellywish", 240_000)

    state.record_scrobble(track, started_at=1_000, now=1_120)

    state.prune(now=9_000_000)
    state.save()
    state = ScrobbleState(state.path)
    assert state.has_consecutive_scrobble(track, now=9_000_000) is True


def test_state_persists_scrobbles_to_disk(tmp_path: Path):
    path = tmp_path / "state.json"
    track = Track("Duster", "The Motion Picture", None, 240_000)

    ScrobbleState(path).record_scrobble(track, started_at=1_000)

    reloaded = ScrobbleState(path)
    assert reloaded.has_recent_scrobble(track, started_at=1_000) is True


def test_state_prunes_old_scrobbles(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json", retention_seconds=100)
    old_track = Track("Artist", "Old", None, 180_000)
    new_track = Track("Artist", "New", None, 180_000)

    state.record_scrobble(old_track, started_at=1_000, now=1_000)
    state.record_scrobble(new_track, started_at=1_200, now=1_200)
    state.prune(now=1_200)

    assert state.has_recent_scrobble(old_track, started_at=1_000) is False
    assert state.has_recent_scrobble(new_track, started_at=1_200) is True


def test_state_ignores_non_dict_scrobble_entries(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text('{"version": 1, "scrobbles": ["bad"]}', encoding="utf-8")
    state = ScrobbleState(path)
    track = Track("Duster", "The Motion Picture", None, 240_000)

    assert state.has_recent_scrobble(track, started_at=1_000) is False


def test_state_ignores_non_numeric_started_at_entries(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(
        '{"version": 1, "scrobbles": [{"track_key": "duster\\\\u0000the motion picture\\\\u0000", "started_at": "bad"}]}',
        encoding="utf-8",
    )
    state = ScrobbleState(path)
    track = Track("Duster", "The Motion Picture", None, 240_000)

    assert state.has_recent_scrobble(track, started_at=1_000) is False


def test_prune_skips_malformed_recorded_at_entries(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text(
        '{"version": 1, "scrobbles": [{"recorded_at": "bad"}, {"recorded_at": 1200}]}',
        encoding="utf-8",
    )
    state = ScrobbleState(path, retention_seconds=100)

    state.prune(now=1_200)

    assert state._data["scrobbles"] == [{"recorded_at": 1200}]


def test_state_queues_and_persists_pending_scrobble(tmp_path: Path):
    path = tmp_path / "state.json"
    track = Track("Duster", "The Motion Picture", "Stratosphere", 240_000)

    queued = ScrobbleState(path).queue_pending(track, started_at=1_000, queued_at=1_200)

    assert queued is True
    pending = ScrobbleState(path).due_pending(now=1_290, settlement_seconds=90)
    assert len(pending) == 1
    assert pending[0].track == track
    assert pending[0].started_at == 1_000


def test_state_collapses_duplicate_multiroom_pending_scrobble(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Duster", "The Motion Picture", "Stratosphere", 240_000)

    assert state.queue_pending(track, started_at=1_000, queued_at=1_200) is True
    assert state.queue_pending(track, started_at=1_020, queued_at=1_220) is False

    assert len(state.due_pending(now=1_500, settlement_seconds=90)) == 1


def test_state_discards_completed_pending_scrobble(tmp_path: Path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Duster", "The Motion Picture", "Stratosphere", 240_000)
    state.queue_pending(track, started_at=1_000, queued_at=1_200)
    pending = state.due_pending(now=1_300, settlement_seconds=90)[0]

    state.complete_pending(pending, now=1_300)

    assert state.due_pending(now=1_500, settlement_seconds=90) == []
    assert state.has_recent_scrobble(track, started_at=1_000) is True


def test_album_case_whitespace_and_unicode_do_not_create_different_songs(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    first = Track("Beyoncé", "  A   Song ", "Original", None)
    variant = Track("BEYONCE\u0301", "a song", "Deluxe", None)
    state.record_scrobble(first, 1_000, now=1_200)
    assert state.has_recent_scrobble(variant, 1_010)
    assert state.has_consecutive_scrobble(variant)


def test_old_state_migrates_album_dependent_history_and_pending(tmp_path):
    path = tmp_path / "state.json"
    item = {"track_key": "artist\u0000song\u0000album", "artist": "Artist", "title": "Song",
            "album": "Album", "started_at": 1_000, "recorded_at": 1_200, "queued_at": 1_100}
    path.write_text(json.dumps({"version": 2, "scrobbles": [item], "pending": [item]}))
    state = ScrobbleState(path)
    variant = Track("artist", "song", None, None)
    assert state.has_consecutive_scrobble(variant, now=99_000_000)
    assert state.has_recent_scrobble(variant, 1_000)
    state.discard_pending(state.due_pending(now=1_300)[0])
    assert state.due_pending(now=1_300) == []


def test_submission_attempt_survives_restart_without_automatic_retry(tmp_path):
    path = tmp_path / "state.json"
    track = Track("Artist", "Song", None, None)
    state = ScrobbleState(path)
    state.queue_pending(track, 1_000, 1_100)
    state.begin_submission(state.due_pending(now=1_300)[0])
    restored = ScrobbleState(path)
    assert restored.due_pending(now=1_300) == []
    assert restored.has_recent_scrobble(track, 1_000)
    assert restored.has_consecutive_scrobble(track)
    assert len(restored._data["uncertain"]) == 1


def test_failed_attempt_write_keeps_song_pending(tmp_path, monkeypatch):
    state = ScrobbleState(tmp_path / "state.json")
    state.queue_pending(Track("Artist", "Song", None, None), 1_000, 1_100)
    pending = state.due_pending(now=1_300)[0]
    def fail(): raise OSError("disk full")
    monkeypatch.setattr(state, "save", fail)
    with pytest.raises(OSError): state.begin_submission(pending)
    assert state.due_pending(now=1_300) == [pending]
    assert state._data["uncertain"] == []


def test_lastfm_canonical_identity_is_also_protected(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    raw = Track("Durruti Column", "Tomorrow", None, None)
    canonical = Track("The Durutti Column", "Tomorrow", None, None)
    state.queue_pending(raw, 1_000, 1_100)
    state.complete_pending(state.due_pending(now=1_300)[0], now=1_300, canonical_track=canonical)
    restored = ScrobbleState(state.path)
    assert restored.has_consecutive_scrobble(raw)
    assert restored.has_consecutive_scrobble(canonical)


def test_corrupt_state_does_not_silently_reset_duplicate_protection(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{broken")
    with pytest.raises(ValueError, match="refusing to reset"):
        ScrobbleState(path)
