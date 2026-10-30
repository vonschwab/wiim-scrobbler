from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .models import Track, song_identity


class LastFmClient:
    api_root = "https://ws.audioscrobbler.com/2.0/"

    def __init__(
        self,
        api_key: str,
        shared_secret: str,
        session_key: str | None = None,
        username: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.session_key = session_key
        self.username = username
        self.timeout = timeout
        self.latest_scrobble: tuple[Track, int] | None = None
        self._corrections: dict[tuple[str, str], tuple[str, str]] = {}

    def sign(self, params: dict[str, Any]) -> str:
        payload = "".join(
            f"{key}{value}" for key, value in sorted(params.items()) if key != "format"
        )
        payload += self.shared_secret
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def auth_url(self, token: str) -> str:
        return "https://www.last.fm/api/auth/?" + urlencode(
            {"api_key": self.api_key, "token": token}
        )

    def get_token(self) -> str:
        data = self._signed_post({"method": "auth.getToken"})
        return data["token"]

    def get_session_key(self, token: str) -> str:
        data = self._signed_post({"method": "auth.getSession", "token": token})
        return data["session"]["key"]

    def update_now_playing(self, track: Track) -> None:
        params: dict[str, Any] = {
            "method": "track.updateNowPlaying",
            "artist": track.artist,
            "track": track.title,
        }
        if track.album:
            params["album"] = track.album
        if track.duration_ms:
            params["duration"] = track.duration_ms // 1000
        data = self._signed_post(params, require_session=True)
        now_playing = data.get("nowplaying", {})
        artist = now_playing.get("artist", {}).get("#text")
        title = now_playing.get("track", {}).get("#text")
        if artist and title:
            # Corrections are for comparison only, never rewritten POST input.
            self._corrections[track.song_key] = song_identity(artist, title)
            if len(self._corrections) > 256:
                del self._corrections[next(iter(self._corrections))]

    def scrobble(self, track: Track, timestamp: int | None = None) -> Track:
        params: dict[str, Any] = {
            "method": "track.scrobble",
            "artist": track.artist,
            "track": track.title,
            "timestamp": timestamp or int(time.time()),
        }
        if track.album:
            params["album"] = track.album
        if track.duration_ms:
            params["duration"] = track.duration_ms // 1000
        data = self._signed_post(params, require_session=True)
        result = data.get("scrobbles", {})
        if str(result.get("@attr", {}).get("accepted")) != "1":
            raise RuntimeError("Last.fm did not confirm an accepted scrobble")
        item = result.get("scrobble", {})
        if isinstance(item, list):
            item = item[0] if item else {}
        return Track(
            item.get("artist", {}).get("#text") or track.artist,
            item.get("track", {}).get("#text") or track.title,
            track.album, track.duration_ms,
        )

    def has_recent_scrobble(
        self, track: Track, started_at: int, window_seconds: int = 600
    ) -> bool:
        if not self.username:
            raise ValueError("lastfm.username is required to check for duplicates")

        self.latest_scrobble = None

        response = requests.get(
            self.api_root,
            params={
                "method": "user.getrecenttracks",
                "user": self.username,
                "api_key": self.api_key,
                "format": "json",
                "limit": 100,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Last.fm error {data['error']}: {data.get('message')}")

        if not isinstance(data.get("recenttracks"), dict):
            raise RuntimeError("Invalid Last.fm recent history response")
        if "track" not in data["recenttracks"]:
            raise RuntimeError("Missing Last.fm recent track list")
        recent_tracks = data["recenttracks"]["track"]
        if isinstance(recent_tracks, dict):
            recent_tracks = [recent_tracks]

        if not isinstance(recent_tracks, list):
            raise RuntimeError("Invalid Last.fm recent track list")
        completed = []
        for recent_track in recent_tracks:
            if not isinstance(recent_track, dict):
                raise RuntimeError("Invalid Last.fm recent track entry")
            if str(recent_track.get("@attr", {}).get("nowplaying", "")).casefold() == "true":
                continue
            artist = recent_track.get("artist", {}).get("#text", "")
            title = recent_track.get("name", "")
            timestamp = recent_track.get("date", {}).get("uts")
            if not artist or not title or not timestamp:
                raise RuntimeError("Incomplete Last.fm scrobble in recent history")
            completed.append((Track(artist, title, None, None), int(timestamp)))
        completed.sort(key=lambda item: item[1], reverse=True)
        self.latest_scrobble = completed[0] if completed else None
        keys = {track.song_key, self._corrections.get(track.song_key, track.song_key)}
        return any(
            recent.song_key in keys
            and (index == 0 or abs(timestamp - started_at) <= window_seconds)
            for index, (recent, timestamp) in enumerate(completed)
        )

    def _signed_post(
        self, params: dict[str, Any], require_session: bool = False
    ) -> dict[str, Any]:
        request_params = {"api_key": self.api_key, "format": "json", **params}
        if require_session:
            if not self.session_key:
                raise ValueError("Last.fm session_key is required for this command")
            request_params["sk"] = self.session_key
        request_params["api_sig"] = self.sign(request_params)

        response = requests.post(self.api_root, data=request_params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Last.fm error {data['error']}: {data.get('message')}")
        return data
