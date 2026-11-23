from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import TypeVar

DEFAULT_SEARCH_URL = "https://www.idealista.com/venta-viviendas/madrid-madrid/"
DEFAULT_PROFILE_DIR = str(Path.home() / ".cache" / "idealista_profile")
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
LINK_STYLES = ("auto", "short", "full")
COMPARABLE_SOURCES = ("all_scraped", "filtered")

T = TypeVar("T")


@dataclass
class SearchConfig:
    urls: list[str] = field(default_factory=lambda: [DEFAULT_SEARCH_URL])
    max_pages: int = 1
    allow_pagination: bool = False
    delay_min: float = 1.5
    delay_max: float = 3.5
    profile_dir: str = DEFAULT_PROFILE_DIR
    headless: bool = False
    max_details: int = 40
    use_cache: bool = True
    cache_path: str = "data/cache/listings.json"


@dataclass
class FilterConfig:
    max_price: int = 305_000
    min_price: int = 0
    min_rooms: int = 1
    max_rooms: int | None = None
    min_size_m2: float = 0
    max_size_m2: float | None = None
    require_elevator: bool = False


@dataclass
class MarketConfig:
    min_comparables: int = 8
    outlier_mad_k: float = 3.5
    min_price_m2: float = 500
    max_price_m2: float = 20_000
    min_size_m2: float = 25
    reference_eur_m2: dict[str, float] = field(default_factory=dict)
    comparables_from: str = "all_scraped"


@dataclass
class ScoringConfig:
    great_deal_pct: float = -10.0
    good_deal_pct: float = -3.0
    overpriced_pct: float = 3.0
    attribute_adjustments: dict[str, float] = field(
        default_factory=lambda: {
            "elevator": 0.03,
            "exterior": 0.02,
            "terrace": 0.02,
            "ground_floor": -0.04,
            "high_floor_no_elevator": -0.05,
            "needs_renovation": -0.10,
        }
    )


@dataclass
class MortgageConfig:
    enabled: bool = True
    down_payment_pct: float = 20.0
    annual_rate_pct: float = 3.0
    years: int = 30


@dataclass
class OutputConfig:
    dir: str = "data/output"
    top_n: int = 30
    write_csv: bool = True
    link_style: str = "auto"


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    mortgage: MortgageConfig = field(default_factory=MortgageConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def validate(self) -> None:
        s, f, m = self.search, self.filters, self.market

        if not s.urls:
            raise ValueError("search.urls must contain at least one URL")
        if s.max_pages < 1:
            raise ValueError("search.max_pages must be >= 1")
        if s.max_pages > 1 and not s.allow_pagination:
            self.search.max_pages = 1
        if s.delay_min < 0 or s.delay_max < s.delay_min:
            raise ValueError("search.delay_min/delay_max are invalid")
        if s.max_details < 0:
            raise ValueError("search.max_details must be >= 0")
        if s.use_cache and not s.cache_path:
            raise ValueError("search.cache_path must be set when use_cache is true")

        if f.max_price is None or f.max_price <= 0:
            raise ValueError("filters.max_price must be > 0")
        if f.min_price is None:
            f.min_price = 0
        if f.min_price < 0 or f.min_price > f.max_price:
            raise ValueError("filters.min_price must be within [0, max_price]")
        if f.min_rooms is None:
            f.min_rooms = 0
        if f.min_rooms < 0:
            raise ValueError("filters.min_rooms must be >= 0")
        if f.max_rooms is not None and f.max_rooms < f.min_rooms:
            raise ValueError("filters.max_rooms must be >= min_rooms")
        if f.min_size_m2 is None:
            f.min_size_m2 = 0.0
        if f.min_size_m2 < 0:
            raise ValueError("filters.min_size_m2 must be >= 0")
        if f.max_size_m2 is not None and f.max_size_m2 < f.min_size_m2:
            raise ValueError("filters.max_size_m2 must be >= min_size_m2")

        if m.min_comparables < 1:
            raise ValueError("market.min_comparables must be >= 1")
        if m.comparables_from not in COMPARABLE_SOURCES:
            raise ValueError(
                "market.comparables_from must be one of: "
                + ", ".join(COMPARABLE_SOURCES)
            )
        if m.outlier_mad_k <= 0:
            raise ValueError("market.outlier_mad_k must be > 0")
        if m.min_size_m2 < 0:
            raise ValueError("market.min_size_m2 must be >= 0")
        if m.min_price_m2 <= 0 or m.max_price_m2 <= m.min_price_m2:
            raise ValueError("market.min_price_m2/max_price_m2 are invalid")

        sc = self.scoring
        if not (sc.great_deal_pct < sc.good_deal_pct < sc.overpriced_pct):
            raise ValueError(
                "scoring thresholds must satisfy great_deal_pct < good_deal_pct "
                "< overpriced_pct"
            )
        if sc.great_deal_pct >= 0:
            raise ValueError("scoring.great_deal_pct must be negative")

        mo = self.mortgage
        if not 0 <= mo.down_payment_pct < 100:
            raise ValueError("mortgage.down_payment_pct must be within [0, 100)")
        if mo.annual_rate_pct < 0:
            raise ValueError("mortgage.annual_rate_pct must be >= 0")
        if mo.years < 1:
            raise ValueError("mortgage.years must be >= 1")

        if self.output.top_n < 1:
            raise ValueError("output.top_n must be >= 1")
        if self.output.link_style not in LINK_STYLES:
            raise ValueError(
                f"output.link_style must be one of: {', '.join(LINK_STYLES)}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        import yaml

        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)


def _build_section(cls: type[T], data: dict | None) -> T:
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise ValueError(f"Config section '{cls.__name__}' must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(
            f"Unknown key(s) in config section '{cls.__name__}': {', '.join(unknown)}"
        )
    return cls(**data)


def load_config(path: str | Path | None = None) -> Config:
    """Load config.yaml over hardcoded defaults.

    A missing path falls back to defaults; an explicitly given missing path is an error.
    """
    import yaml

    cfg = Config()
    if path is None:
        candidate = DEFAULT_CONFIG_PATH
        use_file = candidate.exists()
    else:
        candidate = Path(path)
        use_file = True
        if not candidate.exists():
            raise FileNotFoundError(f"Config file not found: {candidate}")

    if not use_file:
        cfg.validate()
        return cfg

    with candidate.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {candidate}")

    sections = {
        "search": SearchConfig,
        "filters": FilterConfig,
        "market": MarketConfig,
        "scoring": ScoringConfig,
        "mortgage": MortgageConfig,
        "output": OutputConfig,
    }
    unknown = sorted(set(raw) - set(sections))
    if unknown:
        raise ValueError(f"Unknown config section(s): {', '.join(unknown)}")

    for name, cls in sections.items():
        setattr(cfg, name, _build_section(cls, raw.get(name)))

    defaults = ScoringConfig().attribute_adjustments
    cfg.scoring.attribute_adjustments = {
        **defaults,
        **cfg.scoring.attribute_adjustments,
    }

    cfg.validate()
    return cfg
