from __future__ import annotations

import argparse
import sys

from .browser import BrowserSession, ChallengeError
from .config import DEFAULT_PROFILE_DIR, LINK_STYLES, Config, load_config
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idealista",
        description="Find affordable flats in Madrid and score them against area prices.",
    )
    p.add_argument("--config", metavar="PATH", help="YAML config file (default: ./config.yaml)")
    p.add_argument(
        "--url",
        action="append",
        metavar="URL",
        help="Idealista search URL; repeatable. Replaces config search.urls.",
    )
    p.add_argument("--max-price", type=int, help="Maximum asking price in euros")
    p.add_argument("--min-price", type=int, help="Minimum asking price in euros")
    p.add_argument("--min-rooms", type=int, help="Minimum number of rooms")
    p.add_argument("--min-size", type=float, metavar="M2", help="Minimum built surface in m2")
    p.add_argument("--pages", type=int, help="Results pages per URL (needs --allow-pagination)")
    p.add_argument(
        "--allow-pagination",
        action="store_true",
        help="Opt in to paginated URLs (disallowed by idealista robots.txt; low-volume only)",
    )
    p.add_argument("--max-details", type=int, help="Max listings to enrich from detail pages")
    p.add_argument("--top", type=int, help="Rows shown in the console table")
    p.add_argument(
        "--links",
        choices=LINK_STYLES,
        help="Console links: auto, clickable 'open' labels, or full URLs",
    )
    p.add_argument("--cache", metavar="PATH", help="Detail cache JSON path")
    p.add_argument("--no-cache", action="store_true", help="Ignore and do not update the detail cache")
    p.add_argument("--profile-dir", help="Chrome profile directory for the persistent session")
    p.add_argument("--headless", action="store_true", help="Run Chrome headless (likely blocked)")
    p.add_argument("--debug", action="store_true", help="Show full tracebacks on failure")
    p.add_argument(
        "--require-elevator",
        action="store_true",
        help="Only keep listings known to have a lift",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface (Qt/PySide6 with Fluent Design)",
    )
    return p


def apply_overrides(cfg: Config, args: argparse.Namespace) -> None:
    s, f = cfg.search, cfg.filters

    if args.url:
        s.urls = list(args.url)
    if args.max_price is not None:
        f.max_price = args.max_price
    if args.min_price is not None:
        f.min_price = args.min_price
    if args.min_rooms is not None:
        f.min_rooms = args.min_rooms
    if args.min_size is not None:
        f.min_size_m2 = args.min_size
    if args.pages is not None:
        s.max_pages = args.pages
    if args.allow_pagination:
        s.allow_pagination = True
    if args.max_details is not None:
        s.max_details = args.max_details
    if args.top is not None:
        cfg.output.top_n = args.top
    if args.links:
        cfg.output.link_style = args.links
    if args.cache:
        s.cache_path = args.cache
    if args.no_cache:
        s.use_cache = False
    if args.profile_dir:
        s.profile_dir = args.profile_dir
    if args.headless:
        s.headless = True
    if args.require_elevator:
        f.require_elevator = True

    if not s.profile_dir:
        s.profile_dir = DEFAULT_PROFILE_DIR


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "gui", False):
        from PySide6.QtWidgets import QApplication
        from .gui import MainWindow
        from .styles import apply_fluent_style
        app = QApplication(sys.argv)
        apply_fluent_style(app)
        win = MainWindow()
        win.show()
        return app.exec()

    try:
        cfg = load_config(args.config)
        apply_overrides(cfg, args)
        if cfg.search.max_pages > 1 and not cfg.search.allow_pagination:
            print(
                "warning: max_pages > 1 requires --allow-pagination; clamping to 1 page.",
                file=sys.stderr,
            )
        cfg.validate()
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if cfg.search.allow_pagination and cfg.search.max_pages > 1:
        print(
            "warning: paginated URLs are disallowed by idealista robots.txt. "
            "Keep volume low and personal.",
            file=sys.stderr,
        )

    print("Idealista deal-finder")
    print(
        f"Max price {cfg.filters.max_price:,} € | min rooms {cfg.filters.min_rooms} | "
        f"min size {cfg.filters.min_size_m2:g} m² | detail limit {cfg.search.max_details} | "
        f"cache {'on' if cfg.search.use_cache else 'off'} | links {cfg.output.link_style}"
    )
    try:
        with BrowserSession(cfg) as session:
            run_pipeline(cfg, session)
    except ChallengeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - actionable CLI failure
        if args.debug:
            raise
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
