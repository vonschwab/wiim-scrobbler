"""Recover real track metadata for NTS shows and Infinite Mixtapes.

NTS mixtapes stream as one continuous Icecast stream per mixtape, so a WiiM
reports the mixtape name as the track title and never changes it. The actual
track is published as ICY ``StreamTitle`` metadata on the mixtape stream. Some
sources (AirPlay from the NTS app) forward that string to the WiiM in the
``artist`` field; others (Chromecast) drop it entirely, so it is read from the
stream instead.
"""

from __future__ import annotations

import logging
import html
import json
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from .models import Track
from .wiim import UNKNOWN_METADATA

MIXTAPES_URL = "https://www.nts.live/api/v2/mixtapes"
SEARCH_URL = "https://www.nts.live/api/v2/search"
CATALOG_TTL_SECONDS = 21_600.0
NOW_PLAYING_TTL_SECONDS = 15.0

# NTS rotates mixtapes in and out of the catalogue, so cover art is the signal
# that survives: every NTS stream carries artwork from these hosts.
NTS_ART_HOSTS = ("ntslive.co.uk", "ntslive.net")

SHOW_RETRY_SECONDS = 60.0
SHOW_MISS_TTL_SECONDS = 300.0

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


def _title_key(title: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(title))
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-"}))
    return " ".join(text.casefold().split())


def lookup_show(title: str, timeout: float = 5.0) -> bool:
    """Confirm a full show/episode title using the same search as nts.live.

    Search also returns loosely related hits. Only an exact normalised title
    on a show or episode counts; an artist/track hit does not identify NTS.
    """
    response = requests.get(
        SEARCH_URL,
        params={"q": title, "version": 2, "types[]": ["show", "episode"], "limit": 50},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("Invalid NTS search response")
    wanted = _title_key(title)
    return any(
        isinstance(item, dict)
        and item.get("article_type") in {"show", "episode"}
        and isinstance(item.get("title"), str)
        and _title_key(item["title"]) == wanted
        for item in data["results"]
    )


def _show_candidate(track: Track) -> bool:
    # AirPlay hides the source artwork. Look up combined artist/song metadata,
    # broadcast dates, or metadata with the WiiM AirPlay artwork placeholder.
    # Ordinary album tracks never need a show lookup.
    album = (track.album or "").strip().casefold()
    return bool(
        track.title.strip()
        and (not album or album in UNKNOWN_METADATA)
        and (
            parse_now_playing(track.artist)
            or re.fullmatch(r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}", track.artist.strip())
            or urlparse(track.art_uri or "").path.casefold().endswith("/airplayartworkdata.jpeg")
        )
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
    """Turns NTS playback into the individual track being broadcast."""

    def __init__(
        self,
        fetch_catalog: Callable[[], list[Mixtape]] = fetch_mixtapes,
        fetch_now_playing: Callable[[str], str] = fetch_stream_metadata,
        clock: Callable[[], float] = time.time,
        catalog_ttl: float = CATALOG_TTL_SECONDS,
        now_playing_ttl: float = NOW_PLAYING_TTL_SECONDS,
        find_show: Callable[[str], bool] = lookup_show,
        show_cache_path: str | Path | None = None,
    ) -> None:
        self._fetch_catalog = fetch_catalog
        self._fetch_now_playing = fetch_now_playing
        self._clock = clock
        self._catalog_ttl = catalog_ttl
        self._now_playing_ttl = now_playing_ttl
        self._catalog: list[Mixtape] = []
        self._catalog_fetched_at: float | None = None
        self._now_playing: dict[str, tuple[str, float]] = {}
        self._find_show = find_show
        self._show_cache_path = Path(show_cache_path) if show_cache_path else None
        self._known_shows: set[str] = set()
        self._show_checks: dict[str, tuple[bool | None, float]] = {}
        self._load_shows()

    def resolve(self, track: Track) -> Track | None:
        """Return the real track, or None when NTS playback is not recognised.

        When NTS is playing but no track is identified, the artist comes back
        blank so the caller skips it rather than scrobbling a mixtape name.
        """
        mixtape = self._mixtape_for(track.title)
        if mixtape is None and not is_nts_art(track.art_uri):
            if not _show_candidate(track):
                return None
            identified = self._is_show(track.title)
            if identified is False:
                return None
            if identified is None:
                # A failed lookup must not turn the whole show into a song.
                return Track("", track.title, None, None)
        now_playing = parse_now_playing(track.artist)
        if now_playing is None and mixtape is not None:
            now_playing = parse_now_playing(self._stream_now_playing(mixtape))
        if now_playing is None:
            return Track(
                artist="",
                title=track.title,
                album=None,
                duration_ms=None,
            )
        artist, title = now_playing
        return Track(
            artist=artist,
            title=title,
            album=None,
            # The WiiM duration belongs to the entire show/stream, not this song.
            duration_ms=None,
        )

    def _is_show(self, title: str) -> bool | None:
        key = _title_key(title)
        if key in self._known_shows:
            return True
        now = self._clock()
        cached = self._show_checks.get(key)
        if cached is not None and now < cached[1]:
            return cached[0]
        try:
            found = self._find_show(title)
        except Exception as exc:
            logging.warning("Could not identify NTS show %r; retrying: %s", title, exc)
            self._show_checks[key] = (None, now + SHOW_RETRY_SECONDS)
            return None
        if found:
            self._known_shows.add(key)
            self._save_shows()
        else:
            # Bound misses to a short window so newly indexed episodes recover.
            self._show_checks = {
                k: v for k, v in self._show_checks.items() if now < v[1]
            }
            self._show_checks[key] = (False, now + SHOW_MISS_TTL_SECONDS)
        return found

    def _load_shows(self) -> None:
        if self._show_cache_path is None:
            return
        try:
            data = json.loads(self._show_cache_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._known_shows = {_title_key(x) for x in data if isinstance(x, str) and x.strip()}
        except (OSError, ValueError):
            pass

    def _save_shows(self) -> None:
        if self._show_cache_path is None:
            return
        try:
            self._show_cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._show_cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(sorted(self._known_shows)), encoding="utf-8")
            temporary.replace(self._show_cache_path)
        except OSError as exc:
            logging.warning("Could not save NTS show cache: %s", exc)

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
