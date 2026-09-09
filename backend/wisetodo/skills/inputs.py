"""Conservative input hints, without reading files or inferring user intent."""

import re
from collections.abc import Iterable
from pathlib import PureWindowsPath
from urllib.parse import urlsplit

from wisetodo.sessions.models import Message


def input_types(messages: Iterable[Message]) -> tuple[str, ...]:
    kinds: set[str] = set()
    for message in messages:
        if message.role != "user":
            continue
        if message.content.strip():
            kinds.add("text")
        references = [*message.attachments, *re.findall(r"https?://[^\s<>]+", message.content)]
        for reference in references:
            try:
                url = urlsplit(reference)
                if url.scheme in {"http", "https"} and url.hostname:
                    kinds.add("url")
                    if (
                        url.hostname.lower() == "github.com"
                        and len([part for part in url.path.split("/") if part]) >= 2
                    ):
                        kinds.add("github_url")
                    continue
            except ValueError:
                continue
            suffix = PureWindowsPath(reference).suffix.lower()
            if suffix in {".pdf", ".md", ".markdown", ".txt"}:
                kinds.add(
                    {
                        ".pdf": "pdf",
                        ".md": "markdown",
                        ".markdown": "markdown",
                        ".txt": "text_file",
                    }[suffix]
                )
    return tuple(sorted(kinds))
