from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .models import Track


class ScrobbleState:
    def __init__(
        self,
        path: str | Path,
        duplicate_window_seconds: int = 120,
        retention_seconds: int = 14 * 24 * 60 * 60,
    ) -> None:
        self.path = Path(path)
        self.duplicate_window_seconds = duplicate_window_seconds
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

    def record_scrobble(
        self, track: Track, started_at: int, now: int | None = None
    ) -> None:
        self._data["scrobbles"].append(
            {
                "track_key": _track_key(track),
                "artist": track.artist,
                "title": track.title,
                "album": track.album,
                "started_at": started_at,
                "recorded_at": now or int(time.time()),
            }
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

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "scrobbles": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "scrobbles": []}
        if not isinstance(data, dict):
            return {"version": 1, "scrobbles": []}
        scrobbles = data.get("scrobbles")
        if not isinstance(scrobbles, list):
            data["scrobbles"] = []
        data.setdefault("version", 1)
        return data


def _track_key(track: Track) -> str:
    album = track.album.casefold().strip() if track.album else ""
    return "\0".join(
        [track.artist.casefold().strip(), track.title.casefold().strip(), album]
    )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
