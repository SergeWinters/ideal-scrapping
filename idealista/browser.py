from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .config import Config, load_config

CHALLENGE_SELECTOR = (
    "#datadome-captcha, iframe[src*='captcha-delivery.com'], "
    "iframe[src*='geo.captcha-delivery.com']"
)
CHALLENGE_URL_MARKERS = ("captcha-delivery.com",)
BLOCK_TEXT_MARKERS = ("uso indebido", "acceso bloqueado", "access denied")


class ChallengeError(RuntimeError):
    pass


def get_bundled_chrome() -> Path | None:
    """Detecta si hay un Chromium portable junto al ejecutable o en la raíz del proyecto."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent

    for sub in ("browser/chrome-win64/chrome.exe", "browser/chrome.exe", "chrome-win64/chrome.exe"):
        candidate = base_dir / sub
        if candidate.exists():
            return candidate
    return None


class BrowserSession:
    """Headed persistent Chrome session that survives DataDome captchas."""

    def __init__(self, cfg: Config, log=None):
        self.cfg = cfg
        self.log = log or print
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._browser: Browser | None = None

    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        s = self.cfg.search
        profile = Path(s.profile_dir).expanduser()
        profile.mkdir(parents=True, exist_ok=True)

        self._pw = sync_playwright().start()

        bundled = get_bundled_chrome()
        launch_kwargs = {
            "user_data_dir": str(profile),
            "headless": s.headless,
            "locale": "es-ES",
            "timezone_id": "Europe/Madrid",
            "viewport": {"width": 1366, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled", "--no-first-run"],
            "ignore_default_args": ["--enable-automation"],
        }
        if bundled:
            launch_kwargs["executable_path"] = str(bundled)
            self.log(f"Navegador: Usando Chromium portable incluido ({bundled.name})")
        else:
            launch_kwargs["channel"] = "chrome"

        try:
            self._ctx = self._pw.chromium.launch_persistent_context(**launch_kwargs)
        except Exception:
            if not bundled and launch_kwargs.get("channel") == "chrome":
                launch_kwargs["channel"] = "msedge"
                self._ctx = self._pw.chromium.launch_persistent_context(**launch_kwargs)
            else:
                raise

        self._ctx.set_default_timeout(20_000)
        self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

    def close(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            self._ctx = None
            self._pw = None
            self._browser = None

    @property
    def page(self) -> Page:
        if self._ctx is None:
            raise RuntimeError("BrowserSession not started")
        pages = self._ctx.pages
        page = pages[0] if pages else self._ctx.new_page()
        return page

    def _is_challenge(self, page: Page) -> bool:
        if any(marker in page.url for marker in CHALLENGE_URL_MARKERS):
            return True
        try:
            if page.locator(CHALLENGE_SELECTOR).count():
                return True
            title = page.title().lower()
            if "access denied" in title:
                return True
            body = page.locator("body").inner_text(timeout=1_500).lower()
        except PlaywrightTimeoutError:
            return False
        return any(marker in body for marker in BLOCK_TEXT_MARKERS)

    def _wait_for_challenge(self, page: Page, timeout: float) -> None:
        if self.cfg.search.headless:
            raise ChallengeError(
                "DataDome challenge detected in headless mode; rerun without --headless"
            )
        self.log(
            ">> DataDome challenge detected. Solve it in the Chrome window "
            f"(waiting up to {int(timeout)}s)..."
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            page.wait_for_timeout(2_000)
            if not self._is_challenge(page):
                self.log(">> Challenge cleared.")
                return
        raise ChallengeError(f"DataDome challenge not cleared within {int(timeout)}s")

    def fetch(self, url: str, wait_selector: str | None = None) -> str:
        """Navigate to url, solving a captcha if needed, and return page HTML."""
        s = self.cfg.search
        page = self.page
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                except PlaywrightTimeoutError:
                    pass

                if self._is_challenge(page):
                    self._wait_for_challenge(page, timeout=120)

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=20_000)
                    except PlaywrightTimeoutError:
                        if self._is_challenge(page):
                            self._wait_for_challenge(page, timeout=120)
                            page.wait_for_selector(wait_selector, timeout=20_000)

                if self._is_challenge(page):
                    raise ChallengeError("still challenged after navigation")

                return page.content()
            except ChallengeError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry network noise
                last_error = exc
                self.log(f">> attempt {attempt}/3 failed: {exc}")
                if attempt < 3:
                    delay = random.uniform(s.delay_min, s.delay_max)
                    time.sleep(delay)

        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    def polite_delay(self) -> None:
        s = self.cfg.search
        time.sleep(random.uniform(s.delay_min, s.delay_max))

    def screenshot(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idealista.browser", description="Fetch an HTML fixture.")
    parser.add_argument("--config", help="YAML config path")
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--wait-selector", default="article.item")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    out = Path(args.out)
    with BrowserSession(cfg) as session:
        try:
            html = session.fetch(args.url, wait_selector=args.wait_selector)
        except Exception as exc:  # noqa: BLE001 - dump evidence before failing
            debug = Path("data/debug")
            debug.mkdir(parents=True, exist_ok=True)
            try:
                session.screenshot(debug / "fetch_failure.png")
                (debug / "fetch_failure.html").write_text(
                    session.page.content(), encoding="utf-8"
                )
            except Exception:  # noqa: BLE001
                pass
            raise SystemExit(f"fetch failed: {exc}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"saved {len(html):,} chars -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
