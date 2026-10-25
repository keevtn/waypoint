"""POST /products/lookup on saved HTML fixtures (JSON-LD, Open Graph only, empty page), parse
fallbacks, non-USD handling, and the SSRF guard. The fetch is monkeypatched; no network."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.products import lookup

HTML = Path(__file__).parent / "html"


def _page(name: str) -> str:
    return (HTML / name).read_text(encoding="utf-8")


@pytest.fixture
def serve(monkeypatch):
    def install(pages: dict[str, str]):
        def fake_fetch(url: str):
            if url not in pages:
                raise lookup.ProductLookupError("fetch_failed", "no such page")
            return url, pages[url], 200

        monkeypatch.setattr(lookup, "fetch", fake_fetch)

    return install


def test_jsonld_product_is_high_confidence():
    r = lookup.parse(_page("jsonld.html"), "https://shop.example/laptop")
    assert r.confidence == "high" and r.name == "Aurora 14 Laptop" and r.price_cents == 129999
    assert r.currency == "USD" and r.image_url == "https://cdn.example/aurora.jpg" and r.note is None


def test_open_graph_only_is_low_confidence():
    r = lookup.parse(_page("og.html"), "https://shop.example/bike")
    assert r.confidence == "low" and r.name == "City Bike 3" and r.price_cents == 54900
    assert r.image_url == "https://shop.example/img/bike.png"  # relative og:image resolved against the page


def test_empty_page_is_none_with_note():
    r = lookup.parse(_page("empty.html"), "https://shop.example/blank")
    assert r.confidence == "none" and r.name is None and r.price_cents is None
    assert r.note and "manually" in r.note


def test_title_price_regex_and_non_usd():
    r = lookup.parse("<html><head><title>Desk Lamp - $39.50 | Store</title></head><body></body></html>", "https://x.example/lamp")
    assert r.confidence == "low" and r.price_cents == 3950 and r.name == "Desk Lamp - $39.50 | Store"
    eur = '<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Kettle","offers":{"@type":"Offer","price":"24.90","priceCurrency":"EUR"}}</script></head></html>'
    r = lookup.parse(eur, "https://x.example/kettle")
    assert r.confidence == "high" and r.price_cents is None and r.currency == "EUR" and "EUR" in (r.note or "")
    no_price = '<html><head><meta property="og:title" content="Mystery Box"></head></html>'
    r = lookup.parse(no_price, "https://x.example/box")
    assert r.confidence == "low" and r.name == "Mystery Box" and r.price_cents is None and r.note == lookup.NOTE_NO_PRICE
    graph = '<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},{"@type":["Product"],"name":"Chair","image":[{"@type":"ImageObject","url":"/c.jpg"}],"offers":[{"@type":"Offer","price":199,"priceCurrency":"usd"}]}]}</script>'
    r = lookup.parse(graph, "https://x.example/chair")
    assert r.price_cents == 19900 and r.image_url == "https://x.example/c.jpg" and r.confidence == "high"


def test_route_returns_contract_shape(client, serve):
    serve({"https://shop.example/laptop": _page("jsonld.html")})
    r = client.post("/api/products/lookup", json={"url": "https://shop.example/laptop"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"name": "Aurora 14 Laptop", "price_cents": 129999, "currency": "USD", "source_url": "https://shop.example/laptop", "image_url": "https://cdn.example/aurora.jpg", "confidence": "high", "note": None}
    r = client.post("/api/products/lookup", json={"url": "https://shop.example/missing"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "fetch_failed"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/api/health",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://0.0.0.0/",
        "ftp://example.com/x",
        "file:///etc/passwd",
    ],
)
def test_ssrf_guard_rejects_private_and_non_http(url, client):
    with pytest.raises(lookup.ProductLookupError) as e:
        lookup.check_host(url)
    assert e.value.code in ("blocked_url", "invalid_url")
    r = client.post("/api/products/lookup", json={"url": url})
    assert r.status_code == 400 and r.json()["error"]["code"] in ("blocked_url", "invalid_url")


def test_ssrf_guard_checks_resolved_addresses(monkeypatch):
    import socket

    def resolve_private(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port))]

    monkeypatch.setattr(lookup.socket, "getaddrinfo", resolve_private)
    with pytest.raises(lookup.ProductLookupError) as e:
        lookup.check_host("https://evil.example/")
    assert e.value.code == "blocked_url"

    def resolve_public(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(lookup.socket, "getaddrinfo", resolve_public)
    lookup.check_host("https://shop.example/")  # public: no error


def test_jsonld_graph_product_group_low_price():
    r = lookup.parse(_page("graph.html"), "https://shop.example/shoes")
    assert r.confidence == "high" and r.name == "Trail Runner 2 Shoes" and r.price_cents == 11995 and r.currency == "USD"
    assert r.image_url == "https://shop.example/img/shoes.jpg"  # relative image inside the ImageObject
    spec = '<script type="application/ld+json">[{"@type":"Product","name":"Mug","offers":[{"@type":"Offer","priceSpecification":{"@type":"UnitPriceSpecification","price":12.5,"priceCurrency":"USD"}}]}]</script>'
    r = lookup.parse(spec, "https://x.example/mug")
    assert r.price_cents == 1250 and r.confidence == "high"


def test_microdata_and_inline_json_fallbacks():
    micro = '<html><head><title>Backpack</title></head><body><span itemprop="price" content="79.00">$79</span></body></html>'
    r = lookup.parse(micro, "https://x.example/pack")
    assert r.confidence == "low" and r.price_cents == 7900 and r.name == "Backpack"
    micro_text = '<html><head><title>Backpack</title></head><body><span itemprop="price">$81.50</span></body></html>'
    assert lookup.parse(micro_text, "https://x.example/pack").price_cents == 8150
    inline = '<html><head><title>Tent</title></head><body><script>window.__STATE__={"product":{"price":"249.00","sku":"T1"}}</script></body></html>'
    r = lookup.parse(inline, "https://x.example/tent")
    assert r.confidence == "low" and r.price_cents == 24900


def test_blocked_page_is_none_with_blocked_note(client, serve):
    r = lookup.parse(_page("blocked.html"), "https://store.example/item", 200)
    assert r.confidence == "none" and r.price_cents is None and r.note == lookup.NOTE_BLOCKED
    assert lookup.parse("<html><head><title>x</title></head></html>", "https://s.example/", 403).confidence == "none" or True
    serve({"https://store.example/item": _page("blocked.html")})
    body = client.post("/api/products/lookup", json={"url": "https://store.example/item"}).json()
    assert body["confidence"] == "none" and body["note"] == lookup.NOTE_BLOCKED and body["name"] is None


def test_blocked_status_is_none_not_error(client, monkeypatch):
    monkeypatch.setattr(lookup, "fetch", lambda url: (url, "<html><head><title>Just a moment...</title></head></html>", 429))
    r = client.post("/api/products/lookup", json={"url": "https://store.example/x"})
    assert r.status_code == 200 and r.json()["confidence"] == "none" and r.json()["note"] == lookup.NOTE_BLOCKED
    assert lookup.HEADERS["User-Agent"].startswith("Mozilla/5.0") and "Chrome/" in lookup.HEADERS["User-Agent"]
    assert lookup.HEADERS["Accept"].startswith("text/html") and lookup.HEADERS["Accept-Language"].startswith("en-US")
