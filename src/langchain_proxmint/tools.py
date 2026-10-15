"""ProxmintFetchTool: an agent tool that reads web pages through Proxmint proxies."""

from __future__ import annotations

from typing import Literal

import httpx
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field, PrivateAttr, SecretStr

from langchain_proxmint._gateway import (
    Credentials,
    GatewayError,
    client_for,
    fetch,
    load_credentials,
    new_session_id,
    proxy_username,
)


class ProxmintFetchInput(BaseModel):
    url: str = Field(description="The http or https URL of the page to read.")
    country: str | None = Field(
        default=None,
        description="Two-letter country code for the exit IP, for example 'us' or 'de'. Leave empty for any country.",
    )


class ProxmintFetchTool(BaseTool):
    """Fetch a web page through Proxmint residential, datacenter or mobile proxies.

    Setup:
        ``pip install langchain-proxmint`` and set ``PROXMINT_API_KEY`` (Settings in the
        Proxmint dashboard), or ``PROXMINT_USERNAME`` and ``PROXMINT_PASSWORD``.

    Instantiate:
        .. code-block:: python

            from langchain_proxmint import ProxmintFetchTool

            tool = ProxmintFetchTool(product="residential", country="us")

    Invoke:
        .. code-block:: python

            tool.invoke({"url": "https://example.com", "country": "de"})
    """

    name: str = "proxmint_fetch"
    description: str = (
        "Read a web page through a proxy, so the request comes from a residential, datacenter or mobile IP, "
        "optionally in a chosen country. Returns the final URL, HTTP status, title and the page as readable text. "
        "Use it for pages that block cloud servers or show different content in different countries."
    )
    args_schema: type[BaseModel] = ProxmintFetchInput
    handle_tool_error: bool = True

    api_key: SecretStr | None = None
    """Proxmint API key. Defaults to ``PROXMINT_API_KEY``."""
    username: str | None = None
    """Proxy username, if you'd rather not use an API key. Defaults to ``PROXMINT_USERNAME``."""
    password: SecretStr | None = None
    """Proxy password. Defaults to ``PROXMINT_PASSWORD``."""
    product: Literal["residential", "premium-residential", "datacenter", "mobile"] = "residential"
    country: str | None = None
    """Default exit country (two-letter code) when a call doesn't name one."""
    state: str | None = None
    city: str | None = None
    zip_code: str | None = None
    asn: str | None = None
    session_minutes: int | None = Field(default=None, ge=1, le=120)
    """Keep one exit IP across calls for this many minutes. Default: a new IP on every call."""
    output: Literal["text", "html"] = "text"
    max_chars: int = 50_000
    timeout: float = 60.0

    _creds: Credentials | None = PrivateAttr(default=None)
    _session_id: str | None = PrivateAttr(default=None)

    def _credentials(self) -> Credentials:
        if self._creds is None:
            self._creds = load_credentials(
                self.api_key.get_secret_value() if self.api_key else None,
                self.product,
                username=self.username,
                password=self.password.get_secret_value() if self.password else None,
            )
        return self._creds

    def _client(self, creds: Credentials, username: str) -> httpx.Client:
        return client_for(creds, username, timeout=self.timeout)

    def _run(
        self,
        url: str,
        country: str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        if self.session_minutes and self._session_id is None:
            self._session_id = new_session_id()
        try:
            creds = self._credentials()
            # A country named in the call replaces the default one, and the finer default targeting with it.
            targeting = (
                {"country": country}
                if country and country.lower() != (self.country or "").lower()
                else {
                    "country": self.country,
                    "state": self.state,
                    "city": self.city,
                    "zip_code": self.zip_code,
                    "asn": self.asn,
                }
            )
            username = proxy_username(
                creds.username,
                **targeting,
                session_id=self._session_id,
                session_minutes=self.session_minutes,
            )
            with self._client(creds, username) as client:
                page = fetch(client, url)
        except (GatewayError, ValueError) as e:
            raise ToolException(str(e)) from e
        except httpx.HTTPError as e:
            raise ToolException(f"Request failed: {e}") from e

        body = page.html if self.output == "html" else page.text()
        if len(body) > self.max_chars:
            body = body[: self.max_chars] + f"\n\n[cut at {self.max_chars:,} characters]"
        head = [f"URL: {page.url}", f"Status: {page.status}"]
        if page.title:
            head.append(f"Title: {page.title}")
        return "\n".join(head) + "\n\n" + body


__all__ = ["ProxmintFetchInput", "ProxmintFetchTool"]
