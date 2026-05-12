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
