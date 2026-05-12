from __future__ import annotations

import json
from typing import Any

import requests
import urllib3

from .models import PlayerStatus, Track

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WiimClient:
    def __init__(
        self, host: str, timeout: float = 5.0, verify_tls: bool = False
    ) -> None:
        self.host = host
        self.base_url = _base_url(host)
        self.timeout = timeout
        self.verify_tls = verify_tls

    def command(self, command: str) -> Any:
        url = f"{self.base_url}/httpapi.asp"
        response = requests.get(
            url,
            params={"command": command},
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        return load_json_response(response)

    def player_status(self) -> PlayerStatus:
        return parse_player_status(self.command("getPlayerStatus"))

    def current_track(self, duration_ms: int | None = None) -> Track:
        metadata = self.command("getMetaInfo")
        return safe_parse_track(metadata, duration_ms=duration_ms)


def parse_player_status(response: dict[str, Any]) -> PlayerStatus:
    return PlayerStatus(
        is_playing=response.get("status") == "play",
        position_ms=_int_or_zero(response.get("curpos")),
        duration_ms=_int_or_none(response.get("totlen")),
        mode=response.get("mode"),
    )


def parse_track(response: dict[str, Any], duration_ms: int | None) -> Track:
    raw_metadata = response.get("metaData") or {}
    metadata = {str(key).strip(): value for key, value in raw_metadata.items()}
    if not metadata:
        metadata = {str(key).strip(): value for key, value in response.items()}
    return Track(
        artist=_metadata_text(metadata, "artist"),
        title=_metadata_text(metadata, "title"),
        album=_optional_str(_metadata_text(metadata, "album")),
        duration_ms=duration_ms,
    )


def safe_parse_track(response: Any, duration_ms: int | None) -> Track:
    if not isinstance(response, dict):
        return Track(artist="", title="", album=None, duration_ms=duration_ms)
    return parse_track(response, duration_ms=duration_ms)


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _int_or_zero(value: Any) -> int:
    return _int_or_none(value) or 0


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_text(metadata: dict[str, Any], name: str) -> str:
    value = metadata.get(name) or metadata.get(name.title()) or ""
    text = str(value).strip()
    if _looks_like_hex(text):
        try:
            return bytes.fromhex(text).decode("utf-8").strip()
        except ValueError:
            return text
    return text


def _looks_like_hex(value: str) -> bool:
    return bool(value) and len(value) % 2 == 0 and all(
        char in "0123456789abcdefABCDEF" for char in value
    )


def _base_url(host: str) -> str:
    normalized = host.strip().rstrip("/")
    if normalized.startswith(("http://", "https://")):
        return normalized
    return f"https://{normalized}"


def load_json_response(response: Any) -> Any:
    try:
        return response.json()
    except ValueError:
        text = response.content.decode("utf-8").strip()
        try:
            return json.loads(text)
        except ValueError:
            return text
