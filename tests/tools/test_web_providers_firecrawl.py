"""Focused tests for the bounded Firecrawl timeout disposition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class TestFirecrawlScrapeTimeout:
    def test_env_timeout_wins(self, monkeypatch):
        from plugins.web.firecrawl import provider

        monkeypatch.setenv("HERMES_FIRECRAWL_SCRAPE_TIMEOUT", "12.5")
        assert provider._resolve_scrape_timeout() == 12.5

    def test_config_timeout_is_used_when_env_is_invalid(self, monkeypatch):
        from hermes_cli import config
        from plugins.web.firecrawl import provider

        monkeypatch.setenv("HERMES_FIRECRAWL_SCRAPE_TIMEOUT", "not-a-number")
        monkeypatch.setattr(config, "load_config", lambda: {"web": {}})
        monkeypatch.setattr(
            config,
            "cfg_get",
            lambda cfg, *keys: 23.5 if keys == ("web", "firecrawl", "scrape_timeout") else None,
        )
        assert provider._resolve_scrape_timeout() == 23.5

    @pytest.mark.asyncio
    async def test_default_scrape_request_keeps_both_formats(self, monkeypatch):
        from plugins.web.firecrawl import provider

        calls = []

        class FakeClient:
            def scrape(self, **kwargs):
                calls.append(kwargs)
                return {
                    "markdown": "content",
                    "metadata": {"title": "Example", "sourceURL": kwargs["url"]},
                }

        monkeypatch.setattr(provider, "_get_firecrawl_client", lambda: FakeClient())
        monkeypatch.setattr(provider, "check_website_access", lambda url: None)
        monkeypatch.setattr(provider, "is_safe_url", lambda url: True)
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False)

        result = await provider.FirecrawlWebSearchProvider().extract(["https://example.com"])
        assert result[0]["content"] == "content"
        assert calls[0]["formats"] == ["markdown", "html"]
