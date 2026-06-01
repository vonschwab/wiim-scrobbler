from wiim_lastfm.lastfm import LastFmClient
from wiim_lastfm.models import Track


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


def test_has_recent_scrobble_ignores_track_outside_window(monkeypatch):
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
        is False
    )
