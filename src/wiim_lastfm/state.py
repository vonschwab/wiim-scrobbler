from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Track


@dataclass(frozen=True)
class PendingScrobble:
    track: Track
    started_at: int
    queued_at: int


class ScrobbleState:
    def __init__(
        self,
        path: str | Path,
        duplicate_window_seconds: int = 120,
        consecutive_duplicate_window_seconds: int = 6 * 60 * 60,
        retention_seconds: int = 14 * 24 * 60 * 60,
    ) -> None:
        self.path = Path(path)
        self.duplicate_window_seconds = duplicate_window_seconds
        self.consecutive_duplicate_window_seconds = consecutive_duplicate_window_seconds
        self.retention_seconds = retention_seconds
        self._data = self._load()

    def has_recent_scrobble(self, track: Track, started_at: int) -> bool:
        key = _track_key(track)
        for item in self._data["scrobbles"]:
            if not isinstance(item, dict):
                continue
            if item.get("track_key") != key:
                continue
            item_started_at = _safe_int(item.get("started_at"))
            if item_started_at is None:
                continue
            if abs(item_started_at - started_at) <= self.duplicate_window_seconds:
                return True
        return False

    def has_consecutive_scrobble(self, track: Track, now: int | None = None) -> bool:
        key = _track_key(track)
        current_time = now or int(time.time())
        for item in reversed(self._data["scrobbles"]):
            if not isinstance(item, dict):
                continue
            item_key = item.get("track_key")
            if not isinstance(item_key, str):
                continue
            recorded_at = _safe_int(item.get("recorded_at"))
            if recorded_at is None:
                continue
            if current_time - recorded_at > self.consecutive_duplicate_window_seconds:
                return False
            return item_key == key
        return False

    def record_scrobble(
        self, track: Track, started_at: int, now: int | None = None
    ) -> None:
        self._data["scrobbles"].append(_scrobble_item(track, started_at, now))
        self.prune(now=now)
        self.save()

    def queue_pending(
        self, track: Track, started_at: int, queued_at: int | None = None
    ) -> bool:
        if self.has_recent_scrobble(track, started_at):
            return False
        key = _track_key(track)
        for item in self._data["pending"]:
            if not isinstance(item, dict) or item.get("track_key") != key:
                continue
            item_started_at = _safe_int(item.get("started_at"))
            if (
                item_started_at is not None
                and abs(item_started_at - started_at) <= self.duplicate_window_seconds
            ):
                return False

        self._data["pending"].append(
            {
                "track_key": key,
                "artist": track.artist,
                "title": track.title,
                "album": track.album,
                "duration_ms": track.duration_ms,
                "started_at": started_at,
                "queued_at": queued_at if queued_at is not None else int(time.time()),
            }
        )
        self.prune(now=queued_at)
        self.save()
        return True

    def due_pending(
        self, now: int | None = None, settlement_seconds: int = 90
    ) -> list[PendingScrobble]:
        current_time = now or int(time.time())
        pending = []
        for item in self._data["pending"]:
            parsed = _pending_scrobble(item)
            if parsed and current_time - parsed.queued_at >= settlement_seconds:
                pending.append(parsed)
        return sorted(pending, key=lambda item: item.started_at)

    def discard_pending(self, pending: PendingScrobble) -> None:
        self._remove_pending(pending)
        self.save()

    def complete_pending(
        self, pending: PendingScrobble, now: int | None = None
    ) -> None:
        self._remove_pending(pending)
        self._data["scrobbles"].append(
            _scrobble_item(pending.track, pending.started_at, now)
        )
        self.prune(now=now)
        self.save()

    def prune(self, now: int | None = None) -> None:
        cutoff = (now or int(time.time())) - self.retention_seconds
        kept = []
        for item in self._data["scrobbles"]:
            if not isinstance(item, dict):
                continue
            recorded_at = _safe_int(item.get("recorded_at"))
            if recorded_at is None:
                continue
            if recorded_at >= cutoff:
                kept.append(item)
        self._data["scrobbles"] = kept
        self._data["pending"] = [
            item
            for item in self._data["pending"]
            if isinstance(item, dict)
            and (_safe_int(item.get("queued_at")) or 0) >= cutoff
        ]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 2, "scrobbles": [], "pending": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 2, "scrobbles": [], "pending": []}
        if not isinstance(data, dict):
            return {"version": 2, "scrobbles": [], "pending": []}
        scrobbles = data.get("scrobbles")
        if not isinstance(scrobbles, list):
            data["scrobbles"] = []
        pending = data.get("pending")
        if not isinstance(pending, list):
            data["pending"] = []
        data["version"] = 2
        return data

    def _remove_pending(self, pending: PendingScrobble) -> None:
        key = _track_key(pending.track)
        self._data["pending"] = [
            item
            for item in self._data["pending"]
            if not (
                isinstance(item, dict)
                and item.get("track_key") == key
                and _safe_int(item.get("started_at")) == pending.started_at
            )
        ]


def _track_key(track: Track) -> str:
    album = track.album.casefold().strip() if track.album else ""
    return "\0".join(
        [track.artist.casefold().strip(), track.title.casefold().strip(), album]
    )


def _scrobble_item(track: Track, started_at: int, now: int | None) -> dict[str, Any]:
    return {
        "track_key": _track_key(track),
        "artist": track.artist,
        "title": track.title,
        "album": track.album,
        "started_at": started_at,
        "recorded_at": now or int(time.time()),
    }


def _pending_scrobble(item: Any) -> PendingScrobble | None:
    if not isinstance(item, dict):
        return None
    artist = item.get("artist")
    title = item.get("title")
    started_at = _safe_int(item.get("started_at"))
    queued_at = _safe_int(item.get("queued_at"))
    if not isinstance(artist, str) or not isinstance(title, str):
        return None
    if started_at is None or queued_at is None:
        return None
    return PendingScrobble(
        track=Track(
            artist=artist,
            title=title,
            album=item.get("album") if isinstance(item.get("album"), str) else None,
            duration_ms=_safe_int(item.get("duration_ms")),
        ),
        started_at=started_at,
        queued_at=queued_at,
    )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
