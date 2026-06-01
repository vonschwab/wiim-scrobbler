from wiim_lastfm.models import Track
from wiim_lastfm.scrobbler import DeviceScrobbler, ScrobbleDecision, should_scrobble
from wiim_lastfm.state import PendingScrobble, ScrobbleState


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


class IdleStatus:
    is_playing = False
    position_ms = 0
    duration_ms = None


class LastFmSpy:
    def __init__(self):
        self.now_playing = []
        self.scrobbles = []
        self.external_recent = False

    def update_now_playing(self, track):
        self.now_playing.append(track)

    def has_recent_scrobble(self, track, started_at):
        return self.external_recent

    def scrobble(self, track, timestamp=None):
        self.scrobbles.append((track, timestamp))


class FailingState:
    def __init__(self):
        self.pending = None

    def has_recent_scrobble(self, track, started_at):
        return False

    def has_consecutive_scrobble(self, track):
        return False

    def queue_pending(self, track, started_at, queued_at):
        self.pending = PendingScrobble(track, started_at, queued_at)
        return True

    def due_pending(self, now, settlement_seconds):
        if self.pending and now - self.pending.queued_at >= settlement_seconds:
            return [self.pending]
        return []

    def discard_pending(self, pending):
        self.pending = None

    def complete_pending(self, pending):
        self.pending = None
        raise OSError("disk full")


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


def test_device_scrobbler_defers_scrobble_until_next_track_and_settlement(tmp_path):
    first_track = Track("Duster", "The Motion Picture", None, None)
    second_track = Track("Duster", "Echo, Bravo", None, None)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    wiim = StaticWiim(first_track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM",
        wiim,
        lastfm,
        state=state,
        clock=lambda: now[0],
        settlement_seconds=90,
    )

    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.track = second_track
    now[0] = 1_040
    scrobbler.poll_once()
    now[0] = 1_129
    scrobbler.poll_once()

    assert lastfm.scrobbles == []

    now[0] = 1_130
    result = scrobbler.poll_once()

    assert result == "WiiM: scrobbled Duster - The Motion Picture"
    assert len(lastfm.scrobbles) == 1
    assert state.has_recent_scrobble(first_track, lastfm.scrobbles[0][1]) is True


def test_device_scrobbler_suppresses_duplicate_multiroom_scrobble(tmp_path):
    track = Track("Duster", "The Motion Picture", None, None)
    next_track = Track("Duster", "Echo, Bravo", None, None)
    state = ScrobbleState(tmp_path / "state.json")
    first_lastfm = LastFmSpy()
    second_lastfm = LastFmSpy()
    first_wiim = StaticWiim(track, Status())
    second_wiim = StaticWiim(track, Status())
    now = [1_000]
    first = DeviceScrobbler(
        "Pro", first_wiim, first_lastfm, state=state, clock=lambda: now[0]
    )
    second = DeviceScrobbler(
        "Mini", second_wiim, second_lastfm, state=state, clock=lambda: now[0]
    )

    first.poll_once()
    first.poll_once()
    second.poll_once()
    second.poll_once()
    first_wiim.track = next_track
    second_wiim.track = next_track
    now[0] = 1_040
    first.poll_once()
    second.poll_once()
    now[0] = 1_130
    first.poll_once()
    second.poll_once()

    assert len(first_lastfm.scrobbles) == 1
    assert second_lastfm.scrobbles == []


def test_device_scrobbler_suppresses_consecutive_duplicate_scrobble(tmp_path):
    track = Track("Florist", "Shadow Bloom", "Jellywish", None)
    next_track = Track("Florist", "Still", "Jellywish", None)
    state = ScrobbleState(tmp_path / "state.json")
    state.record_scrobble(track, started_at=1_000)
    lastfm = LastFmSpy()
    wiim = StaticWiim(track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM", wiim, lastfm, state=state, clock=lambda: now[0]
    )

    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.track = next_track
    now[0] = 1_040
    scrobbler.poll_once()
    now[0] = 1_130
    result = scrobbler.poll_once()

    assert result == "WiiM: skipped duplicate Florist - Shadow Bloom"
    assert lastfm.scrobbles == []


def test_device_scrobbler_suppresses_external_lastfm_duplicate(tmp_path):
    track = Track("Duster", "The Motion Picture", None, None)
    next_track = Track("Duster", "Echo, Bravo", None, None)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    lastfm.external_recent = True
    wiim = StaticWiim(track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM", wiim, lastfm, state=state, clock=lambda: now[0]
    )

    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.track = next_track
    now[0] = 1_040
    scrobbler.poll_once()
    now[0] = 1_130
    result = scrobbler.poll_once()

    assert result == "WiiM: skipped Last.fm duplicate Duster - The Motion Picture"
    assert lastfm.scrobbles == []


def test_device_scrobbler_does_not_queue_track_seen_once(tmp_path):
    skipped_track = Track("Duster", "Skipped", None, None)
    next_track = Track("Duster", "Played", None, None)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    wiim = StaticWiim(skipped_track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM", wiim, lastfm, state=state, clock=lambda: now[0]
    )

    scrobbler.poll_once()
    wiim.track = next_track
    now[0] = 1_020
    scrobbler.poll_once()
    now[0] = 1_200
    scrobbler.poll_once()

    assert lastfm.scrobbles == []
    assert state.due_pending(now=1_200, settlement_seconds=90) == []


def test_device_scrobbler_flushes_last_track_after_playback_stops(tmp_path):
    track = Track("Duster", "The Motion Picture", None, None)
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    wiim = StaticWiim(track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM", wiim, lastfm, state=state, clock=lambda: now[0]
    )

    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.status = IdleStatus()
    now[0] = 1_040
    scrobbler.poll_once()
    now[0] = 1_130
    result = scrobbler.poll_once()

    assert result == "WiiM: scrobbled Duster - The Motion Picture"
    assert len(lastfm.scrobbles) == 1


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


def test_scrobble_session_is_marked_done_if_state_write_fails():
    track = Track("Duster", "The Motion Picture", None, 240_000)
    next_track = Track("Duster", "Echo, Bravo", None, 240_000)
    lastfm = LastFmSpy()
    wiim = StaticWiim(track, Status())
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM",
        wiim,
        lastfm,
        state=FailingState(),
        clock=lambda: now[0],
    )

    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.track = next_track
    now[0] = 1_040
    scrobbler.poll_once()
    now[0] = 1_130
    try:
        scrobbler.poll_once()
    except OSError:
        pass
    scrobbler.poll_once()

    assert len(lastfm.scrobbles) == 1
