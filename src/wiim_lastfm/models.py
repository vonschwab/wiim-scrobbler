from dataclasses import dataclass
import unicodedata


def song_identity(artist: str, title: str) -> tuple[str, str]:
    return tuple(" ".join(unicodedata.normalize("NFKC", value).casefold().split())
                 for value in (artist, title))


@dataclass(frozen=True)
class Track:
    artist: str
    title: str
    album: str | None
    duration_ms: int | None
    # Identifies the streaming service behind the playback; not scrobbled and
    # deliberately excluded from `key` so it never affects deduplication.
    art_uri: str | None = None

    @property
    def song_key(self) -> tuple[str, str]:
        return song_identity(self.artist, self.title)

    @property
    def key(self) -> tuple[str, str, str | None]:
        return (self.artist.casefold(), self.title.casefold(), self.album.casefold() if self.album else None)


@dataclass(frozen=True)
class PlayerStatus:
    is_playing: bool
    position_ms: int
    duration_ms: int | None
    mode: str | None


@dataclass(frozen=True)
class DeviceConfig:
    name: str
    host: str
