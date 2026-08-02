"""Recover real track metadata for NTS Radio Infinite Mixtape playback.

NTS mixtapes stream as one continuous Icecast stream per mixtape, so a WiiM
reports the mixtape name as the track title and never changes it. The actual
track is published as ICY ``StreamTitle`` metadata on the mixtape stream. Some
sources (AirPlay from the NTS app) forward that string to the WiiM in the
``artist`` field; others (Chromecast) drop it entirely, so it is read from the
stream instead.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from .models import Track
from .wiim import UNKNOWN_METADATA

MIXTAPES_URL = "https://www.nts.live/api/v2/mixtapes"
CATALOG_TTL_SECONDS = 21_600.0
NOW_PLAYING_TTL_SECONDS = 15.0

# NTS rotates mixtapes in and out of the catalogue, so cover art is the signal
# that survives: every NTS stream carries artwork from these hosts.
NTS_ART_HOSTS = ("ntslive.co.uk", "ntslive.net")

_STREAM_TITLE = re.compile(r"StreamTitle='(.*?)';")
# NTS publishes "ARTIST • TITLE"; some shows use "Artist - Title" instead.
_SEPARATORS = ("•", " - ")


@dataclass(frozen=True)
class Mixtape:
    alias: str
    title: str
    stream_url: str


def parse_stream_title(raw: str) -> str:
    match = _STREAM_TITLE.search(raw or "")
    return match.group(1).strip() if match else ""


def parse_now_playing(text: str) -> tuple[str, str] | None:
    """Split an NTS now-playing string into artist and title.

    Returns None for strings that are not tracks: episode credits
    ("JACK SAPSED, ISLAND TIME VOL 17"), broadcast dates ("26 Jul 2026"), and
    WiiM's empty-metadata placeholder.
    """
    candidate = (text or "").strip()
    if not candidate or candidate.casefold() in UNKNOWN_METADATA:
        return None
    for separator in _SEPARATORS:
        artist, found, title = candidate.partition(separator)
        if not found:
            continue
        artist, title = artist.strip(), title.strip()
        if artist and title:
            return artist, title
    return None


def is_nts_art(art_uri: str | None) -> bool:
    host = urlparse(art_uri or "").hostname or ""
    return any(
        host == nts_host or host.endswith(f".{nts_host}")
        for nts_host in NTS_ART_HOSTS
    )


def fetch_mixtapes(timeout: float = 10.0) -> list[Mixtape]:
    response = requests.get(MIXTAPES_URL, timeout=timeout)
    response.raise_for_status()
    results = response.json().get("results") or []
    return [
        Mixtape(
            alias=str(item.get("mixtape_alias") or ""),
            title=str(item.get("title") or ""),
            stream_url=str(item.get("audio_stream_endpoint") or ""),
        )
        for item in results
        if item.get("title") and item.get("audio_stream_endpoint")
    ]


def fetch_stream_metadata(stream_url: str, timeout: float = 10.0) -> str:
    """Read one ICY metadata block from an Icecast stream."""
    response = requests.get(
        stream_url,
        headers={"Icy-MetaData": "1"},
        stream=True,
        timeout=timeout,
    )
    try:
        response.raise_for_status()
        interval = int(response.headers.get("icy-metaint") or 0)
        if interval <= 0:
            return ""
        raw = response.raw
        _read_exactly(raw, interval)
        length = _read_exactly(raw, 1)
        if not length:
            return ""
        block = _read_exactly(raw, length[0] * 16)
        return block.rstrip(b"\x00").decode("utf-8", "replace")
    finally:
        response.close()


def _read_exactly(stream, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = stream.read(count - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


class NtsResolver:
    """Turns mixtape playback into the track NTS is actually broadcasting."""

    def __init__(
        self,
        fetch_catalog: Callable[[], list[Mixtape]] = fetch_mixtapes,
        fetch_now_playing: Callable[[str], str] = fetch_stream_metadata,
        clock: Callable[[], float] = time.time,
        catalog_ttl: float = CATALOG_TTL_SECONDS,
        now_playing_ttl: float = NOW_PLAYING_TTL_SECONDS,
    ) -> None:
        self._fetch_catalog = fetch_catalog
        self._fetch_now_playing = fetch_now_playing
        self._clock = clock
        self._catalog_ttl = catalog_ttl
        self._now_playing_ttl = now_playing_ttl
        self._catalog: list[Mixtape] = []
        self._catalog_fetched_at: float | None = None
        self._now_playing: dict[str, tuple[str, float]] = {}

    def resolve(self, track: Track) -> Track | None:
        """Return the real track, or None when this is not mixtape playback.

        When NTS is playing but no track is identified, the artist comes back
        blank so the caller skips it rather than scrobbling a mixtape name.
        """
        mixtape = self._mixtape_for(track.title)
        if mixtape is None and not is_nts_art(track.art_uri):
            return None
        now_playing = parse_now_playing(track.artist)
        if now_playing is None and mixtape is not None:
            now_playing = parse_now_playing(self._stream_now_playing(mixtape))
        if now_playing is None:
            return Track(
                artist="",
                title=track.title,
                album=None,
                duration_ms=track.duration_ms,
            )
        artist, title = now_playing
        return Track(
            artist=artist,
            title=title,
            album=None,
            duration_ms=track.duration_ms,
        )

    def _mixtape_for(self, title: str) -> Mixtape | None:
        wanted = (title or "").strip().casefold()
        if not wanted:
            return None
        for mixtape in self._catalog_entries():
            if mixtape.title.casefold() == wanted:
                return mixtape
        return None

    def _catalog_entries(self) -> list[Mixtape]:
        now = self._clock()
        if (
            self._catalog_fetched_at is not None
            and now - self._catalog_fetched_at < self._catalog_ttl
        ):
            return self._catalog
        try:
            self._catalog = list(self._fetch_catalog())
        except Exception as exc:  # noqa: BLE001 - stale catalog beats no scrobbles
            logging.debug("Could not refresh NTS mixtape catalog: %s", exc)
            return self._catalog
        self._catalog_fetched_at = now
        return self._catalog

    def _stream_now_playing(self, mixtape: Mixtape) -> str:
        """Read the stream's ICY metadata, shared briefly across devices.

        Reading it opens the audio stream, so multi-room setups polling the
        same mixtape in one cycle reuse a single read.
        """
        now = self._clock()
        cached = self._now_playing.get(mixtape.stream_url)
        if cached is not None and now - cached[1] < self._now_playing_ttl:
            return cached[0]
        try:
            title = parse_stream_title(self._fetch_now_playing(mixtape.stream_url))
        except Exception as exc:  # noqa: BLE001 - a dead stream is not a crash
            logging.debug("Could not read NTS stream metadata: %s", exc)
            return ""
        self._now_playing[mixtape.stream_url] = (title, now)
        return title
