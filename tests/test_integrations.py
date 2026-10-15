import httpx
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_proxmint import ProxmintFetchTool, ProxmintLoader
from langchain_proxmint._gateway import Credentials

CREDS = Credentials("login", "secret")


def fake_client(seen: list):
    """Stands in for the gateway: records the proxy username and answers with a small page."""

    def make(self, creds, username):
        seen.append(username)

        def handler(req):
            if "fail" in req.url.host:
                return httpx.Response(407, extensions={"reason_phrase": b"TRAFFIC_EXHAUSTED"})
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=f"<title>Page {req.url.host}</title><p>Hello from {req.url.host}</p>",
            )

        return httpx.Client(transport=httpx.MockTransport(handler))

    return make


def test_tool_targeting_and_output(monkeypatch):
    seen: list = []
    monkeypatch.setattr(ProxmintFetchTool, "_client", fake_client(seen))
    tool = ProxmintFetchTool(country="us", city="New York", session_minutes=10)
    tool._creds = CREDS

    out = tool.invoke({"url": "https://a.example/"})
    assert out.startswith("URL: https://a.example/\nStatus: 200\nTitle: Page a.example\n\n")
    assert out.endswith("Hello from a.example")
    tool.invoke({"url": "https://a.example/", "country": "de"})
    # Same session id on both calls; naming another country drops the default city.
    sid = seen[0].split("sessid.")[1].split(";")[0]
    assert seen == [
        f"login__cr.us;city.newyork;sessid.{sid};sessttl.10",
        f"login__cr.de;sessid.{sid};sessttl.10",
    ]


def test_tool_reports_gateway_errors(monkeypatch):
    monkeypatch.setattr(ProxmintFetchTool, "_client", fake_client([]))
    tool = ProxmintFetchTool()
    tool._creds = CREDS
    assert "bandwidth is used up" in tool.invoke({"url": "http://fail.example/"})


def test_loader(monkeypatch):
    seen: list = []
    monkeypatch.setattr(ProxmintLoader, "_client", fake_client(seen))
    monkeypatch.setattr("langchain_proxmint.document_loaders.load_credentials", lambda *a, **k: CREDS)
    docs = ProxmintLoader(["https://a.example/", "http://fail.example/", "https://b.example/"], country="gb").load()
    assert [d.page_content for d in docs] == ["Hello from a.example", "Hello from b.example"]
    assert docs[0].metadata["title"] == "Page a.example" and docs[0].metadata["country"] == "gb"
    assert seen == ["login__cr.gb"]


class TestProxmintFetchToolStandard(ToolsUnitTests):
    @property
    def tool_constructor(self):
        return ProxmintFetchTool

    @property
    def tool_constructor_params(self) -> dict:
        return {"api_key": "pmk_test"}

    @property
    def tool_invoke_params_example(self) -> dict:
        return {"url": "https://example.com", "country": "us"}
