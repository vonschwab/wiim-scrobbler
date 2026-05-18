import requests

from wiim_lastfm.wiim import (
    WiimClient,
    load_json_response,
    parse_player_status,
    parse_track,
    safe_parse_track,
)


def test_parse_track_normalizes_metadata_keys():
    response = {
        "metaData": {
            "album": "Country Heat",
            "title": "Old Dirt Roads",
            "artist": "Owen Riegling",
            "albumArtURI ": "https://example.invalid/art.jpg",
        }
    }

    track = parse_track(response, duration_ms=210_000)

    assert track.artist == "Owen Riegling"
    assert track.title == "Old Dirt Roads"
    assert track.album == "Country Heat"
    assert track.duration_ms == 210_000


def test_parse_track_reads_hex_metadata_from_player_status_fallback():
    response = {
        "Title": "536F6E67",
        "Artist": "417274697374",
        "Album": "416C62756D",
    }

    track = parse_track(response, duration_ms=210_000)

    assert track.artist == "Artist"
    assert track.title == "Song"
    assert track.album == "Album"


def test_parse_player_status_converts_numeric_fields():
    status = parse_player_status(
        {"status": "play", "curpos": "184919", "totlen": "210000", "mode": "32"}
    )

    assert status.is_playing is True
    assert status.position_ms == 184_919
    assert status.duration_ms == 210_000
    assert status.mode == "32"


def test_client_uses_https_base_url_when_scheme_is_provided():
    client = WiimClient("https://192.168.1.97")

    assert client.base_url == "https://192.168.1.97"
    assert client.base_urls == ["https://192.168.1.97", "http://192.168.1.97"]


def test_client_tries_https_then_http_for_plain_host():
    client = WiimClient("192.168.1.97")

    assert client.base_url == "https://192.168.1.97"
    assert client.base_urls == ["https://192.168.1.97", "http://192.168.1.97"]


def test_client_uses_only_explicit_http_base_url():
    client = WiimClient("http://192.168.1.97")

    assert client.base_url == "http://192.168.1.97"
    assert client.base_urls == ["http://192.168.1.97"]


def test_command_falls_back_to_http_when_https_connection_fails(monkeypatch):
    calls = []

    class Response:
        content = b'{"status":"stop","curpos":"0","totlen":"0"}'

        def json(self):
            return {"status": "stop", "curpos": "0", "totlen": "0"}

        def raise_for_status(self):
            return None

    def fake_get(url, params, timeout, verify):
        calls.append(url)
        if url.startswith("https://"):
            raise requests.ConnectionError("connection refused")
        return Response()

    monkeypatch.setattr("wiim_lastfm.wiim.requests.get", fake_get)
    client = WiimClient("https://192.168.1.179")

    assert client.command("getPlayerStatus") == {
        "status": "stop",
        "curpos": "0",
        "totlen": "0",
    }
    assert calls == [
        "https://192.168.1.179/httpapi.asp",
        "http://192.168.1.179/httpapi.asp",
    ]
    assert client.base_url == "http://192.168.1.179"


def test_client_disables_tls_verification_for_self_signed_wiim_certificates():
    client = WiimClient("https://192.168.1.97")

    assert client.verify_tls is False


def test_load_json_response_falls_back_to_utf8_bytes():
    class Response:
        content = b'{"status":"none","curpos":"0","totlen":"0"}'

        def json(self):
            raise ValueError("missing encoding")

    assert load_json_response(Response()) == {
        "status": "none",
        "curpos": "0",
        "totlen": "0",
    }


def test_load_json_response_returns_plain_text_when_body_is_not_json():
    class Response:
        content = b"Failed"

        def json(self):
            raise ValueError("not json")

    assert load_json_response(Response()) == "Failed"


def test_safe_parse_track_returns_empty_track_for_failed_metadata_response():
    track = safe_parse_track("Failed", duration_ms=0)

    assert track.artist == ""
    assert track.title == ""
    assert track.album is None
