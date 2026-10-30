import pytest

from wiim_lastfm.models import Track
from wiim_lastfm.nts import (
    Mixtape,
    NtsResolver,
    lookup_show,
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


@pytest.mark.parametrize("host", ["PAM & CHRIS KONTOS", "SPIRIT BLUE"])
def test_early_bird_show_with_local_airplay_art(host):
    resolver = NtsResolver(fetch_catalog=catalog_of(), fetch_now_playing=unreachable_stream, find_show=lambda title: True)
    track = Track(
        artist="Sakurai Keisuke - Tane O Maku",
        title=f"THE EARLY BIRD SHOW W/ {host}",
        album="unknow",
        duration_ms=7_252_000,
        art_uri="https://192.168.1.97/data/AirplayArtWorkData.jpeg",
    )

    assert resolver.resolve(track) == Track("Sakurai Keisuke", "Tane O Maku", None, None)


def test_early_bird_show_broadcast_date_is_not_a_song():
    resolver = NtsResolver(fetch_catalog=catalog_of(), fetch_now_playing=unreachable_stream, find_show=lambda title: True)
    track = Track("28 Oct 2026", "THE EARLY BIRD SHOW W/ SPIRIT BLUE", None, 7_200_000)

    assert resolver.resolve(track).artist == ""


def test_other_radio_show_is_not_assumed_to_be_nts():
    resolver = NtsResolver(fetch_catalog=catalog_of(), fetch_now_playing=unreachable_stream, find_show=lambda title: False)
    track = Track("Artist - Song", "ANOTHER SHOW W/ SOMEONE", None, 7_200_000)

    assert resolver.resolve(track) is None


def local_airplay_track(title, artist="L’Rain - Elmyra"):
    return Track(artist, title, None, 3_580_000,
                 "https://192.168.1.97/data/AirplayArtWorkData.jpeg")


@pytest.mark.parametrize("title", [
    "ASTRAL GARDEN W/ NAILAH HUNTER", "THE EARLY BIRD SHOW W/ PAM & CHRIS KONTOS",
    "SOUP TO NUTS", "A new show without a host marker", "Special: Guest Session 42",
])
def test_any_catalogued_show_title_is_supported(title):
    queried = []
    def find_show(value):
        queried.append(value)
        return True
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=find_show)

    assert resolver.resolve(local_airplay_track(title)) == Track("L’Rain", "Elmyra", None, None)
    assert queried == [title]


@pytest.mark.parametrize("kind", ["show", "episode"])
def test_lookup_matches_only_full_show_or_episode_title(monkeypatch, kind):
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [
                {"article_type": "show", "title": "Unrelated result"},
                {"article_type": kind, "title": "Astral Garden w/ Nailah Hunter"},
            ]}
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr("wiim_lastfm.nts.requests.get", get)

    assert lookup_show("ASTRAL GARDEN W/ NAILAH HUNTER") is True
    assert calls[0][1]["params"]["version"] == 2
    assert calls[0][1]["params"]["types[]"] == ["show", "episode"]


@pytest.mark.parametrize("item", [
    {"article_type": "show", "title": "Astral Garden w/ Someone Else"},
    {"article_type": "artist", "title": "Astral Garden w/ Nailah Hunter"},
    {"article_type": "track", "title": "Astral Garden w/ Nailah Hunter"},
    None,
])
def test_lookup_rejects_loose_matches_and_non_shows(monkeypatch, item):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"results": [item]}
    monkeypatch.setattr("wiim_lastfm.nts.requests.get", lambda *a, **k: Response())

    assert lookup_show("ASTRAL GARDEN W/ NAILAH HUNTER") is False


def test_lookup_normalises_html_unicode_and_whitespace(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"article_type": "episode", "title": "Someone’s Show &amp; Guests"}]}
    monkeypatch.setattr("wiim_lastfm.nts.requests.get", lambda *a, **k: Response())

    assert lookup_show("  SOMEONE'S   SHOW & GUESTS  ") is True


def test_known_shows_survive_restart_and_outage(tmp_path):
    path = tmp_path / "nts-shows.json"
    calls = []
    def find_show(title):
        calls.append(title)
        return True
    track = local_airplay_track("Astral Garden w/ Nailah Hunter")
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=find_show, show_cache_path=path)
    resolver.resolve(track)
    resolver.resolve(local_airplay_track(track.title, "June McDoom - Without You"))
    assert calls == [track.title]

    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=unreachable_stream, show_cache_path=path)
    assert resolver.resolve(track).title == "Elmyra"


def test_lookup_outage_skips_bad_metadata_and_retries():
    now = [1_000]
    calls = []
    def find_show(title):
        calls.append(title)
        if len(calls) == 1: raise ConnectionError("offline")
        return True
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=find_show, clock=lambda: now[0])
    track = local_airplay_track("Astral Garden w/ Nailah Hunter")
    assert resolver.resolve(track).artist == ""
    now[0] += 20
    assert resolver.resolve(track).artist == ""
    assert len(calls) == 1
    now[0] += 41
    assert resolver.resolve(track).artist == "L’Rain"
    assert len(calls) == 2


def test_newly_indexed_episode_recovers_after_negative_cache_expires():
    now = [1_000]
    found = [False]
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=lambda title: found[0], clock=lambda: now[0])
    track = local_airplay_track("A brand new episode")
    assert resolver.resolve(track) is None
    found[0] = True
    now[0] += 301
    assert resolver.resolve(track).artist == "L’Rain"


def test_normal_music_with_hyphenated_artist_and_album_is_untouched():
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=unreachable_stream)
    track = Track("Artist - Alias", "Song", "Album", 250_000)
    assert resolver.resolve(track) is None


def test_non_nts_airplay_is_untouched():
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=lambda title: False)
    assert resolver.resolve(local_airplay_track("A regular song", "Artist")) is None


@pytest.mark.parametrize("artist", ["26 Oct 2026", "", "unknow", "Nailah Hunter"])
def test_confirmed_show_without_individual_song_is_skipped(artist):
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=lambda title: True)
    assert resolver.resolve(local_airplay_track("Astral Garden w/ Nailah Hunter", artist)).artist == ""


def test_corrupt_show_cache_recovers(tmp_path):
    path = tmp_path / "nts-shows.json"
    path.write_text("invalid json", encoding="utf-8")
    resolver = NtsResolver(fetch_catalog=catalog_of(), find_show=lambda title: True, show_cache_path=path)
    assert resolver.resolve(local_airplay_track("Any show")).title == "Elmyra"
