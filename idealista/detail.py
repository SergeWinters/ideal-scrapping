from __future__ import annotations

import re
from typing import TYPE_CHECKING

import lxml.html

from .models import Listing
from .search import (
    BATH_RE,
    LISTING_URL_RE,
    ROOMS_RE,
    SIZE_RE,
    normalize_space,
    parse_floor_line,
    parse_price,
)

if TYPE_CHECKING:
    from .browser import BrowserSession
    from .cache import DetailCache

DISTRICTS = {
    "centro": "Centro",
    "arganzuela": "Arganzuela",
    "retiro": "Retiro",
    "salamanca": "Salamanca",
    "chamartin": "Chamartín",
    "tetuan": "Tetuán",
    "chamberi": "Chamberí",
    "fuencarral-el-pardo": "Fuencarral-El Pardo",
    "moncloa-aravaca": "Moncloa-Aravaca",
    "latina": "Latina",
    "carabanchel": "Carabanchel",
    "usera": "Usera",
    "puente-de-vallecas": "Puente de Vallecas",
    "moratalaz": "Moratalaz",
    "ciudad-lineal": "Ciudad Lineal",
    "hortaleza": "Hortaleza",
    "villaverde": "Villaverde",
    "villa-de-vallecas": "Villa de Vallecas",
    "vicalvaro": "Vicálvaro",
    "san-blas-canillejas": "San Blas-Canillejas",
    "barajas": "Barajas",
}

FLOOR_WORDS = ("planta", "bajo", "baja", "ático", "atico", "entreplanta", "sótano", "sotano")
CONDITION_RULES = (
    (("para reformar", "a reformar"), "Para reformar"),
    (("reformado",), "Reformado"),
    (("obra nueva", "nueva construcción", "nueva construccion"), "Obra nueva"),
    (("buen estado",), "Buen estado"),
    (("segunda mano",), "Segunda mano"),
)
ENERGY_CLASS_RE = re.compile(r"icon-energy-c-([a-g])\b", re.I)


def _pretty_district(slug: str) -> str:
    key = slug.strip().lower()
    if key in DISTRICTS:
        return DISTRICTS[key]
    return " ".join(part.capitalize() for part in key.replace("_", "-").split("-") if part)


def _features(doc) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for li in doc.xpath("//div[contains(@class,'details-property')]//li"):
        text = normalize_space(li.text_content())
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _location(doc) -> tuple[str, str, str]:
    neighborhood, district, city = "", "", ""
    minor = doc.xpath("//*[contains(@class,'main-info__title-minor')]")
    if minor:
        text = normalize_space(minor[0].text_content())
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if parts:
            city = parts[-1].title()
            parts.pop()
        if parts:
            neighborhood = parts[-1]

    for a in doc.xpath("//a[contains(@href,'/venta-viviendas/') or contains(@href,'/alquiler-viviendas/')]"):
        href = a.get("href") or ""
        path = [p for p in href.split("/") if p]
        if len(path) >= 3 and path[0] in ("venta-viviendas", "alquiler-viviendas"):
            if not city:
                city = path[1].replace("-provincia", "").replace("-", " ").title()
            district = _pretty_district(path[2])
            if len(path) >= 4 and not neighborhood:
                neighborhood = " ".join(
                    part.capitalize() for part in path[3].split("-") if part
                )
            break

    if district and not city:
        city = "Madrid"
    return neighborhood, district, city


def _energy_rating(doc) -> str:
    for el in doc.xpath("//*[contains(@class,'icon-energy-c-')]"):
        match = ENERGY_CLASS_RE.search(el.get("class") or "")
        if match:
            return match.group(1).upper()
    return ""


def _condition(features: list[str]) -> str:
    joined = " ".join(features).lower()
    for needles, label in CONDITION_RULES:
        if any(needle in joined for needle in needles):
            return label
    return ""


def _feature_flags(features: list[str], description: str) -> dict:
    text = " ".join(features).lower()
    desc = description.lower()
    both = f"{text} {desc}"

    def present(*needles: str) -> bool | None:
        return True if any(n in both for n in needles) else None

    furnished: bool | None = None
    if "sin amueblar" in both:
        furnished = False
    elif "amueblad" in both:
        furnished = True

    return {
        "terrace": present("terraza"),
        "balcony": present("balcón", "balcon"),
        "pool": present("piscina"),
        "garage": present("garaje", "plaza de garaje"),
        "air_conditioning": present("aire acondicionado"),
        "furnished": furnished,
    }


def _heating(features: list[str]) -> str:
    for feature in features:
        low = feature.lower()
        if "calefacción" in low or "calefaccion" in low:
            return feature
    return ""


def parse_detail_html(html: str, url: str) -> Listing | None:
    doc = lxml.html.fromstring(html)
    h1 = doc.xpath("//h1")
    if not h1:
        return None

    match = LISTING_URL_RE.search(url)
    ad_id = match.group(1) if match else ""

    title = normalize_space(h1[0].text_content())
    property_type = re.split(r"\s+en venta\b", title, maxsplit=1, flags=re.I)[0].strip()

    price_el = doc.xpath("//*[contains(@class,'info-data-price')]")
    price = parse_price(price_el[0].text_content()) if price_el else None

    old_price_el = doc.xpath("//*[contains(@class,'pricedown_price')]")
    previous_price = parse_price(old_price_el[0].text_content()) if old_price_el else None

    features = _features(doc)
    joined = " ".join(features)

    size_m2 = None
    if m := SIZE_RE.search(joined):
        size_m2 = float(m.group(1).replace(".", "").replace(",", "."))

    rooms = int(m.group(1)) if (m := ROOMS_RE.search(joined)) else None
    bathrooms = int(m.group(1)) if (m := BATH_RE.search(joined)) else None

    floor = ""
    exterior: bool | None = None
    elevator: bool | None = None
    for feature in features:
        low = feature.lower()
        if any(word in low for word in FLOOR_WORDS):
            floor, ext, lift = parse_floor_line(feature)
            exterior = ext if ext is not None else exterior
            elevator = lift if lift is not None else elevator
        if low.startswith("con ascensor"):
            elevator = True
        elif low.startswith("sin ascensor"):
            elevator = False

    year_built = None
    if m := re.search(r"construid[oa]\s+en\s+(\d{4})", joined, re.I):
        year_built = int(m.group(1))

    desc_el = doc.xpath("//*[contains(@class,'adCommentsLanguage')]") or doc.xpath(
        "//div[@class='comment']"
    )
    description = normalize_space(desc_el[0].text_content()) if desc_el else ""

    agency_el = doc.xpath("//*[contains(@class,'about-advertiser-name')]") or doc.xpath(
        "//*[contains(@class,'advertiser-name')]"
    )
    agency = normalize_space(agency_el[0].text_content()) if agency_el else ""
    agency = re.sub(r"^profesional\s+", "", agency, flags=re.I)

    neighborhood, district, city = _location(doc)
    flags = _feature_flags(features, description)

    return Listing(
        ad_id=ad_id,
        url=url,
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
        district=district,
        city=city,
        description=description,
        agency=agency,
        tags=list(features),
        year_built=year_built,
        condition=_condition(features),
        energy_rating=_energy_rating(doc),
        heating=_heating(features),
        price_reduced=bool(previous_price and price and previous_price > price),
        previous_price=previous_price,
        detail_fetched=True,
        **flags,
    )


def merge_detail(listing: Listing, detail: Listing) -> Listing:
    """Overlay detail-page data onto a search-card listing (card data wins when richer)."""
    text_fields = (
        "price",
        "size_m2",
        "rooms",
        "bathrooms",
        "property_type",
        "floor",
        "neighborhood",
        "district",
        "city",
        "description",
        "agency",
        "year_built",
        "condition",
        "energy_rating",
        "heating",
        "previous_price",
    )
    bool_fields = (
        "exterior",
        "elevator",
        "terrace",
        "balcony",
        "pool",
        "garage",
        "air_conditioning",
        "furnished",
    )
    for name in text_fields:
        value = getattr(detail, name)
        if value not in (None, ""):
            setattr(listing, name, value)
    for name in bool_fields:
        value = getattr(detail, name)
        if value is not None:
            setattr(listing, name, value)
    if detail.price_reduced:
        listing.price_reduced = True
    merged_tags = list(listing.tags)
    for tag in detail.tags:
        if tag not in merged_tags:
            merged_tags.append(tag)
    listing.tags = merged_tags
    listing.detail_fetched = True
    if listing.price and listing.size_m2:
        listing.price_m2 = round(listing.price / listing.size_m2, 2)
    return listing


def _detail_priority(listing: Listing) -> tuple[float, float]:
    if listing.price and listing.size_m2:
        return (listing.price / listing.size_m2, listing.price)
    return (float("inf"), listing.price or float("inf"))


def fetch_details(
    session: "BrowserSession",
    listings: list[Listing],
    max_details: int,
    cache: "DetailCache | None" = None,
    log=print,
) -> int:
    """Enrich the best-value listings from their detail pages. Returns enriched count."""
    if max_details <= 0:
        return 0
    selected = sorted(listings, key=_detail_priority)[:max_details]
    enriched = 0
    try:
        for item in selected:
            cached = cache.get(item) if cache is not None else None
            if cached is not None:
                merge_detail(item, cached)
                enriched += 1
                log(f"cached {item.ad_id} ({item.price_m2} €/m²)")
                continue
            source_price, source_size_m2 = item.price, item.size_m2
            try:
                html = session.fetch(item.url, wait_selector="h1")
            except Exception as exc:  # noqa: BLE001 - keep card data on failure
                log(f"detail fetch failed for {item.url}: {exc}")
                continue
            detail = parse_detail_html(html, item.url)
            if detail is None:
                log(f"detail page looked empty for {item.url}")
                continue
            merge_detail(item, detail)
            enriched += 1
            if cache is not None:
                cache.put(item, source_price, source_size_m2)
            log(f"enriched {item.ad_id} ({item.price_m2} €/m²)")
            session.polite_delay()
    finally:
        if cache is not None:
            cache.save()
    return enriched
