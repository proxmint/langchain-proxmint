# langchain-proxmint

[LangChain](https://www.langchain.com) integration for [Proxmint](https://proxmint.com) proxies: let an agent
read web pages from residential, datacenter or 4G/5G mobile IPs, or load pages into Documents the same way.
Pick the exit country, state, city, ZIP or ASN, and keep one IP for up to two hours when a site needs it.

- **`ProxmintFetchTool`**: an agent tool. The agent passes a URL and, optionally, a country, and gets back
  the final URL, status, title and the page as readable text.
- **`ProxmintLoader`**: a document loader that fetches a list of URLs into `Document`s.

Requests go straight from your machine to the Proxmint gateway (`gw.proxmint.com`). Nothing else sits in
between, and bandwidth comes out of your own Proxmint account.

## Install

```bash
pip install langchain-proxmint
```

## Credentials

Create an API key under **Settings** in the [Proxmint dashboard](https://proxmint.com/dashboard) and export it:

```bash
export PROXMINT_API_KEY="pmk_..."
```

The key reads the proxy login for the product you choose (`residential` by default). You can pass the proxy
login instead, with `PROXMINT_USERNAME` and `PROXMINT_PASSWORD` or the `username` / `password` arguments.

## Use the tool in an agent

```python
from langchain.agents import create_agent
from langchain_proxmint import ProxmintFetchTool

tool = ProxmintFetchTool(product="residential")

agent = create_agent("anthropic:claude-sonnet-5-5", tools=[tool])
agent.invoke({"messages": [{"role": "user", "content": "What does the front page of example.com say when visited from Germany?"}]})
```

Or call it directly:

```python
print(tool.invoke({"url": "https://example.com", "country": "de"}))
```

Options on `ProxmintFetchTool`:

| Option | Default | What it does |
| --- | --- | --- |
| `product` | `"residential"` | `residential`, `premium-residential`, `datacenter` or `mobile` |
| `country` | any | Default exit country (two-letter code) when a call doesn't name one |
| `state`, `city`, `zip_code`, `asn` | none | Finer targeting; needs `country` |
| `session_minutes` | none | Keep one exit IP across calls for 1 to 120 minutes. Default: a new IP on every call |
| `output` | `"text"` | `"text"` for readable text, `"html"` for the raw page |
| `max_chars` | `50000` | Cut longer pages |
| `timeout` | `60` | Seconds per request |

Gateway refusals (no bandwidth left, no IP matching the targeting, a blocked site) come back to the agent as
a short message saying what to change, instead of an exception.

## Load pages into Documents

```python
from langchain_proxmint import ProxmintLoader

loader = ProxmintLoader(
    ["https://example.com", "https://example.org"],
    country="us",
    city="New York",
    session_minutes=30,  # every page from one IP
)
docs = loader.load()
print(docs[0].metadata)  # source, requested_url, status, title, content_type, country
```

Each URL gets a new IP unless `session_minutes` is set. Failed URLs are logged and skipped; pass
`continue_on_failure=False` to raise instead.

## Good to know

- Web traffic works on destination ports 80, 443, 8080, 8443, 8888 and 8090 ([port access](https://proxmint.com/docs/ports)).
- A short list of sites, mostly banking and government, is refused by the network ([blocked websites](https://proxmint.com/docs/blocked-websites)).
- City, state, ZIP and ASN targeting meter at 2x on residential, datacenter and mobile ([targeting](https://proxmint.com/docs/targeting)).
- Each product allows up to 2,000 concurrent connections.

Full guide: [proxmint.com/docs/langchain](https://proxmint.com/docs/langchain). Pricing: [proxmint.com/pricing](https://proxmint.com/pricing).
Bandwidth is billed per GB and never expires.

## Development

```bash
uv run --group test pytest
```

The tests run offline against a stand-in for the gateway.

## License

MIT
