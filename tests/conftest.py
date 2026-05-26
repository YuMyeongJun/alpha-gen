from __future__ import annotations

import importlib
import os

import pytest


def _reload_config() -> None:
    import config

    importlib.reload(config)


@pytest.fixture(autouse=True)
def isolate_backend_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep pytest independent from developer .env (KIS/Claude/live settings)."""
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("AUTO_MOCK_ON_MISSING_KIS", "true")
    monkeypatch.setenv("IS_REAL_TRADING", "false")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "false")
    monkeypatch.setenv("ALPHA_GEN_STAGE", "mock")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("KIS_APP_KEY", "여기에_APP_KEY")
    monkeypatch.setenv("KIS_APP_SECRET", "여기에_APP_SECRET")
    monkeypatch.setenv("ACCOUNT_NO", "여기에_계좌번호_앞8자리")
    monkeypatch.setenv("ACCOUNT_CODE", "01")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "여기에_Claude_API_키")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    _reload_config()
    from market_adapters import reset_adapters

    reset_adapters()
    yield
    reset_adapters()
    _reload_config()


def isolated_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "MOCK_MODE": "true",
            "AUTO_MOCK_ON_MISSING_KIS": "true",
            "IS_REAL_TRADING": "false",
            "ALLOW_LIVE_TRADING": "false",
            "ALPHA_GEN_STAGE": "mock",
            "KIS_APP_KEY": "여기에_APP_KEY",
            "KIS_APP_SECRET": "여기에_APP_SECRET",
            "ACCOUNT_NO": "여기에_계좌번호_앞8자리",
            "ANTHROPIC_API_KEY": "여기에_Claude_API_키",
        }
    )
    return env
