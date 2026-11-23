from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from tabulate import tabulate

from .config import LINK_STYLES, Config, FilterConfig
from .market import MarketModel, Reference
from .models import Listing
from .scoring import rank_listings

LISTING_PATH_RE = re.compile(r"/inmueble/(\d+)/")
LISTING_BASE_URL = "https://www.idealista.com"
KNOWN_TERM_PROGRAMS = {
    "vscode",
    "iterm.app",
    "wezterm",
    "apple_terminal",
    "ghostty",
    "hyper",
}
BANDS = ("great deal", "good deal", "fair", "overpriced")
LEVELS = ("barrio", "distrito", "city", "manual")
HEADERS = (
    "#",
    "Score",
    "Deal",
    "Price",
    "€/m²",
    "vs area",
    "Rooms",
    "m²",
    "Floor",
    "Lift",
    "Barrio",
    "Link",
)


def format_eur(value: float | None) -> str:
    return f"{value:,.0f} €" if value is not None else "?"


def format_number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "?"
    return f"{value:,.{decimals}f}"


def format_pct(value: float | None) -> str:
    return f"{value:+.1f}%" if value is not None else "n/a"


def listing_url(url: str) -> str:
    match = LISTING_PATH_RE.search(url or "")
    if not match:
        return url or "?"
    return f"{LISTING_BASE_URL}/inmueble/{match.group(1)}/"


def osc8(url: str, label: str = "open") -> str:
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"


def _env_int(name: str) -> int | None:
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return None


def supports_hyperlinks(stream=None) -> bool:
    stream = stream or sys.stdout
    try:
        if not stream.isatty():
            return False
    except (AttributeError, OSError):
        return False

    if os.environ.get("WT_SESSION"):
        return True
    if os.environ.get("TERM_PROGRAM", "").casefold() in KNOWN_TERM_PROGRAMS:
        return True
    if os.environ.get("TERM", "").casefold() == "xterm-kitty":
        return True
    if os.environ.get("KITTY_WINDOW_ID"):
        return True
    if (_env_int("VTE_VERSION") or 0) >= 5000:
        return True
    if (_env_int("KONSOLE_VERSION") or 0) >= 220400:
        return True

    if os.name == "nt":
        try:
            return sys.getwindowsversion().build >= 19041
        except AttributeError:
            return False
    return False


def resolve_link_style(style: str, stream=None) -> str:
    if style not in LINK_STYLES:
        raise ValueError(f"unknown link style: {style!r}")
    if style == "auto":
        return "short" if supports_hyperlinks(stream) else "full"
    return style


def _yes_no_unknown(value: bool | None) -> str:
    if value is None:
        return "?"
    return "yes" if value else "no"


def _row(rank: int, listing: Listing, link: str) -> list[str]:
    area = listing.neighborhood or listing.district or listing.city or "?"
    return [
        str(rank),
        f"{listing.score:.1f}" if listing.score is not None else "n/a",
        listing.band or "n/a",
        format_eur(listing.price),
        format_number(listing.price_m2),
        format_pct(listing.discount_pct),
        str(listing.rooms) if listing.rooms is not None else "?",
        format_number(listing.size_m2),
        listing.floor or "?",
        _yes_no_unknown(listing.elevator),
        area,
        link,
    ]


def build_table(
    listings: list[Listing],
    top_n: int | None = None,
    link_style: str = "auto",
    stream=None,
) -> str:
    ranked = rank_listings(listings, top_n)
    if not ranked:
        return "No listings to show."

    mode = resolve_link_style(link_style, stream)
    if mode == "short":
        tokens = [f"L{index:03d}" for index in range(1, len(ranked) + 1)]
    else:
        tokens = [listing_url(listing.url) for listing in ranked]
    rows = [
        _row(index, listing, token)
        for index, (listing, token) in enumerate(zip(ranked, tokens), start=1)
    ]
    table = tabulate(
        rows,
        headers=HEADERS,
        tablefmt="simple",
        disable_numparse=True,
        colalign=("right", "right", "left", "right", "right", "right", "right",
                  "right", "left", "left", "left", "left"),
    )
    if mode != "short":
        return table

    for listing, token in zip(ranked, tokens):
        url = listing_url(listing.url)
        replacement = osc8(url) if url != "?" else "?"
        table = table.replace(token, replacement)
    return table


def _reference_line(ref: Reference | None) -> list[str]:
    if ref is None:
        return [
            "Market benchmark: not enough comparable listings for a city reference."
        ]
    iqr = f"{ref.iqr_pct:.2f}%" if ref.iqr_pct is not None else "n/a"
    return [
        f"Market benchmark: {ref.area} {format_eur(ref.eur_m2)}/m² "
        f"({ref.level}, n={ref.sample_size}, IQR {iqr}, "
        f"confidence {ref.confidence:.2f})"
    ]


def market_summary(
    listings: list[Listing],
    market: MarketModel,
    filters: FilterConfig,
    min_comparables: int | None = None,
) -> str:
    ref = market.city_reference
    lines = _reference_line(ref)
    if ref is not None and filters.max_price:
        affordable = filters.max_price / ref.eur_m2
        lines.append(
            f"Budget {format_eur(filters.max_price)} buys ~{affordable:.0f} m² "
            f"in {ref.area} at the median asking price (before costs)."
        )

    scored = [item for item in listings if item.score is not None]
    missing = len(listings) - len(scored)
    lines.append(
        f"Matched {len(listings)} listings: {len(scored)} scored, "
        f"{missing} without a reference."
    )
    if ref is not None and not scored:
        peer_requirement = (
            f"{min_comparables} leave-one-out peers"
            if min_comparables is not None
            else "enough leave-one-out peers"
        )
        lines.append(
            f"warning: benchmark n={ref.sample_size}, but each match needs "
            f"{peer_requirement}; no match could be scored."
        )

    bands = Counter(item.band for item in scored)
    band_text = ", ".join(f"{band} {bands[band]}" for band in BANDS if bands[band])
    if band_text:
        lines.append(f"Bands: {band_text}")

    levels = Counter(item.area_level for item in scored)
    lines.append(
        "Reference scope: "
        + ", ".join(f"{level} {levels.get(level, 0)}" for level in LEVELS)
    )
    return "\n".join(lines)


def render_report(
    listings: list[Listing], market: MarketModel, cfg: Config, top_n: int | None = None
) -> str:
    limit = cfg.output.top_n if top_n is None else top_n
    shown = min(limit, len(listings))
    return "\n".join(
        [
            market_summary(
                listings,
                market,
                cfg.filters,
                min_comparables=cfg.market.min_comparables,
            ),
            "",
            f"Ranked listings (top {shown} of {len(listings)})",
            build_table(listings, limit, link_style=cfg.output.link_style),
        ]
    )


def write_csv(
    listings: list[Listing], directory: str | Path, now: datetime | None = None
) -> Path:
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M")
    path = out_dir / f"madrid_{stamp}.csv"
    if path.exists():
        for suffix in range(2, 1000):
            candidate = out_dir / f"madrid_{stamp}_{suffix:02d}.csv"
            if not candidate.exists():
                path = candidate
                break
    ranked = rank_listings(listings)
    fields = Listing.field_names()
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for listing in ranked:
            row = listing.to_row()
            row["tags"] = "; ".join(listing.tags)
            writer.writerow(row)
    return path


def emit_report(
    listings: list[Listing],
    market: MarketModel,
    cfg: Config,
    now: datetime | None = None,
    out=print,
) -> Path | None:
    out(render_report(listings, market, cfg))
    if not cfg.output.write_csv:
        return None
    path = write_csv(listings, cfg.output.dir, now=now)
    out(f"CSV: {path.resolve()}")
    return path
