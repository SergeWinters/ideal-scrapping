from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import DetailCache
from .config import Config
from .detail import fetch_details
from .market import MarketModel, build_market
from .models import Listing
from .report import emit_report
from .scoring import score_listings
from .search import fetch_search_result

if TYPE_CHECKING:
    from .browser import BrowserSession


@dataclass
class PipelineResult:
    listings: list[Listing]
    market: MarketModel
    scored: int
    enriched: int
    csv_path: Path | None
    comparable_count: int = 0


def run_pipeline(
    cfg: Config,
    session: "BrowserSession",
    log=print,
    out=print,
    now: datetime | None = None,
) -> PipelineResult:
    pages = cfg.search.max_pages
    log(
        f"Searching {len(cfg.search.urls)} URL(s), up to {pages} page(s) each; "
        f"detail limit {cfg.search.max_details}."
    )
    search = fetch_search_result(session, cfg, log=log)
    listings = search.matches
    comparables = (
        search.comparables
        if cfg.market.comparables_from == "all_scraped"
        else listings
    )
    log(
        f"Comparables: {len(comparables)} from {cfg.market.comparables_from}; "
        f"{len(listings)} matching filters."
    )
    if not listings:
        log(
            "warning: no listings matched the filters; nothing to enrich. "
            "Try raising --max-price or relaxing filters."
        )

    cache: DetailCache | None = None
    enriched = 0
    if listings and cfg.search.max_details > 0:
        if cfg.search.use_cache:
            cache = DetailCache.load(cfg.search.cache_path, log=log)
            log(f"Detail cache: {len(cache)} entry/entries at {cfg.search.cache_path}")
        else:
            log("Detail cache: disabled.")
        enriched = fetch_details(
            session,
            listings,
            cfg.search.max_details,
            cache=cache,
            log=log,
        )

    market = build_market(comparables, cfg.market)
    scored = score_listings(
        listings,
        market,
        cfg.scoring,
        filters=cfg.filters,
        mortgage=cfg.mortgage,
    )
    log(f"Scored {scored}/{len(listings)} listings.")
    csv_path = emit_report(listings, market, cfg, now=now, out=out)
    return PipelineResult(
        listings=listings,
        market=market,
        scored=scored,
        enriched=enriched,
        csv_path=csv_path,
        comparable_count=len(comparables),
    )
