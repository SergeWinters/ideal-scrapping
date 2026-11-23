from pathlib import Path

import pytest

from idealista.config import Config, FilterConfig
from idealista.models import Listing
from idealista.search import (
    fetch_search,
    fetch_search_result,
    filter_listings,
    page_url,
    parse_floor_line,
    parse_location,
    parse_number,
    parse_price,
    parse_search_file,
    parse_search_html,
)

FIXTURE = Path(__file__).parent / "fixtures" / "search_madrid.html"


@pytest.fixture(scope="module")
def listings() -> list[Listing]:
    return parse_search_file(FIXTURE)


@pytest.fixture(scope="module")
def by_price(listings: list[Listing]) -> dict[int, Listing]:
    return {item.price: item for item in listings if item.price}


def test_parses_all_cards(listings):
    assert len(listings) == 30
    ids = [item.ad_id for item in listings]
    assert len(set(ids)) == len(ids)
    assert all(item.url.startswith("https://www.idealista.com/inmueble/") for item in listings)


def test_first_card_fields(listings):
    item = next(i for i in listings if i.ad_id == "110822401")
    assert item.price == 680_000
    assert item.previous_price == 695_000
    assert item.price_reduced is True
    assert item.rooms == 3
    assert item.size_m2 == 85.0
    assert item.bathrooms == 2
    assert item.property_type == "Piso"
    assert item.floor == "2ª"
    assert item.exterior is True
    assert item.elevator is True
    assert item.neighborhood == "Prosperidad"
    assert item.city == "Madrid"
    assert item.agency == "Clikalia España"
    assert "SOMOS PROPIETARIOS" in item.description
    assert item.terrace is True


def test_detects_no_elevator(listings):
    item = next(i for i in listings if i.ad_id == "111379612")
    assert item.elevator is False
    assert item.floor == "1ª"
    assert item.exterior is True


def test_neighborhood_when_no_street(listings):
    item = next(i for i in listings if "Estrella" in i.title)
    assert item.neighborhood == "Estrella"
    assert item.city == "Madrid"


def test_chalet_type_and_area(listings):
    item = next(i for i in listings if i.property_type.startswith("Casa o chalet"))
    assert item.neighborhood == "Aravaca"
    assert item.city == "Madrid"


def test_all_prices_and_sizes_parsed(listings):
    assert all(i.price and i.price > 0 for i in listings)
    assert all(i.size_m2 and i.size_m2 > 0 for i in listings)
    assert all(i.rooms and i.rooms >= 1 for i in listings)


def test_parse_price():
    assert parse_price("680.000€") == 680_000
    assert parse_price("2.690.000 €") == 2_690_000
    assert parse_price("A consultar") is None
    assert parse_price(None) is None


def test_parse_number():
    assert parse_number("1.234,5") == 1234.5
    assert parse_number("85") == 85.0
    assert parse_number("n/a") is None


@pytest.mark.parametrize(
    "line,expected",
    [
        ("2ª planta exterior con ascensor", ("2ª", True, True)),
        ("1ª planta exterior sin ascensor", ("1ª", True, False)),
        ("4ª planta interior con ascensor", ("4ª", False, True)),
        ("Bajo exterior", ("Bajo", True, None)),
        ("planta 3ª exterior", ("3ª", True, None)),
        ("", ("", None, None)),
    ],
)
def test_parse_floor_line(line, expected):
    assert parse_floor_line(line) == expected


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Piso en Calle de Alcalá, Goya, Madrid", ("Piso", "Goya", "Madrid")),
        ("Piso en Calle de Alcalá, Madrid", ("Piso", "", "Madrid")),
        ("Piso en Estrella, Madrid", ("Piso", "Estrella", "Madrid")),
        ("Ático en Calle Alcalá, Recoletos, Madrid", ("Ático", "Recoletos", "Madrid")),
        ("Piso en Madrid", ("Piso", "", "Madrid")),
        ("Vivienda sin formato", ("Vivienda sin formato", "", "")),
    ],
)
def test_parse_location(title, expected):
    assert parse_location(title) == expected


def mk(**kwargs) -> Listing:
    base = {"ad_id": "1", "url": "https://www.idealista.com/inmueble/1/"}
    base.update(kwargs)
    return Listing(**base)


def test_filter_price_and_rooms():
    items = [
        mk(ad_id="a", price=300_000, rooms=3),
        mk(ad_id="b", price=400_000, rooms=3),
        mk(ad_id="c", price=300_000, rooms=1),
        mk(ad_id="d", price=None, rooms=3),
    ]
    kept = filter_listings(items, FilterConfig(max_price=305_000, min_rooms=2))
    assert [i.ad_id for i in kept] == ["a"]


def test_filter_unknown_values_pass():
    items = [mk(ad_id="a", price=300_000, rooms=None, size_m2=None, elevator=None)]
    kept = filter_listings(items, FilterConfig(max_price=305_000, min_rooms=2))
    assert [i.ad_id for i in kept] == ["a"]


def test_filter_require_elevator():
    items = [
        mk(ad_id="a", price=200_000, elevator=False),
        mk(ad_id="b", price=200_000, elevator=True),
        mk(ad_id="c", price=200_000, elevator=None),
    ]
    kept = filter_listings(items, FilterConfig(require_elevator=True))
    assert [i.ad_id for i in kept] == ["b", "c"]


def test_filter_size_bounds():
    items = [
        mk(ad_id="a", price=200_000, size_m2=30),
        mk(ad_id="b", price=200_000, size_m2=60),
        mk(ad_id="c", price=200_000, size_m2=90),
    ]
    kept = filter_listings(items, FilterConfig(min_size_m2=50, max_size_m2=80))
    assert [i.ad_id for i in kept] == ["b"]


def test_page_url():
    url = "https://www.idealista.com/venta-viviendas/madrid-madrid/"
    assert page_url(url, 1) == url
    assert page_url(url, 2) == url.rstrip("/") + "/pagina-2.htm"


def test_empty_html_returns_nothing():
    assert parse_search_html("<html><body><p>nada</p></body></html>") == []


class FakeSearchSession:
    def __init__(self, html: str):
        self.html = html
        self.calls: list[str] = []

    def fetch(self, url: str, wait_selector: str | None = None) -> str:
        self.calls.append(url)
        return self.html

    def polite_delay(self) -> None:
        pass


def search_config(**filter_overrides) -> Config:
    cfg = Config()
    cfg.search.urls = ["https://www.idealista.com/venta-viviendas/madrid-madrid/"]
    cfg.search.max_pages = 1
    filters = {"max_price": 750_000, "min_rooms": 2}
    filters.update(filter_overrides)
    cfg.filters = FilterConfig(**filters)
    return cfg


def test_fetch_search_result_separates_matches_from_comparables():
    session = FakeSearchSession(FIXTURE.read_text(encoding="utf-8"))
    result = fetch_search_result(session, search_config())

    assert len(result.comparables) == 30
    assert len(result.matches) == 5
    assert all(any(match is comp for comp in result.comparables) for match in result.matches)
    assert len(session.calls) == 1


def test_fetch_search_result_dedupes_repeated_urls():
    html = FIXTURE.read_text(encoding="utf-8")
    session = FakeSearchSession(html)
    cfg = search_config()
    cfg.search.urls = [cfg.search.urls[0], cfg.search.urls[0]]

    result = fetch_search_result(session, cfg)

    assert len(result.comparables) == 30
    assert len(result.matches) == 5
    assert len(session.calls) == 2


def test_fetch_search_wrapper_returns_matches_only():
    session = FakeSearchSession(FIXTURE.read_text(encoding="utf-8"))
    matches = fetch_search(session, search_config())

    assert len(matches) == 5
    assert all(isinstance(item, Listing) for item in matches)
