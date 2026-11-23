from datetime import datetime
from pathlib import Path

from idealista.config import Config
from idealista.pipeline import run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_HTML = (FIXTURES / "search_madrid.html").read_text(encoding="utf-8")
SEARCH_URL = "https://www.idealista.com/venta-viviendas/madrid-madrid/"


def detail_html(price: int = 600_000, size_m2: int = 70) -> str:
    price_text = f"{price:,}".replace(",", ".") + " €"
    return f"""
    <html><body>
      <h1>Piso en venta en Chamberí, Madrid</h1>
      <span class="info-data-price">{price_text}</span>
      <div class="details-property"><ul>
        <li>3 hab.</li><li>{size_m2} m²</li>
        <li>2ª planta exterior con ascensor</li>
        <li>Construido en 1966</li><li>Buen estado</li>
      </ul></div>
      <div class="main-info__title-minor">Chamberí, Madrid</div>
      <a href="/venta-viviendas/madrid/chamberi/"></a>
      <div class="adCommentsLanguage">Piso exterior con terraza.</div>
      <div class="about-advertiser-name">Profesional Inmobiliaria Test</div>
    </body></html>
    """


class FakeSession:
    def __init__(self, search_html: str, detail_page: str | None):
        self.search_html = search_html
        self.detail_page = detail_page
        self.search_calls: list[str] = []
        self.detail_calls: list[str] = []
        self.delays = 0

    def fetch(self, url: str, wait_selector: str | None = None) -> str:
        if "/inmueble/" in url:
            self.detail_calls.append(url)
            if self.detail_page is None:
                raise AssertionError(f"unexpected detail fetch: {url}")
            return self.detail_page
        self.search_calls.append(url)
        return self.search_html

    def polite_delay(self) -> None:
        self.delays += 1


def make_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.filters.max_price = 5_000_000
    cfg.search.max_details = 1
    cfg.search.cache_path = str(tmp_path / "cache" / "listings.json")
    cfg.output.dir = str(tmp_path / "output")
    cfg.output.top_n = 5
    return cfg


def test_pipeline_end_to_end_and_cache_reuse(tmp_path):
    cfg = make_config(tmp_path)
    logs: list[str] = []
    report: list[str] = []
    now = datetime(2026, 11, 9, 15, 0)

    first = FakeSession(SEARCH_HTML, detail_html())
    result = run_pipeline(cfg, first, log=logs.append, out=report.append, now=now)

    assert len(result.listings) == 30
    assert result.scored == 30
    assert result.enriched == 1
    assert len(first.search_calls) == 1
    assert len(first.detail_calls) == 1
    assert first.delays == 1
    assert result.csv_path is not None
    assert result.csv_path.name == "madrid_20261109_1500.csv"
    assert result.csv_path.exists()
    assert Path(cfg.search.cache_path).exists()
    assert sum(item.detail_fetched for item in result.listings) == 1
    assert any("enriched" in line for line in logs)
    assert any("Scored 30/30" in line for line in logs)
    output = "\n".join(report)
    assert "Market benchmark" in output
    assert "Ranked listings (top 5 of 30)" in output

    second_logs: list[str] = []
    second = FakeSession(SEARCH_HTML, None)
    again = run_pipeline(
        cfg, second, log=second_logs.append, out=report.append, now=now
    )

    assert len(second.search_calls) == 1
    assert second.detail_calls == []
    assert again.enriched == 1
    assert sum(item.detail_fetched for item in again.listings) == 1
    assert any("cached" in line for line in second_logs)


def test_pipeline_no_results_still_reports(tmp_path):
    cfg = make_config(tmp_path)
    cfg.filters.max_price = 1
    logs: list[str] = []
    report: list[str] = []
    session = FakeSession(SEARCH_HTML, None)

    result = run_pipeline(cfg, session, log=logs.append, out=report.append)

    assert result.listings == []
    assert result.scored == 0
    assert session.detail_calls == []
    assert any("no listings matched" in line for line in logs)
    assert "Matched 0 listings" in "\n".join(report)
    assert result.csv_path is not None and result.csv_path.exists()


def test_pipeline_uses_all_scraped_listings_as_comparables(tmp_path):
    cfg = make_config(tmp_path)
    cfg.filters.max_price = 750_000
    cfg.search.max_details = 0
    logs: list[str] = []
    session = FakeSession(SEARCH_HTML, None)

    result = run_pipeline(cfg, session, log=logs.append, out=lambda _: None)

    assert len(result.listings) == 5
    assert result.scored == 5
    assert result.comparable_count == 30
    assert result.market.city_reference.sample_size >= 8
    assert any("Comparables: 30 from all_scraped" in line for line in logs)
    assert session.detail_calls == []


def test_pipeline_can_disable_cache(tmp_path):
    cfg = make_config(tmp_path)
    cfg.search.use_cache = False
    cfg.search.max_details = 1
    session = FakeSession(SEARCH_HTML, detail_html())
    logs: list[str] = []

    result = run_pipeline(cfg, session, log=logs.append, out=lambda _: None)

    assert result.enriched == 1
    assert "Detail cache: disabled." in logs
    assert not Path(cfg.search.cache_path).exists()
