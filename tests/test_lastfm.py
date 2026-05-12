from wiim_lastfm.lastfm import LastFmClient


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
