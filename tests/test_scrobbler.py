from wiim_lastfm.models import Track
from wiim_lastfm.scrobbler import DeviceScrobbler, ScrobbleDecision, should_scrobble
from wiim_lastfm.state import ScrobbleState


class StaticWiim:
    def __init__(self, track, status):
        self.track = track
        self.status = status

    def player_status(self):
        return self.status

    def current_track(self, duration_ms=None):
        return Track(
            self.track.artist,
            self.track.title,
            self.track.album,
            duration_ms,
        )


class Status:
    is_playing = True
    position_ms = 130_000
    duration_ms = 240_000


class LastFmSpy:
    def __init__(self):
        self.now_playing = []
        self.scrobbles = []

    def update_now_playing(self, track):
        self.now_playing.append(track)

    def scrobble(self, track, timestamp=None):
        self.scrobbles.append((track, timestamp))


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


def test_device_scrobbler_records_scrobble_in_shared_state(tmp_path):
    track = Track("Duster", "The Motion Picture", None, 240_000)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler("WiiM", StaticWiim(track, Status()), lastfm, state=state)
    scrobbler.session = None

    scrobbler.poll_once()
    scrobbler.poll_once()

    assert len(lastfm.scrobbles) == 1
    assert state.has_recent_scrobble(track, lastfm.scrobbles[0][1]) is True


def test_device_scrobbler_suppresses_duplicate_multiroom_scrobble(tmp_path):
    track = Track("Duster", "The Motion Picture", None, 240_000)
    state = ScrobbleState(tmp_path / "state.json")
    first_lastfm = LastFmSpy()
    second_lastfm = LastFmSpy()
    first = DeviceScrobbler("Pro", StaticWiim(track, Status()), first_lastfm, state=state)
    second = DeviceScrobbler("Mini", StaticWiim(track, Status()), second_lastfm, state=state)

    first.poll_once()
    first.poll_once()
    second.poll_once()
    second.poll_once()

    assert len(first_lastfm.scrobbles) == 1
    assert second_lastfm.scrobbles == []


def test_dry_run_does_not_record_scrobble_in_state(tmp_path):
    track = Track("Duster", "The Motion Picture", None, 240_000)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM",
        StaticWiim(track, Status()),
        lastfm,
        dry_run=True,
        state=state,
    )

    scrobbler.poll_once()
    scrobbler.poll_once()

    assert lastfm.scrobbles == []
    assert state.has_recent_scrobble(track, scrobbler.session.started_at) is False
