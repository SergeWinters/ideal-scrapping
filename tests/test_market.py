import pytest

from idealista.config import MarketConfig
from idealista.market import build_market
from idealista.models import Listing


def make(
    ad_id: str,
    eur_m2: float,
    size: float = 100,
    neighborhood: str = "Sol",
    district: str = "Centro",
    city: str = "Madrid",
) -> Listing:
    return Listing(
        ad_id=ad_id,
        url=f"https://www.idealista.com/inmueble/{ad_id}/",
        price=int(eur_m2 * size),
        size_m2=size,
        neighborhood=neighborhood,
        district=district,
        city=city,
    )


def test_barrio_then_distrito_then_city_fallback():
    listings = [make(f"sol{i}", 5000) for i in range(10)]
    listings.append(make("palacio", 6000, neighborhood="Palacio"))
    listings += [make(f"goya{i}", 7000, neighborhood="Goya", district="Salamanca") for i in range(2)]
    market = build_market(listings, MarketConfig())

    sol = market.reference_for(listings[0])
    palacio = market.reference_for(listings[10])
    goya = market.reference_for(listings[11])

    assert sol.level == "barrio" and sol.area == "Sol"
    assert sol.sample_size == 9
    assert sol.eur_m2 == 5000

    assert palacio.level == "distrito" and palacio.area == "Centro"
    assert palacio.sample_size == 10
    assert palacio.eur_m2 == 5000

    assert goya.level == "city" and goya.area == "Madrid"
    assert goya.sample_size == 12
    assert goya.eur_m2 == 5000


def test_reference_excludes_listing_itself():
    values = [1000, 2000, 3000, 4000, 6000, 7000, 8000, 9000, 10000]
    listings = [make(f"x{i}", value) for i, value in enumerate(values)]
    market = build_market(listings, MarketConfig())

    target = listings[4]
    ref = market.reference_for(target)
    whole_group = market.group_reference("barrio", "Sol")

    assert ref.sample_size == 8
    assert ref.eur_m2 == 5500
    assert whole_group.sample_size == 9
    assert whole_group.eur_m2 == 6000


def test_mad_outlier_is_dropped():
    normal = [4800, 4900, 4950, 5000, 5000, 5050, 5100, 5150, 5200, 5250]
    listings = [make(f"n{i}", value) for i, value in enumerate(normal)]
    listings.append(make("outlier", 15000))
    market = build_market(listings, MarketConfig())

    assert market.group_reference("barrio", "Sol").sample_size == 10
    assert market.reference_for(listings[0]).sample_size == 9


def test_hard_bounds_filter_comparables():
    listings = [make(f"ok{i}", 5000) for i in range(9)]
    listings.append(make("tiny", 5000, size=10))
    listings.append(make("cheap", 400))
    listings.append(make("pricey", 25000))
    market = build_market(listings, MarketConfig())

    ref = market.group_reference("barrio", "Sol")
    assert ref.sample_size == 9
    assert ref.eur_m2 == 5000


def test_iqr_and_confidence_are_reported():
    values = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    listings = [make(f"v{i}", value) for i, value in enumerate(values)]
    market = build_market(listings, MarketConfig())

    ref = market.group_reference("barrio", "Sol")
    assert ref.iqr_pct == 80.0
    assert 0 < ref.confidence < 1


def test_manual_reference_is_accent_and_case_insensitive():
    cfg = MarketConfig(reference_eur_m2={"chamberi": 7000})
    listing = make(
        "manual",
        5000,
        neighborhood="Chamberí",
        district="Chamberí",
    )
    market = build_market([listing], cfg)

    ref = market.reference_for(listing)
    assert ref.level == "manual"
    assert ref.area == "Chamberí"
    assert ref.eur_m2 == 7000
    assert ref.sample_size == 0


def test_no_reference_when_group_is_too_small():
    listings = [make(f"s{i}", 5000, neighborhood="Solo", district="Centro") for i in range(3)]
    market = build_market(listings, MarketConfig())
    assert market.reference_for(listings[0]) is None


def test_config_validation_rejects_bad_bounds():
    cfg = MarketConfig(min_price_m2=20000, max_price_m2=500)
    from idealista.config import Config

    with pytest.raises(ValueError):
        Config(market=cfg).validate()


def test_config_validation_rejects_bad_comparable_source():
    from idealista.config import Config

    cfg = MarketConfig(comparables_from="somewhere")
    with pytest.raises(ValueError, match="market.comparables_from"):
        Config(market=cfg).validate()
