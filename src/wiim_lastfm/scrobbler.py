from __future__ import annotations

import enum
import time
from dataclasses import dataclass

from .lastfm import LastFmClient
from .models import Track
from .state import ScrobbleState
from .wiim import WiimClient


class ScrobbleDecision(enum.Enum):
    IGNORE = "ignore"
    WAIT = "wait"
    SCROBBLE = "scrobble"


@dataclass
class TrackSession:
    track: Track
    started_at: int
    now_playing_sent: bool = False
    scrobbled: bool = False


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
    ) -> None:
        self.name = name
        self.wiim = wiim
        self.lastfm = lastfm
        self.dry_run = dry_run
        self.state = state
        self.session: TrackSession | None = None

    def poll_once(self) -> str | None:
        status = self.wiim.player_status()
        if not status.is_playing:
            return None

        track = self.wiim.current_track(duration_ms=status.duration_ms)
        if not track.artist or not track.title:
            return f"{self.name}: playing, but WiiM did not expose artist/title"

        if self.session is None or self.session.track.key != track.key:
            started_at = int(time.time() - (status.position_ms / 1000))
            self.session = TrackSession(track=track, started_at=started_at)
            self._now_playing(track)
            self.session.now_playing_sent = True
            return f"{self.name}: now playing {track.artist} - {track.title}"

        decision = should_scrobble(track, status.position_ms)
        if decision == ScrobbleDecision.SCROBBLE and not self.session.scrobbled:
            if self.state and self.state.has_recent_scrobble(track, self.session.started_at):
                self.session.scrobbled = True
                return f"{self.name}: skipped duplicate {track.artist} - {track.title}"
            self._scrobble(track, self.session.started_at)
            self.session.scrobbled = True
            if self.state and not self.dry_run:
                self.state.record_scrobble(track, self.session.started_at)
            return f"{self.name}: scrobbled {track.artist} - {track.title}"

        return None

    def _now_playing(self, track: Track) -> None:
        if not self.dry_run:
            self.lastfm.update_now_playing(track)

    def _scrobble(self, track: Track, timestamp: int) -> None:
        if not self.dry_run:
            self.lastfm.scrobble(track, timestamp=timestamp)
