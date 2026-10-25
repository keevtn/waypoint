"""POST /products/lookup: read a product page server-side and pull name / price / image.

Fetch: http(s) only, browser-like headers, 6 s timeout, 1 MB body cap, at most 3 redirects, and
an SSRF guard that resolves every hop's host and rejects private, loopback, link-local, multicast
and reserved addresses (`check_host`). A 403 / 429 / 503 or a bot-challenge body ("access denied",
"verify you are human") is not an error: it returns confidence "none" with NOTE_BLOCKED.

Parse order: every `<script type="application/ld+json">` (arrays and `@graph` included; `Product`
or `ProductGroup`; `offers.price`, `offers[].price`, `offers.lowPrice`,
`offers.priceSpecification.price`) -> confidence "high"; Open Graph `og:title` /
`product:price:amount` / `og:price:amount` / `og:image` -> "low"; microdata `itemprop="price"`
(content attribute or text) -> "low"; `<title>` with a price regex -> "low"; a last-resort
`"price":"12.34"` in inline JSON -> "low"; else "none" with a note. Non-USD prices return the
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
BLOCKED_STATUSES = (403, 429, 503)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
NOTE_NO_PRICE = "Couldn't read a price from this page; enter it manually."
NOTE_NOT_USD = "This page lists the price in {cur}; enter the USD amount manually."
NOTE_NOTHING = "Couldn't read this page; enter the name and price manually."
NOTE_BLOCKED = "This store blocks automated lookups; enter the price manually."
CHALLENGE_RE = re.compile(r"access denied|verify you are human|are you a (?:human|robot)|bot detection|unusual traffic|enable javascript and cookies|captcha|request blocked|pardon our interruption", re.I)


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


def fetch(url: str) -> tuple[str, str, int]:
    """(final_url, html text, status) following up to MAX_REDIRECTS hops, guarding each hop.
    Blocked statuses (403/429/503) are returned, not raised, so the caller can say so."""
    current = url
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=False, headers=HEADERS) as client:
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
                    if r.status_code >= 400 and r.status_code not in BLOCKED_STATUSES:
                        raise ProductLookupError("fetch_failed", f"The page returned HTTP {r.status_code}")
                    ctype = r.headers.get("content-type", "")
                    if r.status_code < 400 and ctype and "html" not in ctype and "xml" not in ctype:
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
                    return current, text, r.status_code
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
        self.itemprop_price: list[str] = []
        self._in_ld = False
        self._in_title = False
        self._in_price = False

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
        if a.get("itemprop", "").lower() == "price":
            if a.get("content"):
                self.itemprop_price.append(a["content"])
            elif tag != "meta":
                self._in_price = True
                self.itemprop_price.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False
        elif tag == "title":
            self._in_title = False
        if self._in_price:
            self._in_price = False

    def handle_data(self, data: str) -> None:
        if self._in_ld and self.jsonld:
            self.jsonld[-1] += data
        elif self._in_title:
            self.title += data
        elif self._in_price and self.itemprop_price:
            self.itemprop_price[-1] += data


PRICE_RE = re.compile(r"(?:(US\$|USD|\$|€|£)\s?)(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")
INLINE_PRICE_RE = re.compile(r'"price"\s*:\s*"?(\d+\.\d{2})')
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
    """Every Product / ProductGroup object in a JSON-LD document (lists and @graph included)."""
    out: list[dict] = []
    if isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.lower() in ("product", "productgroup") for x in types):
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


def _offer_price(offer: dict) -> tuple[Any, Any]:
    raw = offer.get("price")
    if raw is None:
        raw = offer.get("lowPrice")
    spec = offer.get("priceSpecification")
    if isinstance(spec, list):
        spec = spec[0] if spec else None
    cur = offer.get("priceCurrency")
    if isinstance(spec, dict):
        if raw is None:
            raw = spec.get("price")
        cur = cur or spec.get("priceCurrency")
    return raw, cur


def _image(v: Any) -> str | None:
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    return str(v) if isinstance(v, str) and v else None


def looks_blocked(page: str, status: int) -> bool:
    if status in BLOCKED_STATUSES:
        return True
    return bool(CHALLENGE_RE.search(page[:50000]))


def parse(page: str, source_url: str, status: int = 200) -> ProductLookupResponse:
    c = _Collector()
    try:
        c.feed(page)
    except Exception:  # noqa: BLE001 - malformed markup: fall through with what was collected
        pass

    def done(name, price_cents, currency, image, confidence, note=None):
        image = urljoin(source_url, image) if image else None
        return ProductLookupResponse(name=name, price_cents=price_cents, currency=currency, source_url=source_url, image_url=image, confidence=confidence, note=note)

    def finish(name, raw_price, currency, image, confidence):
        currency = currency or ("USD" if raw_price is not None else None)
        currency = currency.upper() if isinstance(currency, str) else None
        cents = to_cents(raw_price)
        if cents is None:
            return done(name, None, currency, image, confidence, NOTE_NO_PRICE)
        if currency != "USD":
            return done(name, None, currency, image, confidence, NOTE_NOT_USD.format(cur=currency))
        return done(name, cents, "USD", image, confidence)

    title = html.unescape(c.title).strip() or None
    m = c.meta
    og_name = (m.get("og:title") or "").strip() or None
    og_image = m.get("og:image") or m.get("og:image:url")
    name = og_name or title

    # 1. JSON-LD Product / ProductGroup (first one with a readable price wins; else the first one)
    found: list[tuple] = []
    for blob in c.jsonld:
        try:
            doc = json.loads(blob.strip())
        except ValueError:
            continue
        for prod in _products(doc):
            offer = _first_offer(prod.get("offers"))
            raw, cur = _offer_price(offer)
            pname = prod.get("name")
            pname = html.unescape(str(pname)).strip() if pname else name
            found.append((pname, raw, cur, _image(prod.get("image")) or og_image))
    if found:
        best = next((f for f in found if to_cents(f[1]) is not None), found[0])
        return finish(*best, "high")

    # 2. Open Graph price
    og_price = m.get("product:price:amount") or m.get("og:price:amount") or m.get("product:price") or m.get("price")
    og_cur = m.get("product:price:currency") or m.get("og:price:currency")
    if og_price is not None:
        return finish(name, og_price, og_cur, og_image, "low")

    # 3. microdata itemprop="price"
    for raw in c.itemprop_price:
        if to_cents(raw) is not None or PRICE_RE.search(raw):
            pm = PRICE_RE.search(raw)
            cur = m.get("product:price:currency") or (SYMBOL_CUR.get(pm.group(1)) if pm else None)
            return finish(name, pm.group(2) if pm else raw, cur, og_image, "low")

    # 4. <title> / og:title with a price in it
    pm = PRICE_RE.search(title or "") or PRICE_RE.search(og_name or "")
    if pm:
        return finish(name, pm.group(2), SYMBOL_CUR.get(pm.group(1)), og_image, "low")

    # 5. "price":"12.34" in inline JSON anywhere in the page
    im = INLINE_PRICE_RE.search(page)
    if im:
        return finish(name, im.group(1), None, og_image, "low")

    if looks_blocked(page, status):
        return done(None, None, None, None, "none", NOTE_BLOCKED)
    if name:
        return done(name, None, None, og_image, "low", NOTE_NO_PRICE)
    return done(None, None, None, None, "none", NOTE_NOTHING)


def lookup(url: str) -> ProductLookupResponse:
    url = url.strip()
    if not urlsplit(url).scheme:
        url = "https://" + url
    final_url, page, status = fetch(url)
    if status in BLOCKED_STATUSES:
        return ProductLookupResponse(name=None, price_cents=None, currency=None, source_url=final_url, image_url=None, confidence="none", note=NOTE_BLOCKED)
    return parse(page, final_url, status)
