from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Listing

CACHE_VERSION = 1
DEFAULT_CACHE_PATH = "data/cache/listings.json"
_UNSET = object()


class DetailCache:
    """Persist enriched detail pages so reruns only fetch new or changed listings."""

    def __init__(
        self,
        path: str | Path = DEFAULT_CACHE_PATH,
        entries: dict[str, dict] | None = None,
    ):
        self.path = Path(path)
        self._entries = entries or {}
        self.dirty = False
        self.hits = 0

    def __len__(self) -> int:
        return len(self._entries)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CACHE_PATH, log=None) -> "DetailCache":
        cache = cls(path)
        if not cache.path.exists():
            return cache
        try:
            raw = json.loads(cache.path.read_text(encoding="utf-8"))
            if raw.get("version") != CACHE_VERSION:
                raise ValueError(f"unsupported cache version {raw.get('version')!r}")
            entries = raw.get("listings")
            if not isinstance(entries, dict):
                raise ValueError("cache 'listings' must be an object")
            cache._entries = entries
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            if log:
                log(f"warning: ignoring detail cache {cache.path}: {exc}")
            cache._entries = {}
        return cache

    def get(self, listing: Listing) -> Listing | None:
        entry = self._entries.get(listing.ad_id)
        if not isinstance(entry, dict):
            return None
        if entry.get("url") != listing.url:
            return None
        if listing.price is not None and entry.get("card_price") != listing.price:
            return None
        if (
            listing.size_m2 is not None
            and entry.get("card_size_m2") != listing.size_m2
        ):
            return None
        detail = entry.get("detail")
        if not isinstance(detail, dict):
            return None
        try:
            cached = Listing(**detail)
        except TypeError:
            return None
        if cached.ad_id != listing.ad_id or not cached.detail_fetched:
            return None
        self.hits += 1
        return cached

    def put(
        self,
        listing: Listing,
        source_price: object = _UNSET,
        source_size_m2: object = _UNSET,
    ) -> None:
        if not listing.detail_fetched:
            return
        self._entries[listing.ad_id] = {
            "url": listing.url,
            "card_price": listing.price if source_price is _UNSET else source_price,
            "card_size_m2": (
                listing.size_m2 if source_size_m2 is _UNSET else source_size_m2
            ),
            "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": listing.to_row(),
        }
        self.dirty = True

    def save(self) -> Path | None:
        if not self.dirty:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": CACHE_VERSION, "listings": self._entries}
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self.path)
        self.dirty = False
        return self.path
