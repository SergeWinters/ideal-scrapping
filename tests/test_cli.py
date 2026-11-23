import pytest

from idealista import cli
from idealista.browser import ChallengeError
from idealista.config import Config


class FakeBrowser:
    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


def test_main_wires_pipeline_and_overrides(monkeypatch):
    captured = {}

    def fake_pipeline(cfg, session):
        captured["cfg"] = cfg
        captured["session"] = session

    monkeypatch.setattr(cli, "BrowserSession", FakeBrowser)
    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)

    code = cli.main(
        [
            "--max-price",
            "400000",
            "--max-details",
            "3",
            "--top",
            "7",
            "--links",
            "short",
            "--cache",
            "tmp/cache.json",
            "--no-cache",
        ]
    )

    assert code == 0
    cfg = captured["cfg"]
    assert isinstance(captured["session"], FakeBrowser)
    assert cfg.filters.max_price == 400_000
    assert cfg.search.max_details == 3
    assert cfg.output.top_n == 7
    assert cfg.output.link_style == "short"
    assert cfg.search.cache_path == "tmp/cache.json"
    assert cfg.search.use_cache is False


def test_main_returns_3_on_challenge(monkeypatch):
    def fail_pipeline(cfg, session):
        raise ChallengeError("solve captcha")

    monkeypatch.setattr(cli, "BrowserSession", FakeBrowser)
    monkeypatch.setattr(cli, "run_pipeline", fail_pipeline)

    assert cli.main([]) == 3


def test_main_returns_1_on_runtime_error(monkeypatch):
    def fail_pipeline(cfg, session):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "BrowserSession", FakeBrowser)
    monkeypatch.setattr(cli, "run_pipeline", fail_pipeline)

    assert cli.main([]) == 1


def test_main_debug_reraises(monkeypatch):
    def fail_pipeline(cfg, session):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "BrowserSession", FakeBrowser)
    monkeypatch.setattr(cli, "run_pipeline", fail_pipeline)

    with pytest.raises(RuntimeError, match="boom"):
        cli.main(["--debug"])


def test_invalid_config_returns_2(monkeypatch):
    monkeypatch.setattr(cli, "BrowserSession", FakeBrowser)
    assert cli.main(["--config", "does-not-exist.yaml"]) == 2


def test_invalid_link_style_is_rejected():
    cfg = Config()
    cfg.output.link_style = "fancy"
    with pytest.raises(ValueError, match="output.link_style"):
        cfg.validate()
