from datetime import datetime

from idealista.config import Config, FilterConfig
from idealista.market import Reference
from idealista.models import Listing
from idealista.report import (
    build_table,
    emit_report,
    format_eur,
    format_pct,
    listing_url,
    market_summary,
    osc8,
    render_report,
    supports_hyperlinks,
    write_csv,
)


class FakeMarket:
    def __init__(self, city_reference: Reference | None):
        self.city_reference = city_reference


def city_ref() -> Reference:
    return Reference(
        area="Madrid",
        level="city",
        eur_m2=8000,
        sample_size=29,
        iqr_pct=54.82,
        confidence=0.429,
    )


def make(**overrides) -> Listing:
    data = dict(
        ad_id="123",
        url="https://www.idealista.com/inmueble/123/",
        title="Piso en venta",
        price=305_000,
        size_m2=50.0,
        rooms=2,
        floor="3ª",
        elevator=True,
        neighborhood="Sol",
        district="Centro",
        city="Madrid",
        price_m2=6100.0,
        area_level="city",
        discount_pct=-12.3,
        score=72.5,
        band="great deal",
    )
    data.update(overrides)
    return Listing(**data)


def test_formatting_helpers():
    assert format_eur(305_000) == "305,000 €"
    assert format_eur(None) == "?"
    assert format_pct(-12.34) == "-12.3%"
    assert format_pct(3.0) == "+3.0%"
    assert format_pct(None) == "n/a"
    assert listing_url("https://www.idealista.com/inmueble/98765/") == (
        "https://www.idealista.com/inmueble/98765/"
    )
    assert listing_url("https://www.idealista.com/venta-viviendas/") == (
        "https://www.idealista.com/venta-viviendas/"
    )


class FakeStream:
    def __init__(self, tty: bool):
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


def test_osc8_sequence():
    assert osc8("https://example.com", "open") == (
        "\x1b]8;;https://example.com\x1b\\open\x1b]8;;\x1b\\"
    )


def test_hyperlinks_require_a_tty_and_known_terminal(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "test-session")
    assert supports_hyperlinks(FakeStream(True)) is True
    assert supports_hyperlinks(FakeStream(False)) is False


def test_build_table_short_links_are_clickable_and_narrow():
    best = make(ad_id="1", url="https://www.idealista.com/inmueble/1/")
    table = build_table([best], link_style="short")

    assert osc8("https://www.idealista.com/inmueble/1/") in table
    assert "L001" not in table
    assert "open" in table


def test_build_table_full_links_have_no_escape_codes():
    best = make(ad_id="1", url="https://www.idealista.com/inmueble/1/")
    table = build_table([best], link_style="full")

    assert "https://www.idealista.com/inmueble/1/" in table
    assert "\x1b]8" not in table


def test_build_table_auto_uses_detected_mode(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "test-session")
    best = make(ad_id="1", url="https://www.idealista.com/inmueble/1/")

    assert "\x1b]8" in build_table(
        [best], link_style="auto", stream=FakeStream(True)
    )
    assert "\x1b]8" not in build_table(
        [best], link_style="auto", stream=FakeStream(False)
    )


def test_build_table_orders_listings_and_respects_top_n():
    best = make(ad_id="1", url="https://www.idealista.com/inmueble/1/", score=90.0)
    second = make(ad_id="2", url="https://www.idealista.com/inmueble/2/", score=70.0)
    unscored = make(ad_id="3", url="https://www.idealista.com/inmueble/3/", score=None)

    table = build_table([second, unscored, best], top_n=2)

    assert "Score" in table and "vs area" in table and "Link" in table
    assert "/inmueble/1/" in table and "/inmueble/2/" in table
    assert "/inmueble/3/" not in table
    assert table.index("/inmueble/1/") < table.index("/inmueble/2/")
    assert "90.0" in table and "70.0" in table


def test_build_table_handles_missing_values():
    listing = make(
        price=None,
        size_m2=None,
        rooms=None,
        floor="",
        elevator=None,
        neighborhood="",
        district="",
        city="Madrid",
        price_m2=None,
        discount_pct=None,
        score=None,
        band="no reference",
    )
    table = build_table([listing])
    assert "n/a" in table and "no reference" in table and "Madrid" in table


def test_market_summary_reports_budget_and_counts():
    listings = [
        make(ad_id="1", score=80.0, band="great deal"),
        make(ad_id="2", score=60.0, band="fair", area_level="city"),
    ]
    listings.append(make(ad_id="3", score=None, band="no reference", area_level=""))
    summary = market_summary(listings, FakeMarket(city_ref()), FilterConfig(max_price=305_000))

    assert "Madrid 8,000 €/m²" in summary
    assert "n=29" in summary and "IQR 54.82%" in summary and "confidence 0.43" in summary
    assert "~38 m²" in summary
    assert "Matched 3 listings: 2 scored, 1 without a reference." in summary
    assert "great deal 1, fair 1" in summary
    assert "Reference scope: barrio 0, distrito 0, city 2, manual 0" in summary


def test_market_summary_without_reference():
    summary = market_summary([make(score=None)], FakeMarket(None), FilterConfig())
    assert "not enough comparable listings" in summary
    assert "Matched 1 listings: 0 scored, 1 without a reference." in summary


def test_market_summary_warns_when_benchmark_cannot_score_matches():
    summary = market_summary(
        [make(score=None, band="no reference")],
        FakeMarket(city_ref()),
        FilterConfig(),
        min_comparables=8,
    )
    assert "warning: benchmark n=29" in summary
    assert "each match needs 8 leave-one-out peers" in summary


def test_render_report_includes_summary_and_table():
    cfg = Config()
    cfg.output.link_style = "short"
    text = render_report([make()], FakeMarket(city_ref()), cfg)
    assert "Market benchmark" in text
    assert "Ranked listings (top 1 of 1)" in text
    assert osc8("https://www.idealista.com/inmueble/123/") in text


def test_write_csv_uses_expected_name_and_row(tmp_path):
    listing = make(tags=["ascensor", "terraza"])
    path = write_csv([listing], tmp_path, now=datetime(2026, 11, 9, 14, 30))

    assert path.name == "madrid_20261109_1430.csv"
    text = path.read_text(encoding="utf-8-sig")
    header, *rows = text.splitlines()
    assert header.startswith("ad_id,url,title,price")
    assert ",ascensor; terraza," in text
    assert len(rows) == 1


def test_write_csv_does_not_overwrite_same_minute(tmp_path):
    now = datetime(2026, 11, 9, 14, 30)
    first = write_csv([make()], tmp_path, now=now)
    second = write_csv([make()], tmp_path, now=now)

    assert first.name == "madrid_20261109_1430.csv"
    assert second.name == "madrid_20261109_1430_02.csv"
    assert first.exists() and second.exists()
    assert first.stat().st_size == second.stat().st_size


def test_emit_report_prints_and_writes_csv(tmp_path, capsys):
    cfg = Config()
    cfg.output.dir = str(tmp_path)
    printed: list[str] = []
    path = emit_report(
        [make()],
        FakeMarket(city_ref()),
        cfg,
        now=datetime(2026, 11, 9, 14, 30),
        out=printed.append,
    )

    assert path is not None and path.exists()
    output = "\n".join(printed)
    assert "Market benchmark" in output
    assert "CSV:" in output
    assert capsys.readouterr().out == ""


def test_emit_report_respects_write_csv_flag(tmp_path):
    cfg = Config()
    cfg.output.dir = str(tmp_path)
    cfg.output.write_csv = False
    printed: list[str] = []
    path = emit_report([make()], FakeMarket(city_ref()), cfg, out=printed.append)
    assert path is None
    assert list(tmp_path.iterdir()) == []
