from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .models import Track


class LastFmClient:
    api_root = "https://ws.audioscrobbler.com/2.0/"

    def __init__(
        self,
        api_key: str,
        shared_secret: str,
        session_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.session_key = session_key
        self.timeout = timeout

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
        self._signed_post(params, require_session=True)

    def scrobble(self, track: Track, timestamp: int | None = None) -> None:
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
        self._signed_post(params, require_session=True)

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
