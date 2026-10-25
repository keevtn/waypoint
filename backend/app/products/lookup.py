"""POST /products/lookup: read a product page server-side and pull name / price / image.

Fetch: http(s) only, 6 s timeout, 1 MB body cap, at most 3 redirects, and an SSRF guard that
resolves every hop's host and rejects private, loopback, link-local, multicast and reserved
addresses (`check_host`). Parse order: JSON-LD `@type: Product` (confidence "high"), then Open
Graph `og:title` / `product:price:amount` / `og:image` (confidence "low"), then `<title>` with a
price regex ("low"). Nothing parsed -> confidence "none" with a note. Non-USD prices return the
currency with `price_cents` null. No LLM involved; numbers come straight from the page.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from ..models import ProductLookupResponse

TIMEOUT_S = 6.0
MAX_BYTES = 1024 * 1024
MAX_REDIRECTS = 3
NOTE_NO_PRICE = "Couldn't read a price from this page; enter it manually."
NOTE_NOT_USD = "This page lists the price in {cur}; enter the USD amount manually."
NOTE_NOTHING = "Couldn't read this page; enter the name and price manually."


class ProductLookupError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# -- SSRF guard -------------------------------------------------------------------------


def _blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def check_host(url: str) -> None:
    """Raise ProductLookupError unless `url` is http(s) to a public address (every resolved address must be public)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ProductLookupError("invalid_url", "Only http and https links are supported")
    host = parts.hostname
    if not host:
        raise ProductLookupError("invalid_url", "The link has no host")
    if host.lower() in ("localhost",) or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        raise ProductLookupError("blocked_url", "That address is not reachable from here")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        addrs = [ip]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            raise ProductLookupError("unreachable", "Could not resolve that host") from None
        addrs = [ipaddress.ip_address(i[4][0]) for i in infos]
    if not addrs or any(_blocked(a) for a in addrs):
        raise ProductLookupError("blocked_url", "That address is not reachable from here")


# -- fetch ------------------------------------------------------------------------------


def fetch(url: str) -> tuple[str, str]:
    """(final_url, html text) following up to MAX_REDIRECTS hops, guarding each hop."""
    current = url
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0 (compatible; WaypointLookup/1.0)", "Accept": "text/html,application/xhtml+xml"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            check_host(current)
            try:
                with client.stream("GET", current) as r:
                    if r.is_redirect:
                        loc = r.headers.get("location")
                        if not loc:
                            raise ProductLookupError("fetch_failed", "Redirect without a location")
                        current = urljoin(current, loc)
                        continue
                    if r.status_code >= 400:
                        raise ProductLookupError("fetch_failed", f"The page returned HTTP {r.status_code}")
                    ctype = r.headers.get("content-type", "")
                    if ctype and "html" not in ctype and "xml" not in ctype:
                        raise ProductLookupError("fetch_failed", "That link is not a web page")
                    buf = bytearray()
                    for chunk in r.iter_bytes():
                        buf.extend(chunk)
                        if len(buf) > MAX_BYTES:
                            break
                    enc = r.encoding or "utf-8"
                    try:
                        text = bytes(buf[:MAX_BYTES]).decode(enc, errors="replace")
                    except LookupError:  # unknown codec name (builtin)
                        text = bytes(buf[:MAX_BYTES]).decode("utf-8", errors="replace")
                    return current, text
            except httpx.TimeoutException:
                raise ProductLookupError("fetch_failed", "The page took too long to respond") from None
            except httpx.HTTPError as e:
                raise ProductLookupError("fetch_failed", f"Could not fetch the page: {e.__class__.__name__}") from None
    raise ProductLookupError("fetch_failed", "Too many redirects")


# -- parse ------------------------------------------------------------------------------


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_ld = False
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").lower().strip() == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_ld and self.jsonld:
            self.jsonld[-1] += data
        elif self._in_title:
            self.title += data


PRICE_RE = re.compile(r"(?:(US\$|USD|\$|€|£)\s?)(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")
SYMBOL_CUR = {"$": "USD", "US$": "USD", "USD": "USD", "€": "EUR", "£": "GBP"}


def to_cents(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    s = re.sub(r"[^\d.]", "", s)
    if not re.fullmatch(r"\d+(\.\d{1,2})?|\.\d{1,2}", s):
        return None
    return int(round(float(s) * 100))


def _products(node: Any) -> list[dict]:
    """Every object with @type Product (or a list containing it) in a JSON-LD document, incl. @graph."""
    out: list[dict] = []
    if isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.lower() == "product" for x in types):
            out.append(node)
        for v in node.values():
            if isinstance(v, (dict, list)):
                out.extend(_products(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_products(v))
    return out


def _first_offer(offers: Any) -> dict:
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return {}
    if isinstance(offers.get("offers"), (list, dict)):  # AggregateOffer with nested offers
        inner = _first_offer(offers["offers"])
        return {**offers, **{k: v for k, v in inner.items() if v is not None}}
    return offers


def _image(v: Any) -> str | None:
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    return str(v) if isinstance(v, str) and v else None


def parse(page: str, source_url: str) -> ProductLookupResponse:
    c = _Collector()
    try:
        c.feed(page)
    except Exception:  # noqa: BLE001 - malformed markup: fall through with what was collected
        pass

    def done(name, price_cents, currency, image, confidence, note=None):
        image = urljoin(source_url, image) if image else None
        return ProductLookupResponse(name=name, price_cents=price_cents, currency=currency, source_url=source_url, image_url=image, confidence=confidence, note=note)

    def finish(name, raw_price, currency, image, confidence):
        currency = (currency or ("USD" if raw_price is not None else None))
        currency = currency.upper() if isinstance(currency, str) else None
        cents = to_cents(raw_price)
        if cents is None:
            return done(name, None, currency, image, confidence, NOTE_NO_PRICE)
        if currency != "USD":
            return done(name, None, currency, image, confidence, NOTE_NOT_USD.format(cur=currency))
        return done(name, cents, "USD", image, confidence)

    # 1. JSON-LD Product
    for blob in c.jsonld:
        try:
            doc = json.loads(blob.strip())
        except ValueError:
            continue
        for prod in _products(doc):
            offer = _first_offer(prod.get("offers"))
            raw = offer.get("price") if offer.get("price") is not None else offer.get("lowPrice")
            if isinstance(offer.get("priceSpecification"), dict) and raw is None:
                raw = offer["priceSpecification"].get("price")
            name = prod.get("name")
            name = html.unescape(str(name)).strip() if name else None
            return finish(name, raw, offer.get("priceCurrency"), _image(prod.get("image")), "high")

    # 2. Open Graph
    m = c.meta
    og_name = m.get("og:title")
    og_price = m.get("product:price:amount") or m.get("og:price:amount") or m.get("product:price") or m.get("price")
    og_cur = m.get("product:price:currency") or m.get("og:price:currency")
    og_image = m.get("og:image") or m.get("og:image:url")
    title = html.unescape(c.title).strip() or None
    if og_name or og_price or og_image:
        if og_price is not None:
            return finish(og_name.strip() if og_name else title, og_price, og_cur, og_image, "low")
        pm = PRICE_RE.search(title or "") or PRICE_RE.search(og_name or "")
        if pm:
            return finish(og_name.strip() if og_name else title, pm.group(2), SYMBOL_CUR.get(pm.group(1)), og_image, "low")
        return done(og_name.strip() if og_name else title, None, None, og_image, "low", NOTE_NO_PRICE)

    # 3. <title> + price regex
    if title:
        pm = PRICE_RE.search(title) or PRICE_RE.search(page[:200000])
        if pm:
            return finish(title, pm.group(2), SYMBOL_CUR.get(pm.group(1)), None, "low")
        return done(title, None, None, None, "low", NOTE_NO_PRICE)

    return done(None, None, None, None, "none", NOTE_NOTHING)


def lookup(url: str) -> ProductLookupResponse:
    url = url.strip()
    if not urlsplit(url).scheme:
        url = "https://" + url
    final_url, page = fetch(url)
    return parse(page, final_url)
