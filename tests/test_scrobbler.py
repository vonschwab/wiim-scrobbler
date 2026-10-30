from wiim_lastfm.models import Track
from wiim_lastfm.scrobbler import DeviceScrobbler, ScrobbleDecision, should_scrobble
from wiim_lastfm.state import PendingScrobble, ScrobbleState
import pytest


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
        self.latest_scrobble = None

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

    def begin_submission(self, pending):
        self.pending = None

    def complete_pending(self, pending, canonical_track=None):
        self.pending = None
        raise OSError("disk full")


class StubResolver:
    def __init__(self, resolved=None):
        self.resolved = resolved
        self.seen = []

    def resolve(self, track):
        self.seen.append(track)
        return self.resolved


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


def test_poll_once_reports_the_resolved_nts_track():
    mixtape = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)
    resolver = StubResolver(Track("Benedek", "Alpha Tape", None, None))
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM",
        StaticWiim(mixtape, Status()),
        lastfm,
        nts=resolver,
    )

    message = scrobbler.poll_once()

    assert message == "WiiM: now playing Benedek - Alpha Tape"
    assert lastfm.now_playing == [Track("Benedek", "Alpha Tape", None, None)]


def test_poll_once_skips_nts_playback_with_no_identified_track():
    mixtape = Track(
        artist="JACK SAPSED, ISLAND TIME VOL 17",
        title="ISLAND TIME",
        album=None,
        duration_ms=None,
    )
    resolver = StubResolver(Track("", "ISLAND TIME", None, None))
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM",
        StaticWiim(mixtape, Status()),
        lastfm,
        nts=resolver,
    )

    message = scrobbler.poll_once()

    assert lastfm.now_playing == []
    assert "did not expose artist/title" in message


def test_poll_once_keeps_device_metadata_when_resolver_declines():
    track = Track("Orchid Mantis", "blank slate", "album", None)
    resolver = StubResolver(None)
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM",
        StaticWiim(track, Status()),
        lastfm,
        nts=resolver,
    )

    scrobbler.poll_once()

    assert lastfm.now_playing == [
        Track("Orchid Mantis", "blank slate", "album", 240_000)
    ]


def test_nts_show_songs_get_individual_timestamps_and_no_show_duration(tmp_path):
    from wiim_lastfm.nts import NtsResolver

    show = "THE EARLY BIRD SHOW W/ PAM & CHRIS KONTOS"
    status = Status()
    status.position_ms = 2_000_000
    status.duration_ms = 7_252_000
    wiim = StaticWiim(Track("Chen Min Yang - Theme 1（主題一）", show, "unknow", None), status)
    now = [10_000]
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM", wiim, lastfm,
        state=ScrobbleState(tmp_path / "state.json"),
        nts=NtsResolver(fetch_catalog=lambda: [], find_show=lambda title: True),
        clock=lambda: now[0], settlement_seconds=0,
    )
    scrobbler.poll_once()
    now[0] += 20
    status.position_ms += 20_000
    scrobbler.poll_once()
    now[0] += 160
    status.position_ms += 160_000
    wiim.track = Track("Sakurai Keisuke - Tane O Maku", show, "unknow", None)
    scrobbler.poll_once()
    scrobbler.poll_once()
    now[0] += 180
    wiim.status = IdleStatus()
    scrobbler.poll_once()

    assert lastfm.scrobbles == [
        (Track("Chen Min Yang", "Theme 1（主題一）", None, None), 10_000),
        (Track("Sakurai Keisuke", "Tane O Maku", None, None), 10_180),
    ]


def test_ordinary_track_keeps_position_based_timestamp():
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler(
        "WiiM", StaticWiim(Track("Artist", "Song", None, None), Status()),
        lastfm, nts=StubResolver(None), clock=lambda: 1_000,
    )
    scrobbler.poll_once()

    assert scrobbler.session.started_at == 870


def test_nts_metadata_gap_finishes_previous_song(tmp_path):
    first = Track("Benedek", "Alpha Tape", None, None)
    resolver = StubResolver(first)
    lastfm = LastFmSpy()
    now = [1_000]
    scrobbler = DeviceScrobbler(
        "WiiM", StaticWiim(first, Status()), lastfm,
        state=ScrobbleState(tmp_path / "state.json"), nts=resolver,
        clock=lambda: now[0], settlement_seconds=0,
    )
    scrobbler.poll_once()
    scrobbler.poll_once()
    resolver.resolved = Track("", "POOLSIDE", None, None)
    now[0] += 100
    scrobbler.poll_once()
    scrobbler.poll_once()

    assert lastfm.scrobbles == [(first, 1_000)]
    assert scrobbler.session is None


def queue_one(state, track, started_at=1_000):
    state.queue_pending(track, started_at, queued_at=started_at + 100)
    return state.due_pending(now=started_at + 200)[0]


def test_failed_history_lookup_defers_without_sending(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Artist", "Song", None, None)
    pending = queue_one(state, track)
    class OfflineHistory(LastFmSpy):
        def has_recent_scrobble(self, *args): raise ConnectionError("offline")
    lastfm = OfflineHistory()
    scrobbler = DeviceScrobbler("WiiM", None, lastfm, state=state)
    assert "deferred" in scrobbler._submit_pending(pending)
    assert lastfm.scrobbles == []
    assert state.due_pending(now=1_200) == [pending]


def test_timeout_after_server_acceptance_is_never_resent_after_restart(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Artist", "Song", None, None)
    pending = queue_one(state, track)
    class AcceptedThenTimeout(LastFmSpy):
        def scrobble(self, track, timestamp=None):
            super().scrobble(track, timestamp)
            raise TimeoutError("response lost after server accepted")
    lastfm = AcceptedThenTimeout()
    scrobbler = DeviceScrobbler("WiiM", None, lastfm, state=state)
    assert "held unconfirmed" in scrobbler._submit_pending(pending)
    restored = ScrobbleState(state.path)
    assert restored.due_pending(now=2_000) == []
    # A restart can observe the same song with a much later start estimate.
    pending_again = queue_one(restored, Track("Artist", "Song", "Other Album", None), 2_000)
    scrobbler = DeviceScrobbler("WiiM", None, lastfm, state=restored)
    assert "skipped duplicate" in scrobbler._submit_pending(pending_again)
    assert len(lastfm.scrobbles) == 1


def test_cannot_send_without_persisting_attempt(tmp_path, monkeypatch):
    state = ScrobbleState(tmp_path / "state.json")
    pending = queue_one(state, Track("Artist", "Song", None, None))
    def fail(): raise OSError("disk full")
    monkeypatch.setattr(state, "save", fail)
    lastfm = LastFmSpy()
    with pytest.raises(OSError):
        DeviceScrobbler("WiiM", None, lastfm, state=state)._submit_pending(pending)
    assert lastfm.scrobbles == []


def test_crash_after_post_before_completion_save_does_not_retry(tmp_path, monkeypatch):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Artist", "Song", None, None)
    pending = queue_one(state, track)
    original_save = state.save
    saves = []
    def fail_on_completion():
        saves.append(1)
        if len(saves) == 2: raise OSError("disk full")
        original_save()
    monkeypatch.setattr(state, "save", fail_on_completion)
    lastfm = LastFmSpy()
    with pytest.raises(OSError):
        DeviceScrobbler("WiiM", None, lastfm, state=state)._submit_pending(pending)
    restored = ScrobbleState(state.path)
    assert len(lastfm.scrobbles) == 1
    assert restored.due_pending(now=2_000) == []
    assert restored.has_consecutive_scrobble(track)


def test_intervening_external_song_allows_local_song_again(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    track = Track("Artist", "Song", None, None)
    state.record_scrobble(track, 1_000, now=1_100)
    pending = queue_one(state, track, 3_000)
    lastfm = LastFmSpy()
    lastfm.latest_scrobble = (Track("Artist", "Other Song", None, None), 2_000)
    assert "scrobbled" in DeviceScrobbler("WiiM", None, lastfm, state=state)._submit_pending(pending)
    assert len(lastfm.scrobbles) == 1


def test_album_metadata_change_does_not_end_a_playback_session(tmp_path):
    wiim = StaticWiim(Track("Artist", "Song", None, None), Status())
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    scrobbler = DeviceScrobbler("WiiM", wiim, lastfm, state=state, clock=lambda: 1_000)
    scrobbler.poll_once()
    scrobbler.poll_once()
    wiim.track = Track("Artist", "Song", "Album now available", None)
    scrobbler.poll_once()
    assert len(lastfm.now_playing) == 1
    assert state.due_pending(now=2_000) == []


def test_album_variant_from_second_device_is_suppressed_after_restart(tmp_path):
    state = ScrobbleState(tmp_path / "state.json")
    lastfm = LastFmSpy()
    first = queue_one(state, Track("Artist", "Song", "Album", None))
    DeviceScrobbler("First", None, lastfm, state=state)._submit_pending(first)
    state = ScrobbleState(state.path)
    second = queue_one(state, Track(" ARTIST ", "song", None, None), 2_000)
    assert "skipped duplicate" in DeviceScrobbler("Second", None, lastfm, state=state)._submit_pending(second)
    assert len(lastfm.scrobbles) == 1
