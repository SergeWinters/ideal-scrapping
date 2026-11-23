import json

from idealista.cache import CACHE_VERSION, DetailCache
from idealista.models import Listing


def detail_listing(**overrides) -> Listing:
    data = dict(
        ad_id="110822401",
        url="https://www.idealista.com/inmueble/110822401/",
        title="Piso en venta en Prosperidad, Madrid",
        price=680_000,
        size_m2=85.0,
        rooms=3,
        district="Chamartín",
        neighborhood="Prosperidad",
        city="Madrid",
        detail_fetched=True,
        tags=["Con ascensor"],
    )
    data.update(overrides)
    return Listing(**data)


def card(price=680_000, size_m2=85.0, url=None) -> Listing:
    return Listing(
        ad_id="110822401",
        url=url or "https://www.idealista.com/inmueble/110822401/",
        price=price,
        size_m2=size_m2,
    )


def test_put_get_roundtrip_with_card_signature():
    cache = DetailCache()
    listing = detail_listing()
    cache.put(listing, source_price=670_000, source_size_m2=84.0)

    cached = cache.get(card(price=670_000, size_m2=84.0))
    assert cached is not None
    assert cached.detail_fetched is True
    assert cached.district == "Chamartín"
    assert cached.tags == ["Con ascensor"]
    assert cache.hits == 1


def test_stale_price_size_or_url_is_a_miss():
    cache = DetailCache()
    cache.put(detail_listing(), source_price=670_000, source_size_m2=84.0)

    assert cache.get(card(price=680_000, size_m2=84.0)) is None
    assert cache.get(card(price=670_000, size_m2=85.0)) is None
    assert (
        cache.get(
            card(
                price=670_000,
                size_m2=84.0,
                url="https://www.idealista.com/inmueble/999/",
            )
        )
        is None
    )
    assert cache.hits == 0


def test_put_ignores_listings_without_fetched_detail():
    cache = DetailCache()
    cache.put(detail_listing(detail_fetched=False))
    assert len(cache) == 0
    assert cache.dirty is False


def test_save_and_load_utf8(tmp_path):
    path = tmp_path / "nested" / "listings.json"
    cache = DetailCache(path)
    cache.put(detail_listing())
    assert cache.save() == path
    assert cache.save() is None
    assert not path.with_suffix(".json.tmp").exists()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == CACHE_VERSION
    assert raw["listings"]["110822401"]["detail"]["district"] == "Chamartín"
    assert raw["listings"]["110822401"]["cached_at"]

    loaded = DetailCache.load(path)
    cached = loaded.get(card())
    assert cached is not None and cached.neighborhood == "Prosperidad"


def test_corrupt_cache_is_ignored_with_warning(tmp_path):
    path = tmp_path / "listings.json"
    path.write_text("{not json", encoding="utf-8")
    messages: list[str] = []
    cache = DetailCache.load(path, log=messages.append)
    assert len(cache) == 0
    assert any("ignoring detail cache" in message for message in messages)


def test_unsupported_cache_version_is_ignored(tmp_path):
    path = tmp_path / "listings.json"
    path.write_text(json.dumps({"version": 99, "listings": {}}), encoding="utf-8")
    messages: list[str] = []
    cache = DetailCache.load(path, log=messages.append)
    assert len(cache) == 0
    assert any("unsupported cache version" in message for message in messages)
