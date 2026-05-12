from wiim_lastfm.upnp import (
    PlayQueueClient,
    build_playqueue_action_body,
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
