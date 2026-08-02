import pytest

from wiim_lastfm.models import Track
from wiim_lastfm.nts import (
    Mixtape,
    NtsResolver,
    parse_now_playing,
    parse_stream_title,
)


POOLSIDE = Mixtape(
    alias="poolside",
    title="Poolside",
    stream_url="https://stream-mixtape-geo.ntslive.net/mixtape4",
)
ISLAND_TIME = Mixtape(
    alias="island-time",
    title="Island Time",
    stream_url="https://stream-mixtape-geo.ntslive.net/mixtape21",
)


def catalog_of(*mixtapes):
    def fetch():
        return list(mixtapes)

    return fetch


def unreachable_stream(url):
    raise AssertionError(f"stream metadata should not be fetched, got {url}")


def test_parse_now_playing_splits_bullet_separated_artist_and_title():
    assert parse_now_playing("CLAUDIUS LINTON  •  Crying Time") == (
        "CLAUDIUS LINTON",
        "Crying Time",
    )


def test_parse_now_playing_splits_hyphen_separated_artist_and_title():
    assert parse_now_playing("Sofie Birch - Spirit Cartography") == (
        "Sofie Birch",
        "Spirit Cartography",
    )


def test_parse_now_playing_keeps_hyphens_inside_the_title():
    assert parse_now_playing("anaiis - Call Me (a) - (B)") == (
        "anaiis",
        "Call Me (a) - (B)",
    )


def test_parse_now_playing_rejects_episode_credit_without_separator():
    assert parse_now_playing("JACK SAPSED, ISLAND TIME VOL 17") is None


def test_parse_now_playing_rejects_broadcast_date():
    assert parse_now_playing("26 Jul 2026") is None


def test_parse_now_playing_rejects_wiim_unknown_placeholder():
    assert parse_now_playing("unknow") is None


def test_parse_stream_title_extracts_icy_stream_title():
    raw = "StreamTitle='AL MOODIE  •  Moses Rock';json='{}';"

    assert parse_stream_title(raw) == "AL MOODIE  •  Moses Rock"


def test_parse_stream_title_returns_empty_string_when_no_track_is_published():
    assert parse_stream_title("StreamTitle='';json='{}';") == ""


def test_resolver_ignores_playback_that_is_not_an_nts_mixtape():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=unreachable_stream,
    )
    track = Track(
        artist="Orchid Mantis",
        title="blank slate",
        album="i don't think i'm ever going to figure it out",
        duration_ms=180_000,
    )

    assert resolver.resolve(track) is None


def test_resolver_unpacks_track_the_device_reported_as_the_artist():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(ISLAND_TIME),
        fetch_now_playing=unreachable_stream,
    )
    track = Track(
        artist="CLAUDIUS LINTON  •  Crying Time",
        title="ISLAND TIME",
        album=None,
        duration_ms=None,
    )

    resolved = resolver.resolve(track)

    assert resolved.artist == "CLAUDIUS LINTON"
    assert resolved.title == "Crying Time"
    assert resolved.album is None


def test_resolver_reads_stream_metadata_when_device_reports_no_track():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=lambda url: "StreamTitle='Benedek  •  Alpha Tape';json='{}';",
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)

    resolved = resolver.resolve(track)

    assert resolved.artist == "Benedek"
    assert resolved.title == "Alpha Tape"


def test_resolver_blanks_the_artist_when_nts_publishes_no_track():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=lambda url: "StreamTitle='';json='{}';",
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)

    resolved = resolver.resolve(track)

    assert resolved is not None
    assert resolved.artist == ""
    assert resolved.title == "POOLSIDE"


def test_resolver_blanks_the_artist_when_device_reports_an_episode_credit():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(ISLAND_TIME),
        fetch_now_playing=lambda url: "StreamTitle='';json='{}';",
    )
    track = Track(
        artist="JACK SAPSED, ISLAND TIME VOL 17",
        title="ISLAND TIME",
        album=None,
        duration_ms=None,
    )

    resolved = resolver.resolve(track)

    assert resolved.artist == ""


def test_resolver_fetches_stream_metadata_for_the_matching_mixtape():
    requested = []

    def fetch_now_playing(url):
        requested.append(url)
        return "StreamTitle='Benedek  •  Alpha Tape';json='{}';"

    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE, ISLAND_TIME),
        fetch_now_playing=fetch_now_playing,
    )
    resolver.resolve(Track(artist="", title="ISLAND TIME", album=None, duration_ms=None))

    assert requested == [ISLAND_TIME.stream_url]


def test_resolver_caches_the_mixtape_catalog_between_lookups():
    calls = []

    def fetch_catalog():
        calls.append(1)
        return [POOLSIDE]

    resolver = NtsResolver(
        fetch_catalog=fetch_catalog,
        fetch_now_playing=lambda url: "StreamTitle='';json='{}';",
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)
    resolver.resolve(track)
    resolver.resolve(track)

    assert len(calls) == 1


def test_resolver_refetches_the_catalog_after_the_cache_expires():
    calls = []
    now = [1000.0]

    def fetch_catalog():
        calls.append(1)
        return [POOLSIDE]

    resolver = NtsResolver(
        fetch_catalog=fetch_catalog,
        fetch_now_playing=lambda url: "StreamTitle='';json='{}';",
        clock=lambda: now[0],
        catalog_ttl=600.0,
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)
    resolver.resolve(track)
    now[0] += 601.0
    resolver.resolve(track)

    assert len(calls) == 2


def test_resolver_keeps_device_metadata_when_the_catalog_is_unreachable():
    def fetch_catalog():
        raise ConnectionError("nts.live unreachable")

    resolver = NtsResolver(
        fetch_catalog=fetch_catalog,
        fetch_now_playing=unreachable_stream,
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)

    assert resolver.resolve(track) is None


def test_resolver_blanks_the_artist_when_the_stream_is_unreachable():
    def fetch_now_playing(url):
        raise ConnectionError("stream unreachable")

    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=fetch_now_playing,
    )
    track = Track(
        artist="unknow-leftover",
        title="POOLSIDE",
        album=None,
        duration_ms=None,
    )

    resolved = resolver.resolve(track)

    assert resolved.artist == ""


@pytest.mark.parametrize("title", ["POOLSIDE", "Poolside", "poolside "])
def test_resolver_matches_mixtape_titles_regardless_of_case(title):
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=lambda url: "StreamTitle='Benedek  •  Alpha Tape';json='{}';",
    )

    resolved = resolver.resolve(
        Track(artist="", title=title, album=None, duration_ms=None)
    )

    assert resolved.artist == "Benedek"


def test_resolver_reuses_stream_metadata_across_devices_in_the_same_cycle():
    calls = []

    def fetch_now_playing(url):
        calls.append(url)
        return "StreamTitle='Benedek  •  Alpha Tape';json='{}';"

    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=fetch_now_playing,
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)
    resolver.resolve(track)
    resolver.resolve(track)

    assert len(calls) == 1


def test_resolver_rereads_stream_metadata_after_the_cache_window():
    calls = []
    now = [1000.0]

    def fetch_now_playing(url):
        calls.append(url)
        return "StreamTitle='Benedek  •  Alpha Tape';json='{}';"

    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=fetch_now_playing,
        clock=lambda: now[0],
        now_playing_ttl=15.0,
    )
    track = Track(artist="", title="POOLSIDE", album=None, duration_ms=None)
    resolver.resolve(track)
    now[0] += 16.0
    resolver.resolve(track)

    assert len(calls) == 2


NTS_ART = "https://media2.ntslive.co.uk/crop/800x800/art.jpeg"


def test_resolver_unpacks_track_for_a_mixtape_missing_from_the_catalogue():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=unreachable_stream,
    )
    track = Track(
        artist="Sofie Birch - Spirit Cartography",
        title="THE SLIP",
        album=None,
        duration_ms=None,
        art_uri=NTS_ART,
    )

    resolved = resolver.resolve(track)

    assert resolved.artist == "Sofie Birch"
    assert resolved.title == "Spirit Cartography"


def test_resolver_blanks_the_artist_for_nts_playback_it_cannot_identify():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=unreachable_stream,
    )
    track = Track(
        artist="26 Jul 2026",
        title="THE SLIP",
        album=None,
        duration_ms=None,
        art_uri=NTS_ART,
    )

    assert resolver.resolve(track).artist == ""


def test_resolver_ignores_art_from_other_services():
    resolver = NtsResolver(
        fetch_catalog=catalog_of(POOLSIDE),
        fetch_now_playing=unreachable_stream,
    )
    track = Track(
        artist="Orchid Mantis",
        title="blank slate",
        album="album",
        duration_ms=None,
        art_uri="https://i.scdn.co/image/abc123",
    )

    assert resolver.resolve(track) is None
