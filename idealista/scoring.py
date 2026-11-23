from __future__ import annotations

import re

from .config import FilterConfig, MortgageConfig, ScoringConfig
from .market import MarketModel
from .models import Listing

GROUND_FLOOR_PREFIXES = ("bajo", "baja", "planta baja")
HIGH_FLOOR_MARKERS = ("ático", "atico", "altillo")


def _is_ground_floor(floor: str) -> bool:
    text = (floor or "").strip().lower()
    if any(text.startswith(prefix) for prefix in GROUND_FLOOR_PREFIXES):
        return True
    match = re.match(r"(\d+)", text)
    return bool(match and int(match.group(1)) == 0)


def _is_high_floor(floor: str) -> bool:
    text = (floor or "").strip().lower()
    if any(marker in text for marker in HIGH_FLOOR_MARKERS):
        return True
    match = re.match(r"(\d+)", text)
    return bool(match and int(match.group(1)) >= 3)


def _needs_renovation(condition: str) -> bool:
    return "reformar" in (condition or "").lower()


def adjustment_sum(listing: Listing, cfg: ScoringConfig) -> float:
    adj = cfg.attribute_adjustments
    total = 0.0
    if listing.elevator is True:
        total += adj.get("elevator", 0.0)
    if listing.exterior is True:
        total += adj.get("exterior", 0.0)
    if listing.terrace is True:
        total += adj.get("terrace", 0.0)
    if _is_ground_floor(listing.floor):
        total += adj.get("ground_floor", 0.0)
    if listing.elevator is False and _is_high_floor(listing.floor):
        total += adj.get("high_floor_no_elevator", 0.0)
    if _needs_renovation(listing.condition):
        total += adj.get("needs_renovation", 0.0)
    return max(-0.9, total)


def _fit(listing: Listing, filters: FilterConfig) -> float:
    fit = 1.0
    if filters.min_rooms > 0:
        if listing.rooms is None:
            fit *= 0.85
        elif listing.rooms < filters.min_rooms:
            fit *= 0.5
    if filters.min_size_m2 > 0:
        if listing.size_m2 is None:
            fit *= 0.7
        elif listing.size_m2 < filters.min_size_m2:
            fit *= 0.5
    if filters.max_price and listing.price and listing.price > filters.max_price:
        fit *= 0.6
    if filters.require_elevator and listing.elevator is not True:
        fit *= 0.85 if listing.elevator is None else 0.5
    return max(0.3, fit)


def _band(discount_pct: float, cfg: ScoringConfig) -> str:
    if discount_pct <= cfg.great_deal_pct:
        return "great deal"
    if discount_pct <= cfg.good_deal_pct:
        return "good deal"
    if discount_pct <= cfg.overpriced_pct:
        return "fair"
    return "overpriced"


def estimate_monthly_payment(price: float | None, cfg: MortgageConfig) -> float | None:
    if not cfg.enabled or not price or price <= 0 or cfg.years <= 0:
        return None
    principal = price * (1 - cfg.down_payment_pct / 100.0)
    months = cfg.years * 12
    rate = cfg.annual_rate_pct / 100.0 / 12.0
    if principal <= 0:
        return 0.0
    if rate <= 0:
        return round(principal / months, 2)
    growth = (1 + rate) ** months
    return round(principal * rate * growth / (growth - 1), 2)


def score_listing(
    listing: Listing,
    market: MarketModel,
    cfg: ScoringConfig,
    filters: FilterConfig | None = None,
    mortgage: MortgageConfig | None = None,
) -> Listing:
    filters = filters or FilterConfig()
    mortgage = mortgage or MortgageConfig()

    if listing.price and listing.size_m2:
        listing.price_m2 = round(listing.price / listing.size_m2, 2)
    listing.monthly_payment = estimate_monthly_payment(listing.price, mortgage)

    ref = market.reference_for(listing)
    if ref is None or not listing.price_m2 or not listing.size_m2 or not listing.price:
        listing.band = "no reference"
        listing.score = None
        return listing

    listing.area_reference_m2 = round(ref.eur_m2, 2)
    listing.area_level = ref.level
    listing.area_sample_size = ref.sample_size
    listing.area_iqr_pct = ref.iqr_pct
    listing.confidence = ref.confidence

    adjusted = ref.eur_m2 * (1 + adjustment_sum(listing, cfg))
    listing.adjusted_reference_m2 = round(max(adjusted, 1.0), 2)
    listing.fair_price = round(listing.adjusted_reference_m2 * listing.size_m2, 2)
    listing.discount_pct = round(
        (listing.price - listing.fair_price) / listing.fair_price * 100.0, 2
    )
    listing.band = _band(listing.discount_pct, cfg)

    span = abs(cfg.great_deal_pct) or 10.0
    value_raw = max(0.0, min(100.0, 50.0 - 50.0 * listing.discount_pct / span))
    fit = _fit(listing, filters)
    listing.score = round(
        50.0 + (value_raw - 50.0) * ref.confidence * fit, 1
    )
    return listing


def score_listings(
    listings: list[Listing],
    market: MarketModel,
    cfg: ScoringConfig,
    filters: FilterConfig | None = None,
    mortgage: MortgageConfig | None = None,
) -> int:
    scored = 0
    for listing in listings:
        score_listing(listing, market, cfg, filters, mortgage)
        if listing.score is not None:
            scored += 1
    return scored


def rank_listings(listings: list[Listing], top_n: int | None = None) -> list[Listing]:
    scored = [listing for listing in listings if listing.score is not None]
    unscored = [listing for listing in listings if listing.score is None]
    scored.sort(
        key=lambda listing: (
            -listing.score,
            listing.discount_pct if listing.discount_pct is not None else 0.0,
            listing.price if listing.price is not None else float("inf"),
        )
    )
    ranked = scored + unscored
    return ranked[:top_n] if top_n is not None else ranked
