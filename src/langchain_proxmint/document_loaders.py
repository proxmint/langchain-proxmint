"""ProxmintLoader: load web pages into Documents through Proxmint proxies."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Literal

import httpx
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from langchain_proxmint._gateway import (
    GatewayError,
    client_for,
    fetch,
    load_credentials,
    new_session_id,
    proxy_username,
)

logger = logging.getLogger(__name__)


class ProxmintLoader(BaseLoader):
    """Load web pages through Proxmint residential, datacenter or mobile proxies.

    Every URL gets a new exit IP unless ``session_minutes`` is set, in which case the
    whole run leaves from one IP (useful when the pages belong to one browsing session).

    .. code-block:: python

        from langchain_proxmint import ProxmintLoader

        loader = ProxmintLoader(["https://example.com", "https://example.org"], country="gb")
        docs = loader.load()
    """

    def __init__(
        self,
        urls: str | Sequence[str],
        *,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        product: Literal["residential", "premium-residential", "datacenter", "mobile"] = "residential",
        country: str | None = None,
        state: str | None = None,
        city: str | None = None,
        zip_code: str | None = None,
        asn: str | None = None,
        session_minutes: int | None = None,
        output: Literal["text", "html"] = "text",
        timeout: float = 60.0,
        headers: dict[str, str] | None = None,
        continue_on_failure: bool = True,
    ) -> None:
        self.urls = [urls] if isinstance(urls, str) else list(urls)
        self.api_key = api_key
        self.username = username
        self.password = password
        self.product = product
        self.targeting = {"country": country, "state": state, "city": city, "zip_code": zip_code, "asn": asn}
        self.session_minutes = session_minutes
        self.output = output
        self.timeout = timeout
        self.headers = headers
        self.continue_on_failure = continue_on_failure

    def _client(self, creds, username: str) -> httpx.Client:
        return client_for(creds, username, timeout=self.timeout, headers=self.headers)

    def lazy_load(self) -> Iterator[Document]:
        creds = load_credentials(self.api_key, self.product, username=self.username, password=self.password)
        username = proxy_username(
            creds.username,
            **self.targeting,
            session_id=new_session_id() if self.session_minutes else None,
            session_minutes=self.session_minutes,
        )
        with self._client(creds, username) as client:
            for url in self.urls:
                try:
                    page = fetch(client, url)
                except (GatewayError, httpx.HTTPError) as e:
                    if not self.continue_on_failure:
                        raise
                    logger.warning("Skipped %s: %s", url, e)
                    continue
                yield Document(
                    page_content=page.html if self.output == "html" else page.text(),
                    metadata={
                        "source": page.url,
                        "requested_url": url,
                        "status": page.status,
                        "title": page.title,
                        "content_type": page.content_type,
                        "country": self.targeting["country"],
                    },
                )
