from __future__ import annotations

import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from .config import MarketConfig
from .models import Listing


@dataclass(frozen=True)
class Reference:
    area: str
    level: str
    eur_m2: float
    sample_size: int
    iqr_pct: float | None
    confidence: float


@dataclass(frozen=True)
class _Comp:
    ad_id: str
    eur_m2: float


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return text.encode("ascii", "ignore").decode("ascii").casefold().strip()


def _price_m2(listing: Listing) -> float | None:
    if listing.price and listing.size_m2:
        return listing.price / listing.size_m2
    return None


def _is_valid_comp(listing: Listing, cfg: MarketConfig) -> bool:
    ratio = _price_m2(listing)
    if ratio is None or not listing.size_m2:
        return False
    return (
        listing.size_m2 >= cfg.min_size_m2
        and cfg.min_price_m2 <= ratio <= cfg.max_price_m2
    )


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _percentile(sorted_values: list[float], pct: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct / 100.0
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    fraction = rank - low
    return sorted_values[low] * (1 - fraction) + sorted_values[high] * fraction


def _mad_filter(comps: list[_Comp], k: float) -> list[_Comp]:
    if len(comps) < 3:
        return comps
    values = [c.eur_m2 for c in comps]
    median = _median(values)
    mad = _median([abs(v - median) for v in values])
    if mad == 0:
        return comps
    limit = k * 1.4826 * mad
    return [c for c in comps if abs(c.eur_m2 - median) <= limit]


def _confidence(sample_size: int, iqr_pct: float | None, min_comparables: int) -> float:
    if sample_size < min_comparables:
        return 0.0
    growth = (sample_size - min_comparables) / (3 * min_comparables)
    size_factor = min(1.0, 0.6 + 0.4 * growth)
    dispersion_factor = 1.0 if iqr_pct is None else max(0.3, 1.0 - iqr_pct / 100.0)
    return round(size_factor * dispersion_factor, 3)


def _reference(
    area: str, level: str, comps: list[_Comp], min_comparables: int
) -> Reference | None:
    if len(comps) < min_comparables:
        return None
    values = sorted(c.eur_m2 for c in comps)
    median = _median(values)
    p25 = _percentile(values, 25)
    p75 = _percentile(values, 75)
    iqr_pct = round((p75 - p25) / median * 100.0, 2) if median else None
    return Reference(
        area=area,
        level=level,
        eur_m2=round(median, 2),
        sample_size=len(comps),
        iqr_pct=iqr_pct,
        confidence=_confidence(len(comps), iqr_pct, min_comparables),
    )


def _group(listings: list[Listing], key_fn, cfg: MarketConfig) -> dict[str, list[_Comp]]:
    raw: dict[str, list[_Comp]] = defaultdict(list)
    for listing in listings:
        key = key_fn(listing)
        ratio = _price_m2(listing)
        if key and ratio is not None and _is_valid_comp(listing, cfg):
            raw[key].append(_Comp(listing.ad_id, ratio))
    return {
        key: _mad_filter(comps, cfg.outlier_mad_k) for key, comps in raw.items()
    }


class MarketModel:
    def __init__(
        self,
        cfg: MarketConfig,
        city: str,
        city_groups: dict[str, list[_Comp]],
        district_groups: dict[str, list[_Comp]],
        neighborhood_groups: dict[str, list[_Comp]],
    ):
        self.cfg = cfg
        self.city = city
        self._groups = {
            "city": city_groups,
            "distrito": district_groups,
            "barrio": neighborhood_groups,
        }
        self._manual = {
            _normalize_key(key): value
            for key, value in cfg.reference_eur_m2.items()
        }

    def _manual_reference(self, listing: Listing) -> Reference | None:
        for area in (listing.neighborhood, listing.district, listing.city):
            value = self._manual.get(_normalize_key(area))
            if value:
                return Reference(
                    area=area,
                    level="manual",
                    eur_m2=float(value),
                    sample_size=0,
                    iqr_pct=None,
                    confidence=0.85,
                )
        return None

    def reference_for(self, listing: Listing) -> Reference | None:
        manual = self._manual_reference(listing)
        if manual is not None:
            return manual
        candidates = (
            ("barrio", listing.neighborhood),
            ("distrito", listing.district),
            ("city", listing.city),
        )
        for level, key in candidates:
            if not key:
                continue
            comps = [
                c
                for c in self._groups[level].get(key, [])
                if c.ad_id != listing.ad_id
            ]
            ref = _reference(key, level, comps, self.cfg.min_comparables)
            if ref is not None:
                return ref
        return None

    def group_reference(self, level: str, key: str) -> Reference | None:
        if level not in self._groups or not key:
            return None
        comps = self._groups[level].get(key, [])
        return _reference(key, level, comps, self.cfg.min_comparables)

    @property
    def city_reference(self) -> Reference | None:
        return self.group_reference("city", self.city)


def build_market(listings: list[Listing], cfg: MarketConfig) -> MarketModel:
    city_counts = Counter(
        listing.city for listing in listings if listing.city and _is_valid_comp(listing, cfg)
    )
    city = city_counts.most_common(1)[0][0] if city_counts else ""
    return MarketModel(
        cfg=cfg,
        city=city,
        city_groups=_group(listings, lambda x: x.city, cfg),
        district_groups=_group(listings, lambda x: x.district, cfg),
        neighborhood_groups=_group(listings, lambda x: x.neighborhood, cfg),
    )
