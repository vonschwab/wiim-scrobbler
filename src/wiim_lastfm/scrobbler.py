from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass

from .lastfm import LastFmClient
from .models import Track
from .nts import NtsResolver
from .state import PendingScrobble, ScrobbleState
from .wiim import WiimClient


class ScrobbleDecision(enum.Enum):
    IGNORE = "ignore"
    WAIT = "wait"
    SCROBBLE = "scrobble"


@dataclass
class TrackSession:
    track: Track
    started_at: int
    observations: int = 1
    now_playing_sent: bool = False


def should_scrobble(track: Track, played_ms: int) -> ScrobbleDecision:
    if not track.artist or not track.title:
        return ScrobbleDecision.IGNORE
    if not track.duration_ms:
        return ScrobbleDecision.WAIT

    threshold_ms = min(track.duration_ms // 2, 240_000)
    return (
        ScrobbleDecision.SCROBBLE
        if played_ms >= threshold_ms
        else ScrobbleDecision.WAIT
    )


class DeviceScrobbler:
    def __init__(
        self,
        name: str,
        wiim: WiimClient,
        lastfm: LastFmClient,
        dry_run: bool = False,
        state: ScrobbleState | None = None,
        settlement_seconds: int = 90,
        nts: NtsResolver | None = None,
        clock=time.time,
    ) -> None:
        self.name = name
        self.wiim = wiim
        self.lastfm = lastfm
        self.dry_run = dry_run
        self.state = state
        self.settlement_seconds = settlement_seconds
        self.nts = nts
        self._clock = clock
        self.session: TrackSession | None = None

    def poll_once(self) -> str | None:
        now = int(self._clock())
        status = self.wiim.player_status()
        if not status.is_playing:
            self._queue_session(now)
            self.session = None
            return self._flush_due_pending(now)

        track = self._resolve(self.wiim.current_track(duration_ms=status.duration_ms))
        if not track.artist or not track.title:
            return self._flush_due_pending(now) or (
                f"{self.name}: playing, but WiiM did not expose artist/title"
            )

        if self.session is None or self.session.track.key != track.key:
            self._queue_session(now)
            started_at = int(now - (status.position_ms / 1000))
            self.session = TrackSession(track=track, started_at=started_at)
            self._now_playing(track)
            self.session.now_playing_sent = True
            return self._flush_due_pending(now) or (
                f"{self.name}: now playing {track.artist} - {track.title}"
            )

        self.session.observations += 1
        return self._flush_due_pending(now)

    def _resolve(self, track: Track) -> Track:
        if self.nts is None:
            return track
        resolved = self.nts.resolve(track)
        return track if resolved is None else resolved

    def _queue_session(self, now: int) -> None:
        if (
            self.session is None
            or self.session.observations < 2
            or self.dry_run
            or self.state is None
        ):
            return
        self.state.queue_pending(
            self.session.track,
            started_at=self.session.started_at,
            queued_at=now,
        )

    def _flush_due_pending(self, now: int) -> str | None:
        if self.dry_run or self.state is None:
            return None
        due = self.state.due_pending(
            now=now, settlement_seconds=self.settlement_seconds
        )
        if not due:
            return None
        return self._submit_pending(due[0])

    def _submit_pending(self, pending: PendingScrobble) -> str:
        track = pending.track
        if self.state and (
            self.state.has_recent_scrobble(track, pending.started_at)
            or self.state.has_consecutive_scrobble(track)
        ):
            self.state.discard_pending(pending)
            return f"{self.name}: skipped duplicate {track.artist} - {track.title}"
        try:
            if self.lastfm.has_recent_scrobble(track, pending.started_at):
                self.state.discard_pending(pending)
                return (
                    f"{self.name}: skipped Last.fm duplicate "
                    f"{track.artist} - {track.title}"
                )
        except Exception as exc:
            logging.warning("%s: could not check Last.fm history: %s", self.name, exc)
        self._scrobble(track, pending.started_at)
        self.state.complete_pending(pending)
        return f"{self.name}: scrobbled {track.artist} - {track.title}"

    def _now_playing(self, track: Track) -> None:
        if not self.dry_run:
            self.lastfm.update_now_playing(track)

    def _scrobble(self, track: Track, timestamp: int) -> None:
        if not self.dry_run:
            self.lastfm.scrobble(track, timestamp=timestamp)
