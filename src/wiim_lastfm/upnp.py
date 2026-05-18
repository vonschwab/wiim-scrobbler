from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

from .models import PlayerStatus, Track

PLAYQUEUE_SERVICE = "urn:schemas-wiimu-com:service:PlayQueue:1"
AVTRANSPORT_SERVICE = "urn:schemas-upnp-org:service:AVTransport:1"


@dataclass(frozen=True)
class SoapRequest:
    url: str
    soap_action: str
    body: str


class PlayQueueClient:
    def __init__(self, host: str, timeout: float = 10.0) -> None:
        self.base_url = upnp_base_url(host)
        self.timeout = timeout

    def build_history_request(self, account_source: str, number: int) -> SoapRequest:
        action = "GetUserAccountHistory"
        return SoapRequest(
            url=f"{self.base_url}/upnp/control/PlayQueue1",
            soap_action=f"{PLAYQUEUE_SERVICE}#{action}",
            body=build_playqueue_action_body(
                action,
                {"AccountSource": account_source, "Number": str(number)},
            ),
        )

    def build_basic_user_info_request(self) -> SoapRequest:
        action = "GetBasicUserInfo"
        return SoapRequest(
            url=f"{self.base_url}/upnp/control/PlayQueue1",
            soap_action=f"{PLAYQUEUE_SERVICE}#{action}",
            body=build_playqueue_action_body(action, {}),
        )

    def get_basic_user_info(self) -> str:
        return self._post(self.build_basic_user_info_request())

    def get_user_account_history(self, account_source: str, number: int) -> str:
        return self._post(self.build_history_request(account_source, number))

    def _post(self, request: SoapRequest) -> str:
        response = requests.post(
            request.url,
            data=request.body.encode("utf-8"),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"{request.soap_action}"',
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"UPnP {response.status_code}: {response.text.strip() or '<empty>'}"
            )
        result = parse_soap_value(response.content, "Result")
        return result or parse_soap_value(response.content, "QueueContext")


class AVTransportClient:
    def __init__(self, host: str, timeout: float = 10.0) -> None:
        self.base_url = upnp_base_url(host)
        self.timeout = timeout

    def build_transport_info_request(self) -> SoapRequest:
        action = "GetTransportInfo"
        return SoapRequest(
            url=f"{self.base_url}/upnp/control/rendertransport1",
            soap_action=f"{AVTRANSPORT_SERVICE}#{action}",
            body=build_avtransport_action_body(action, {"InstanceID": "0"}),
        )

    def build_position_info_request(self) -> SoapRequest:
        action = "GetPositionInfo"
        return SoapRequest(
            url=f"{self.base_url}/upnp/control/rendertransport1",
            soap_action=f"{AVTRANSPORT_SERVICE}#{action}",
            body=build_avtransport_action_body(action, {"InstanceID": "0"}),
        )

    def player_status(self) -> PlayerStatus:
        transport = self._post(self.build_transport_info_request())
        position = self._post(self.build_position_info_request())
        state = parse_soap_value(transport, "CurrentTransportState")
        return PlayerStatus(
            is_playing=state == "PLAYING",
            position_ms=parse_duration_ms(parse_soap_value(position, "RelTime")) or 0,
            duration_ms=parse_duration_ms(parse_soap_value(position, "TrackDuration")),
            mode="upnp",
        )

    def current_track(self, duration_ms: int | None = None) -> Track:
        position = self._post(self.build_position_info_request())
        return parse_didl_track(
            parse_soap_value(position, "TrackMetaData"),
            duration_ms=duration_ms
            or parse_duration_ms(parse_soap_value(position, "TrackDuration")),
        )

    def _post(self, request: SoapRequest) -> bytes:
        response = requests.post(
            request.url,
            data=request.body.encode("utf-8"),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"{request.soap_action}"',
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"UPnP {response.status_code}: {response.text.strip() or '<empty>'}"
            )
        return response.content


def upnp_base_url(host: str) -> str:
    parsed = urlparse(host if "://" in host else f"https://{host}")
    return f"http://{parsed.hostname}:49152"


def build_playqueue_action_body(action: str, arguments: dict[str, str]) -> str:
    return build_soap_action_body(PLAYQUEUE_SERVICE, action, arguments)


def build_avtransport_action_body(action: str, arguments: dict[str, str]) -> str:
    return build_soap_action_body(AVTRANSPORT_SERVICE, action, arguments)


def build_soap_action_body(
    service: str, action: str, arguments: dict[str, str]
) -> str:
    argument_xml = "".join(
        f"<{name}>{escape(value)}</{name}>" for name, value in arguments.items()
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        "<s:Body>"
        f'<u:{action} xmlns:u="{service}">'
        f"{argument_xml}"
        f"</u:{action}>"
        "</s:Body>"
        "</s:Envelope>"
    )


def parse_soap_value(content: bytes, name: str) -> str:
    root = ElementTree.fromstring(content)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == name:
            return element.text or ""
    return ""


def parse_duration_ms(value: str) -> int | None:
    text = (value or "").strip()
    if not text or text in {"NOT_IMPLEMENTED", "00:00:00"}:
        return None
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = parts
        total_seconds = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)
    except ValueError:
        return None
    return total_seconds * 1000


def parse_didl_track(metadata: str, duration_ms: int | None = None) -> Track:
    if not metadata.strip():
        return Track(artist="", title="", album=None, duration_ms=duration_ms)
    try:
        root = ElementTree.fromstring(metadata)
    except ElementTree.ParseError:
        return Track(artist="", title="", album=None, duration_ms=duration_ms)
    return Track(
        artist=_didl_text(root, "artist"),
        title=_didl_text(root, "title"),
        album=_optional_text(_didl_text(root, "album")),
        duration_ms=duration_ms,
    )


def _didl_text(root: ElementTree.Element, name: str) -> str:
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].casefold() == name.casefold():
            return (element.text or "").strip()
    return ""


def _optional_text(value: str) -> str | None:
    text = value.strip()
    return text or None
