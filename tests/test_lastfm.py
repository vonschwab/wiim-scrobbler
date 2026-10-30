from wiim_lastfm.lastfm import LastFmClient
from wiim_lastfm.models import Track
import pytest


def test_lastfm_signature_sorts_params_and_appends_secret():
    client = LastFmClient(api_key="key", shared_secret="secret", session_key="session")

    signature = client.sign(
        {
            "track": "Song",
            "artist": "Artist",
            "method": "track.scrobble",
            "api_key": "key",
        }
    )

    assert signature == "4e0f2741023e48344b86bb8b332dd5a3"


def test_auth_url_contains_api_key_and_token():
    client = LastFmClient(api_key="key", shared_secret="secret")

    assert client.auth_url("token") == (
        "https://www.last.fm/api/auth/?api_key=key&token=token"
    )


def test_has_recent_scrobble_detects_matching_external_track(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "recenttracks": {
                    "track": [
                        {
                            "artist": {"#text": "Duster"},
                            "name": "The Motion Picture",
                            "date": {"uts": "1030"},
                        }
                    ]
                }
            }

    monkeypatch.setattr(
        "wiim_lastfm.lastfm.requests.get", lambda *args, **kwargs: Response()
    )
    client = LastFmClient(
        api_key="key",
        shared_secret="secret",
        username="vonschwab",
    )

    assert (
        client.has_recent_scrobble(
            Track(" duster ", "THE MOTION PICTURE", "Different Album", 240_000),
            started_at=1_000,
        )
        is True
    )


def history_client(monkeypatch, tracks):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"recenttracks": {"track": tracks}}
    monkeypatch.setattr("wiim_lastfm.lastfm.requests.get", lambda *a, **k: Response())
    return LastFmClient("key", "secret", username="listener")


def history_track(artist, title, timestamp, nowplaying=False):
    return {"artist": {"#text": artist}, "name": title, "date": {"uts": str(timestamp)},
            "@attr": {"nowplaying": "true" if nowplaying else "false"}}


def test_current_now_playing_is_not_a_completed_duplicate(monkeypatch):
    client = history_client(monkeypatch, [
        history_track("Artist", "Song", 1_000, nowplaying=True),
        history_track("Artist", "Other", 900),
    ])
    assert not client.has_recent_scrobble(Track("Artist", "Song", None, None), 1_000)
    assert client.latest_scrobble[0].title == "Other"


def test_intervening_track_allows_song_again_outside_time_window(monkeypatch):
    client = history_client(monkeypatch, [
        history_track("Artist", "Other", 2_000), history_track("Artist", "Song", 1_000),
    ])
    assert not client.has_recent_scrobble(Track("Artist", "Song", None, None), 3_000)


def test_history_check_fails_closed_without_username():
    with pytest.raises(ValueError, match="username"):
        LastFmClient("key", "secret").has_recent_scrobble(Track("A", "B", None, None), 1_000)


def test_corrections_are_used_for_deduplication_only(monkeypatch):
    client = history_client(monkeypatch, [history_track("The Durutti Column", "Tomorrow", 1_000)])
    params = []
    def post(value, **kwargs):
        params.append(value)
        return {"nowplaying": {"artist": {"#text": "The Durutti Column"}, "track": {"#text": "Tomorrow"}}}
    monkeypatch.setattr(client, "_signed_post", post)
    raw = Track("Durruti Column", "Tomorrow", None, None)
    client.update_now_playing(raw)
    assert client.has_recent_scrobble(raw, 2_000)
    assert params[0]["artist"] == "Durruti Column"


def test_scrobble_requires_accepted_response(monkeypatch):
    client = LastFmClient("key", "secret", session_key="session")
    monkeypatch.setattr(client, "_signed_post", lambda *a, **k: {"scrobbles": {"@attr": {"accepted": "0", "ignored": "1"}}})
    with pytest.raises(RuntimeError, match="accepted"):
        client.scrobble(Track("Artist", "Song", None, None), 1_000)


def test_scrobble_returns_confirmed_canonical_identity(monkeypatch):
    client = LastFmClient("key", "secret", session_key="session")
    monkeypatch.setattr(client, "_signed_post", lambda *a, **k: {
        "scrobbles": {"@attr": {"accepted": "1"}, "scrobble": {
            "artist": {"#text": "The Durutti Column"}, "track": {"#text": "Tomorrow"}}}})
    assert client.scrobble(Track("Durruti Column", "Tomorrow", None, None), 1_000).artist == "The Durutti Column"


def test_last_completed_track_is_duplicate_even_outside_window(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "recenttracks": {
                    "track": {
                        "artist": {"#text": "Duster"},
                        "name": "The Motion Picture",
                        "date": {"uts": "2000"},
                    }
                }
            }

    monkeypatch.setattr(
        "wiim_lastfm.lastfm.requests.get", lambda *args, **kwargs: Response()
    )
    client = LastFmClient(
        api_key="key",
        shared_secret="secret",
        username="vonschwab",
    )

    assert (
        client.has_recent_scrobble(
            Track("Duster", "The Motion Picture", None, 240_000),
            started_at=1_000,
            window_seconds=300,
        )
        is True
    )
