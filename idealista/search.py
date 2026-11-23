from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import lxml.html

from .config import FilterConfig
from .models import Listing

if TYPE_CHECKING:
    from .browser import BrowserSession

BASE_URL = "https://www.idealista.com"
LISTING_URL_RE = re.compile(r"/inmueble/(\d+)/")
ROOMS_RE = re.compile(r"(\d+)\s*hab", re.I)
SIZE_RE = re.compile(r"([\d.,]+)\s*m(?:2|²|\s*²)", re.I)
BATH_RE = re.compile(r"(\d+)\s*ba[ñn]o", re.I)
@dataclass
class SearchResult:
    """Filtered matches plus the wider market-comparable sample from the same pages."""

    matches: list[Listing] = field(default_factory=list)
    comparables: list[Listing] = field(default_factory=list)


STREET_PREFIXES = (
    "calle",
    "avenida",
    "plaza",
    "paseo",
    "camino",
    "ronda",
    "callejón",
    "callejon",
    "travesía",
    "travesia",
    "glorieta",
    "carretera",
    "vía",
    "via",
)


def normalize_space(text: str | None) -> str:
    return " ".join((text or "").split())


def parse_price(text: str | None) -> int | None:
    """'680.000€' -> 680000; 'A consultar' -> None."""
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def parse_number(text: str | None) -> float | None:
    """Spanish-formatted number: '1.234,5' -> 1234.5."""
    if not text:
        return None
    cleaned = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_location(title: str) -> tuple[str, str, str]:
    """Split a card title into (property_type, neighborhood, city).

    'Piso en Calle de Alcalá, Goya, Madrid' -> ('Piso', 'Goya', 'Madrid')
    'Piso en Calle de Alcalá, Madrid'       -> ('Piso', '', 'Madrid')
    'Piso en Estrella, Madrid'              -> ('Piso', 'Estrella', 'Madrid')
    """
    title = normalize_space(title)
    match = re.search(r"\s+en\s+(.+)$", title, re.I)
    if not match:
        return title, "", ""

    property_type = title[: match.start()].strip()
    parts = [p.strip() for p in match.group(1).split(",") if p.strip()]
    city = ""
    if parts:
        last = parts[-1]
        if last.lower() in {"madrid", "madrid capital"}:
            city = "Madrid"
        else:
            city = last.title()
        parts.pop()
    if parts and parts[0].lower().startswith(STREET_PREFIXES):
        parts.pop(0)
    neighborhood = parts[-1] if parts else ""
    return property_type, neighborhood, city


def parse_floor_line(text: str) -> tuple[str, bool | None, bool | None]:
    """'2ª planta exterior con ascensor' -> ('2ª', True, True)."""
    t = normalize_space(text).lower()
    if not t:
        return "", None, None

    elevator: bool | None = None
    if "sin ascensor" in t:
        elevator = False
    elif "ascensor" in t:
        elevator = True

    exterior: bool | None = None
    if re.search(r"\bexterior\b", t):
        exterior = True
    elif re.search(r"\binterior\b", t):
        exterior = False

    floor = ""
    match = re.search(r"(\d+)\s*[ªº]?\s*planta", t) or re.search(r"planta\s*(\d+)", t)
    if match:
        floor = f"{match.group(1)}ª"
    elif "bajo" in t or "baja" in t:
        floor = "Bajo"
    elif "entreplanta" in t:
        floor = "Entreplanta"
    elif "ático" in t or "atico" in t:
        floor = "Ático"
    elif "sótano" in t or "sotano" in t:
        floor = "Sótano"
    return floor, exterior, elevator


def _detail_spans(article) -> list[str]:
    return [
        normalize_space(span.text_content())
        for span in article.xpath(".//span[contains(@class,'item-detail')]")
    ]


def _pick_floor_line(spans: list[str]) -> str:
    for text in spans:
        low = text.lower()
        if (
            "planta" in low
            or "bajo" in low
            or "baja" in low
            or "ático" in low
            or "atico" in low
            or "entreplanta" in low
            or "sótano" in low
        ):
            return text
    return ""


def parse_card(article, base_url: str = BASE_URL) -> Listing | None:
    link = article.xpath(".//a[contains(@class,'item-link')]")
    href = link[0].get("href") if link else None
    if not href:
        for candidate in article.xpath(".//a[@href]"):
            if LISTING_URL_RE.search(candidate.get("href", "")):
                href = candidate.get("href")
                break
    if not href:
        return None

    ad_id = (article.get("data-element-id") or "").strip()
    if not ad_id:
        match = LISTING_URL_RE.search(href)
        ad_id = match.group(1) if match else ""
    if not ad_id:
        return None

    title = normalize_space(link[0].get("title") if link else "") or normalize_space(
        link[0].text_content() if link else ""
    )
    property_type, neighborhood, city = parse_location(title)

    price_el = article.xpath(".//*[contains(@class,'item-price')]")
    price = parse_price(price_el[0].text_content()) if price_el else None

    old_price_el = article.xpath(".//*[contains(@class,'pricedown_price')]")
    previous_price = parse_price(old_price_el[0].text_content()) if old_price_el else None

    spans = _detail_spans(article)
    joined = " ".join(spans)

    rooms = None
    if m := ROOMS_RE.search(joined):
        rooms = int(m.group(1))

    size_m2 = None
    if m := SIZE_RE.search(joined):
        size_m2 = parse_number(m.group(1))

    floor, exterior, elevator = parse_floor_line(_pick_floor_line(spans))

    desc_el = article.xpath(".//*[contains(@class,'item-description')]")
    description = normalize_space(desc_el[0].text_content()) if desc_el else ""

    bathrooms = None
    if m := BATH_RE.search(description or joined):
        bathrooms = int(m.group(1))

    agency_el = article.xpath(".//*[contains(@class,'hightop-agent-name')]")
    agency = normalize_space(agency_el[0].text_content()) if agency_el else ""

    lower_desc = description.lower()
    return Listing(
        ad_id=ad_id,
        url=urljoin(base_url, href),
        title=title,
        price=price,
        size_m2=size_m2,
        rooms=rooms,
        bathrooms=bathrooms,
        property_type=property_type,
        floor=floor,
        exterior=exterior,
        elevator=elevator,
        neighborhood=neighborhood,
        city=city,
        description=description,
        agency=agency,
        terrace=True if "terraza" in lower_desc else None,
        balcony=True if ("balcón" in lower_desc or "balcon" in lower_desc) else None,
        pool=True if "piscina" in lower_desc else None,
        garage=True if "garaje" in lower_desc else None,
        air_conditioning=True if "aire acondicionado" in lower_desc else None,
        furnished=True if "amueblado" in lower_desc else None,
        price_reduced=bool(previous_price and price and previous_price > price),
        previous_price=previous_price,
    )


def parse_search_html(html: str, base_url: str = BASE_URL) -> list[Listing]:
    doc = lxml.html.fromstring(html)
    listings: list[Listing] = []
    seen: set[str] = set()
    for article in doc.xpath("//article[contains(@class,'item')]"):
        listing = parse_card(article, base_url=base_url)
        if listing and listing.ad_id not in seen:
            seen.add(listing.ad_id)
            listings.append(listing)
    return listings


def parse_search_file(path: str | Path) -> list[Listing]:
    return parse_search_html(Path(path).read_text(encoding="utf-8"))


def filter_listings(listings: list[Listing], filters: FilterConfig) -> list[Listing]:
    """Keep listings that match known filters. Unknown values pass through."""
    kept: list[Listing] = []
    for item in listings:
        if item.price is None:
            continue
        if item.price < filters.min_price or item.price > filters.max_price:
            continue
        if item.rooms is not None:
            if item.rooms < filters.min_rooms:
                continue
            if filters.max_rooms is not None and item.rooms > filters.max_rooms:
                continue
        if item.size_m2 is not None:
            if item.size_m2 < filters.min_size_m2:
                continue
            if filters.max_size_m2 is not None and item.size_m2 > filters.max_size_m2:
                continue
        if filters.require_elevator and item.elevator is False:
            continue
        kept.append(item)
    return kept


def page_url(url: str, page: int) -> str:
    if page <= 1:
        return url
    return f"{url.rstrip('/')}/pagina-{page}.htm"


def _dump_debug(session: "BrowserSession", html: str, tag: str) -> None:
    debug = Path("data/debug")
    debug.mkdir(parents=True, exist_ok=True)
    (debug / f"{tag}.html").write_text(html, encoding="utf-8")
    try:
        session.screenshot(debug / f"{tag}.png")
    except Exception:  # noqa: BLE001 - screenshot is best-effort
        pass


def fetch_search_result(
    session: "BrowserSession",
    cfg,
    log=print,
) -> SearchResult:
    """Fetch search pages and return filtered matches plus all scraped comparables."""
    result = SearchResult()
    seen_matches: set[str] = set()
    seen_comparables: set[str] = set()

    for url in cfg.search.urls:
        for page in range(1, cfg.search.max_pages + 1):
            target = page_url(url, page)
            html = session.fetch(target, wait_selector="article.item")
            parsed = parse_search_html(html, base_url=target)
            kept = filter_listings(parsed, cfg.filters)
            log(f"{target}: parsed {len(parsed)}, kept after filters {len(kept)}")
            if parsed and not kept:
                log(
                    "warning: every listing on this page was filtered out; "
                    "raise --max-price or relax filters."
                )
            if not parsed:
                _dump_debug(session, html, f"search_empty_p{page}")
            for item in parsed:
                if item.ad_id not in seen_comparables:
                    seen_comparables.add(item.ad_id)
                    result.comparables.append(item)
            for item in kept:
                if item.ad_id not in seen_matches:
                    seen_matches.add(item.ad_id)
                    result.matches.append(item)
            if page < cfg.search.max_pages:
                session.polite_delay()
    return result


def fetch_search(
    session: "BrowserSession",
    cfg,
    log=print,
) -> list[Listing]:
    """Fetch every configured search page and return filtered, deduped listings."""
    return fetch_search_result(session, cfg, log=log).matches
