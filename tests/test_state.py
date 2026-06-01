from pathlib import Path

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


def test_state_allows_consecutive_same_track_outside_history_window(tmp_path: Path):
    state = ScrobbleState(
        tmp_path / "state.json", consecutive_duplicate_window_seconds=300
    )
    track = Track("Florist", "Shadow Bloom", "Jellywish", 240_000)

    state.record_scrobble(track, started_at=1_000, now=1_120)

    assert state.has_consecutive_scrobble(track, now=1_500) is False


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
