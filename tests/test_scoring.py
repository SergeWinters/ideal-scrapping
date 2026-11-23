import pytest

from idealista.config import Config, FilterConfig, MortgageConfig, ScoringConfig
from idealista.market import Reference
from idealista.models import Listing
from idealista.scoring import (
    estimate_monthly_payment,
    rank_listings,
    score_listing,
    score_listings,
)


class FakeMarket:
    def __init__(self, ref: Reference | None):
        self.ref = ref

    def reference_for(self, listing: Listing) -> Reference | None:
        return self.ref


def ref(eur_m2: float = 6000, confidence: float = 1.0) -> Reference:
    return Reference(
        area="Sol",
        level="barrio",
        eur_m2=eur_m2,
        sample_size=12,
        iqr_pct=10.0,
        confidence=confidence,
    )


def make(**overrides) -> Listing:
    data = dict(
        ad_id="1",
        url="https://www.idealista.com/inmueble/1/",
        title="Piso en venta",
        price=600_000,
        size_m2=100.0,
        rooms=3,
        floor="2ª",
        elevator=True,
        exterior=True,
        terrace=True,
        condition="Buen estado",
    )
    data.update(overrides)
    return Listing(**data)


def test_price_m2_fair_price_and_adjustments():
    listing = make()
    score_listing(
        listing,
        FakeMarket(ref(6000)),
        ScoringConfig(),
        FilterConfig(max_price=2_000_000),
    )

    assert listing.price_m2 == 6000
    assert listing.area_reference_m2 == 6000
    assert listing.adjusted_reference_m2 == 6420
    assert listing.fair_price == 642_000
    assert listing.discount_pct == -6.54
    assert listing.band == "good deal"
    assert listing.score == 82.7
    assert listing.confidence == 1.0


def test_ground_floor_and_renovation_discount():
    listing = make(
        floor="Bajo",
        elevator=False,
        exterior=False,
        terrace=False,
        condition="Para reformar",
    )
    score_listing(listing, FakeMarket(ref(6000)), ScoringConfig())
    assert listing.adjusted_reference_m2 == 5160
    assert listing.fair_price == 516_000


def test_high_floor_without_elevator_discount():
    listing = make(
        floor="5ª",
        elevator=False,
        exterior=False,
        terrace=False,
        condition="Buen estado",
    )
    score_listing(listing, FakeMarket(ref(6000)), ScoringConfig())
    assert listing.adjusted_reference_m2 == 5700


@pytest.mark.parametrize(
    "price,expected_band",
    [
        (900_000, "great deal"),
        (970_000, "good deal"),
        (1_030_000, "fair"),
        (1_040_000, "overpriced"),
    ],
)
def test_band_thresholds(price, expected_band):
    listing = make(
        price=price,
        floor="",
        elevator=None,
        exterior=None,
        terrace=None,
        condition="",
    )
    score_listing(listing, FakeMarket(ref(10_000)), ScoringConfig())
    assert listing.band == expected_band


def test_score_is_damped_by_confidence():
    no_attrs = dict(floor="", elevator=None, exterior=None, terrace=None, condition="")
    low = make(price=900_000, **no_attrs)
    high = make(price=900_000, **no_attrs)

    score_listing(
        low,
        FakeMarket(ref(10_000, confidence=0.5)),
        ScoringConfig(),
        FilterConfig(max_price=2_000_000),
    )
    score_listing(
        high,
        FakeMarket(ref(10_000, confidence=1.0)),
        ScoringConfig(),
        FilterConfig(max_price=2_000_000),
    )

    assert low.score == 75.0
    assert high.score == 100.0
    assert low.discount_pct == high.discount_pct == -10.0


def test_fit_damps_score_when_requirements_are_missed():
    listing = make(price=900_000, rooms=1)
    filters = FilterConfig(min_rooms=3, max_price=2_000_000)
    score_listing(listing, FakeMarket(ref(10_000)), ScoringConfig(), filters)
    assert listing.score == 75.0


def test_fit_penalises_unknown_elevator_when_required():
    listing = make(price=900_000, elevator=None)
    filters = FilterConfig(require_elevator=True, max_price=2_000_000)
    score_listing(listing, FakeMarket(ref(10_000)), ScoringConfig(), filters)
    assert listing.score == 92.5


def test_mortgage_payment():
    cfg = MortgageConfig()
    assert estimate_monthly_payment(300_000, cfg) == pytest.approx(1011.85, abs=0.5)


def test_zero_interest_mortgage():
    cfg = MortgageConfig(annual_rate_pct=0)
    assert estimate_monthly_payment(300_000, cfg) == pytest.approx(666.67, abs=0.01)


def test_mortgage_disabled():
    assert estimate_monthly_payment(300_000, MortgageConfig(enabled=False)) is None


def test_no_reference_marks_listing_unscored():
    listing = make()
    score_listing(listing, FakeMarket(None), ScoringConfig())
    assert listing.score is None
    assert listing.band == "no reference"
    assert listing.price_m2 == 6000
    assert listing.monthly_payment is not None


def test_score_listings_counts_scored():
    good = make(ad_id="1")
    bad = make(ad_id="2", price=None)
    market = FakeMarket(ref())
    assert score_listings([good, bad], market, ScoringConfig()) == 1


def test_rank_listings_orders_and_limits():
    a = make(ad_id="a", price=900_000)
    b = make(ad_id="b", price=970_000)
    no_ref = make(ad_id="z", price=None)
    market = FakeMarket(ref(10_000))
    listings = [b, a, no_ref]
    score_listings(listings, market, ScoringConfig())

    ranked = rank_listings(listings, top_n=2)
    assert [item.ad_id for item in ranked] == ["a", "b"]

    full = rank_listings(listings)
    assert [item.ad_id for item in full] == ["a", "b", "z"]


def test_config_rejects_inverted_scoring_thresholds():
    cfg = Config()
    cfg.scoring.great_deal_pct = 5
    with pytest.raises(ValueError):
        cfg.validate()
