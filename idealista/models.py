from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class Listing:
    """A single property listing, raw plus computed analysis fields."""

    ad_id: str
    url: str

    title: str = ""
    price: int | None = None
    size_m2: float | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    property_type: str = ""

    floor: str = ""
    exterior: bool | None = None
    elevator: bool | None = None

    neighborhood: str = ""
    district: str = ""
    city: str = ""

    description: str = ""
    agency: str = ""
    tags: list[str] = field(default_factory=list)

    year_built: int | None = None
    condition: str = ""
    energy_rating: str = ""
    terrace: bool | None = None
    balcony: bool | None = None
    pool: bool | None = None
    garage: bool | None = None
    heating: str = ""
    air_conditioning: bool | None = None
    furnished: bool | None = None
    price_reduced: bool = False
    previous_price: int | None = None
    detail_fetched: bool = False

    price_m2: float | None = None
    area_reference_m2: float | None = None
    adjusted_reference_m2: float | None = None
    area_level: str = ""
    area_sample_size: int = 0
    area_iqr_pct: float | None = None
    confidence: float | None = None
    fair_price: float | None = None
    discount_pct: float | None = None
    score: float | None = None
    band: str = ""
    monthly_payment: float | None = None

    @property
    def area(self) -> str:
        return self.neighborhood or self.district or self.city

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]
