from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests


PLAYQUEUE_SERVICE = "urn:schemas-wiimu-com:service:PlayQueue:1"


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


def upnp_base_url(host: str) -> str:
    parsed = urlparse(host if "://" in host else f"https://{host}")
    return f"http://{parsed.hostname}:49152"


def build_playqueue_action_body(action: str, arguments: dict[str, str]) -> str:
    argument_xml = "".join(
        f"<{name}>{escape(value)}</{name}>" for name, value in arguments.items()
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        "<s:Body>"
        f'<u:{action} xmlns:u="{PLAYQUEUE_SERVICE}">'
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
