from wiim_lastfm.models import Track
from wiim_lastfm.scrobbler import ScrobbleDecision, should_scrobble


def test_scrobbles_after_half_track_played():
    track = Track(artist="Artist", title="Song", album="Album", duration_ms=240_000)

    assert should_scrobble(track, played_ms=120_000) == ScrobbleDecision.SCROBBLE


def test_scrobbles_after_four_minutes_for_long_track():
    track = Track(artist="Artist", title="Song", album="Album", duration_ms=900_000)

    assert should_scrobble(track, played_ms=240_000) == ScrobbleDecision.SCROBBLE


def test_does_not_scrobble_before_threshold():
    track = Track(artist="Artist", title="Song", album="Album", duration_ms=240_000)

    assert should_scrobble(track, played_ms=60_000) == ScrobbleDecision.WAIT


def test_ignores_missing_artist_or_title():
    track = Track(artist="", title="Song", album=None, duration_ms=240_000)

    assert should_scrobble(track, played_ms=240_000) == ScrobbleDecision.IGNORE
