from wiim_lastfm.upnp import (
    AVTransportClient,
    PlayQueueClient,
    build_avtransport_action_body,
    build_playqueue_action_body,
    parse_didl_track,
    parse_duration_ms,
    parse_soap_value,
    upnp_base_url,
)


def test_upnp_base_url_uses_http_port_49152_for_https_device_url():
    assert upnp_base_url("https://192.168.1.97") == "http://192.168.1.97:49152"


def test_build_playqueue_action_body_contains_arguments():
    body = build_playqueue_action_body(
        "GetUserAccountHistory", {"AccountSource": "tidal", "Number": "10"}
    )

    assert "<u:GetUserAccountHistory" in body
    assert "<AccountSource>tidal</AccountSource>" in body
    assert "<Number>10</Number>" in body


def test_parse_soap_value_extracts_result_text():
    response = b"""<?xml version="1.0"?>
    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
      <s:Body>
        <u:GetUserAccountHistoryResponse xmlns:u="urn:schemas-wiimu-com:service:PlayQueue:1">
          <Result>{&quot;items&quot;:[]}</Result>
        </u:GetUserAccountHistoryResponse>
      </s:Body>
    </s:Envelope>"""

    assert parse_soap_value(response, "Result") == '{"items":[]}'


def test_history_builds_get_user_account_history_request():
    client = PlayQueueClient("https://192.168.1.97")

    request = client.build_history_request("tidal", 5)

    assert request.url == "http://192.168.1.97:49152/upnp/control/PlayQueue1"
    assert request.soap_action.endswith("#GetUserAccountHistory")
    assert "<AccountSource>tidal</AccountSource>" in request.body
    assert "<Number>5</Number>" in request.body


def test_basic_user_info_builds_get_basic_user_info_request():
    client = PlayQueueClient("https://192.168.1.97")

    request = client.build_basic_user_info_request()

    assert request.url == "http://192.168.1.97:49152/upnp/control/PlayQueue1"
    assert request.soap_action.endswith("#GetBasicUserInfo")
    assert "<u:GetBasicUserInfo" in request.body


def test_build_playqueue_action_body_wraps_request_without_soap_encoding_style():
    body = build_playqueue_action_body("GetBasicUserInfo", {})

    assert "encodingStyle" not in body


def test_avtransport_builds_get_position_info_request():
    client = AVTransportClient("https://192.168.1.179")

    request = client.build_position_info_request()

    assert request.url == "http://192.168.1.179:49152/upnp/control/rendertransport1"
    assert request.soap_action.endswith("#GetPositionInfo")
    assert "<InstanceID>0</InstanceID>" in request.body


def test_parse_duration_ms_reads_hms_values():
    assert parse_duration_ms("00:03:42") == 222_000


def test_parse_didl_track_reads_title_artist_and_album():
    metadata = """<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
      xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">
      <item>
        <dc:title>Shadow Bloom</dc:title>
        <upnp:artist>Florist</upnp:artist>
        <upnp:album>Jellywish</upnp:album>
      </item>
    </DIDL-Lite>"""

    track = parse_didl_track(metadata, duration_ms=222_000)

    assert track.artist == "Florist"
    assert track.title == "Shadow Bloom"
    assert track.album == "Jellywish"
    assert track.duration_ms == 222_000


def test_avtransport_parses_player_status_and_current_track(monkeypatch):
    responses = {
        "GetTransportInfo": b"""<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
          <s:Body><u:GetTransportInfoResponse xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
          <CurrentTransportState>PLAYING</CurrentTransportState>
          </u:GetTransportInfoResponse></s:Body></s:Envelope>""",
        "GetPositionInfo": b"""<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
          <s:Body><u:GetPositionInfoResponse xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
          <TrackDuration>00:03:42</TrackDuration>
          <RelTime>00:01:12</RelTime>
          <TrackMetaData>&lt;DIDL-Lite xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot; xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot;&gt;&lt;item&gt;&lt;dc:title&gt;Shadow Bloom&lt;/dc:title&gt;&lt;upnp:artist&gt;Florist&lt;/upnp:artist&gt;&lt;upnp:album&gt;Jellywish&lt;/upnp:album&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;</TrackMetaData>
          </u:GetPositionInfoResponse></s:Body></s:Envelope>""",
    }

    class Response:
        status_code = 200
        text = ""

        def __init__(self, content):
            self.content = content

    def fake_post(url, data, headers, timeout):
        action = headers["SOAPAction"].rsplit("#", 1)[1].strip('"')
        return Response(responses[action])

    monkeypatch.setattr("wiim_lastfm.upnp.requests.post", fake_post)
    client = AVTransportClient("https://192.168.1.179")

    status = client.player_status()
    track = client.current_track(duration_ms=status.duration_ms)

    assert status.is_playing is True
    assert status.position_ms == 72_000
    assert status.duration_ms == 222_000
    assert status.mode == "upnp"
    assert track.artist == "Florist"
    assert track.title == "Shadow Bloom"
