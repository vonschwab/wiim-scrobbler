from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    artist: str
    title: str
    album: str | None
    duration_ms: int | None

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
