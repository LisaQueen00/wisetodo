"""Public static pages only. DNS is checked and the connection pinned per hop."""

import asyncio
import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx
from pydantic import JsonValue

from wisetodo.tools.transport import ToolTransportError

MAX_BYTES = 1_048_576


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.in_title = False
        self.title: list[str] = []
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and not self.hidden and len(self.links) < 20:
            href = dict(attrs).get("href")
            if href and len(href) <= 2048:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.text.append(data)
            if self.in_title:
                self.title.append(data)


def public_url(value: str) -> httpx.URL:
    if len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
        raise ToolTransportError("web_blocked")
    url = httpx.URL(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or url.port not in {None, 80, 443}
    ):
        raise ToolTransportError("web_blocked")
    return url.copy_with(fragment=None)


async def pinned_url(url: httpx.URL) -> httpx.URL:
    addresses = await asyncio.get_running_loop().getaddrinfo(
        url.host,
        url.port or (443 if url.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    ips = [ipaddress.ip_address(row[4][0]) for row in addresses]
    if not ips or any(
        not ip.is_global
        or ip.is_multicast
        or ip.is_reserved
        or (
            isinstance(ip, ipaddress.IPv6Address)
            and (
                ip.ipv4_mapped is not None
                or ip.sixtofour is not None
                or ip.teredo is not None
                or ip in ipaddress.IPv6Network("64:ff9b::/96")
            )
        )
        for ip in ips
    ):
        raise ToolTransportError("web_blocked")
    return url.copy_with(host=str(ips[0]))


async def read_url(arguments: dict[str, JsonValue]) -> JsonValue:
    value = arguments.get("url")
    if set(arguments) != {"url"} or not isinstance(value, str):
        raise ToolTransportError("invalid_tool_arguments")
    try:
        async with asyncio.timeout(20):
            current = public_url(value)
            for _ in range(4):
                pinned = await pinned_url(current)
                # A new client per hop prevents cookie propagation or cross-host pooling.
                async with (
                    httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client,
                    client.stream(
                        "GET",
                        pinned,
                        headers={
                            "Host": current.netloc.decode(),
                            "Accept-Encoding": "identity",
                            "User-Agent": "WiseTodo",
                            "Accept": "text/html,text/plain",
                        },
                        extensions={"sni_hostname": current.host},
                    ) as response,
                ):
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ToolTransportError("web_unavailable")
                        current = public_url(urljoin(str(current), location))
                        continue
                    if response.status_code == 429:
                        raise ToolTransportError("rate_limited")
                    if response.status_code != 200:
                        raise ToolTransportError("web_unavailable")
                    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if kind not in {"text/html", "text/plain", "application/xhtml+xml"}:
                        raise ToolTransportError("web_unsupported")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ToolTransportError("web_unsupported")
                    data = bytearray()
                    async for chunk in response.aiter_raw():
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise ToolTransportError("web_too_large")
                    encoding = response.encoding or "utf-8"
                content = data.decode(encoding, errors="replace")
                page = Page()
                if kind != "text/plain":
                    page.feed(content)
                    content = " ".join(" ".join(page.text).split())
                links: list[JsonValue] = []
                for href in page.links:
                    try:
                        links.append(str(public_url(urljoin(str(current), href))))
                    except (ValueError, httpx.InvalidURL, ToolTransportError):
                        continue
                result: dict[str, JsonValue] = {
                    "url": str(current),
                    "title": " ".join(page.title)[:300],
                    "text": content[:12000],
                    "links": links,
                    "truncated": len(content) > 12000,
                    "untrusted": True,
                }
                while len(json.dumps(result, ensure_ascii=False)) > 15_000:
                    result["truncated"] = True
                    if links:
                        links.pop()
                    else:
                        text = result["text"]
                        assert isinstance(text, str)
                        result["text"] = text[: max(0, len(text) - 1000)]
                return result
            raise ToolTransportError("web_redirect_limit")
    except (httpx.HTTPError, OSError, TimeoutError):
        raise ToolTransportError("web_network_failed") from None
    except (ValueError, LookupError):
        raise ToolTransportError("web_unsupported") from None
