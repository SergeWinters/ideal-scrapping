from pathlib import Path

import pytest

from idealista.config import Config
from idealista.detail import (
    _pretty_district,
    fetch_details,
    merge_detail,
    parse_detail_html,
)
from idealista.search import parse_search_file

FIXTURES = Path(__file__).parent / "fixtures"
DETAIL_URL = "https://www.idealista.com/inmueble/110822401/"


@pytest.fixture(scope="module")
def detail_html() -> str:
    return (FIXTURES / "detail_110822401.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail(detail_html: str):
    return parse_detail_html(detail_html, DETAIL_URL)


@pytest.fixture(scope="module")
def card_listings():
    return parse_search_file(FIXTURES / "search_madrid.html")


def test_detail_core_fields(detail):
    assert detail is not None
    assert detail.ad_id == "110822401"
    assert detail.price == 680_000
    assert detail.previous_price == 695_000
    assert detail.price_reduced is True
    assert detail.size_m2 == 85.0
    assert detail.rooms == 3
    assert detail.bathrooms == 2
    assert detail.property_type == "Piso"


def test_detail_location(detail):
    assert detail.neighborhood == "Prosperidad"
    assert detail.district == "Chamartín"
    assert detail.city == "Madrid"


def test_detail_building_and_condition(detail):
    assert detail.floor == "2ª"
    assert detail.exterior is True
    assert detail.elevator is True
    assert detail.year_built == 1966
    assert detail.condition == "Buen estado"
    assert detail.energy_rating == "E"
    assert detail.heating == "Calefacción central"


def test_detail_amenities(detail):
    assert detail.terrace is True
    assert detail.air_conditioning is True
    assert detail.furnished is True
    assert detail.balcony is None
    assert detail.pool is None
    assert detail.garage is None


def test_detail_description_and_agency(detail):
    assert "SOMOS PROPIETARIOS" in detail.description
    assert detail.agency == "Clikalia España"
    assert detail.detail_fetched is True
    assert "Con ascensor" in detail.tags


def test_merge_keeps_card_fields_and_adds_detail(detail, card_listings):
    card = next(i for i in card_listings if i.ad_id == "110822401")
    original_title = card.title
    merged = merge_detail(card, detail)
    assert merged is card
    assert merged.title == original_title
    assert merged.ad_id == "110822401"
    assert merged.detail_fetched is True
    assert merged.district == "Chamartín"
    assert merged.year_built == 1966
    assert merged.energy_rating == "E"
    assert merged.price_m2 == 8000.0
    assert merged.tags.count("Con ascensor") == 1


def test_empty_or_blocked_page_returns_none():
    assert parse_detail_html("<html><body>Access denied</body></html>", DETAIL_URL) is None


@pytest.mark.parametrize(
    "slug,expected",
    [
        ("chamartin", "Chamartín"),
        ("san-blas-canillejas", "San Blas-Canillejas"),
        ("unknown-place", "Unknown Place"),
    ],
)
def test_pretty_district(slug, expected):
    assert _pretty_district(slug) == expected


class FakeSession:
    def __init__(self, html: str):
        self.html = html
        self.urls: list[str] = []
        self.delays = 0

    def fetch(self, url: str, wait_selector: str | None = None) -> str:
        self.urls.append(url)
        return self.html

    def polite_delay(self) -> None:
        self.delays += 1


def test_fetch_details_limits_and_prioritises_value(detail_html, card_listings):
    session = FakeSession(detail_html)
    expected = sorted(
        [i for i in card_listings if i.price and i.size_m2],
        key=lambda i: (i.price / i.size_m2, i.price),
    )[:2]
    cfg = Config()
    cfg.search.max_details = 2

    enriched = fetch_details(session, card_listings, cfg.search.max_details)

    assert enriched == 2
    assert session.urls == [i.url for i in expected]
    assert session.delays == 2
    assert all(i.detail_fetched for i in expected)
    assert all(i.district == "Chamartín" for i in expected)
