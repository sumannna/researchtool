# -*- coding: utf-8 -*-
"""
jan_resolver unit tests
External APIs (Serper / Claude) are replaced with mocks.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from backend.jan_resolver import (
    shorten_product_name,
    build_user_prompt,
    search_serper,
    extract_jan_with_claude,
    resolve_jan,
)

MOCK_DIR = Path(__file__).parent / "mock_responses"


def load_serper_mock() -> list:
    with open(MOCK_DIR / "serper_result.json", encoding="utf-8") as f:
        return json.load(f)["organic"]


def run(coro):
    return asyncio.run(coro)


# ── shorten_product_name ──────────────────────────

class TestShortenProductName:
    def test_removes_kakko_brackets(self):
        result = shorten_product_name("test product [Amazon exclusive] 500ml")
        assert "[" not in result
        assert "Amazon exclusive" not in result

    def test_removes_angle_brackets(self):
        # Japanese full-width angle brackets
        title = "\u30c6\u30b9\u30c8\u5546\u54c1 \u300a\u304a\u5f97\u30bb\u30c3\u30c8\u300b 500ml"
        result = shorten_product_name(title)
        assert len(result) <= len(title)

    def test_keeps_volume_notation_in_parens(self):
        result = shorten_product_name("Brand A product (500ml x24)")
        assert "500ml" in result

    def test_removes_descriptive_parens(self):
        result = shorten_product_name("Brand A product (trial set)")
        assert "trial set" not in result

    def test_truncates_to_30_chars(self):
        long_title = "Brand A Test Product Super Quality Premium Domestic Organic 500ml x24"
        result = shorten_product_name(long_title)
        assert len(result) <= 30

    def test_short_title_unchanged(self):
        short = "Brand A product"
        result = shorten_product_name(short)
        assert result == short

    def test_collapses_extra_spaces(self):
        title = "Brand A   Test   Product"
        result = shorten_product_name(title)
        assert "  " not in result

    def test_real_amazon_title_example(self):
        # Simulates a realistic Amazon JP title with Japanese brackets
        title = (
            "\u82b1\u738b \u30d3\u30aa\u30ec u \u6ce1\u30cf\u30f3\u30c9\u30bd\u30fc\u30d7 "
            "\u672c\u4f53 250ml "
            "\u3010\u533b\u85ac\u90e8\u5916\u54c1\u3011 "
            "[\u7121\u6dfb\u52a0\u30fb\u4f4e\u523a\u6fc3]"
        )
        result = shorten_product_name(title)
        assert len(result) <= 30

    def test_removes_japanese_square_brackets(self):
        title = "\u30c6\u30b9\u30c8\u5546\u54c1 \u3010\u304a\u5f97\u30bb\u30c3\u30c8\u3011 500ml"
        result = shorten_product_name(title)
        assert "\u3010" not in result
        assert "\u304a\u5f97\u30bb\u30c3\u30c8" not in result


# ── build_user_prompt ─────────────────────────────

class TestBuildUserPrompt:
    def test_prompt_contains_product_title(self):
        results = [{"title": "test", "snippet": "JAN: 1234567890123"}]
        prompt = build_user_prompt("Test product", results)
        assert "Test product" in prompt

    def test_prompt_contains_snippet(self):
        results = [{"title": "Title1", "snippet": "Snippet1"}]
        prompt = build_user_prompt("Product A", results)
        assert "Snippet1" in prompt
        assert "Title1" in prompt

    def test_uses_max_5_results(self):
        results = [{"title": f"t{i}", "snippet": f"s{i}"} for i in range(10)]
        prompt = build_user_prompt("Product A", results)
        assert "[5]" in prompt
        assert "[6]" not in prompt

    def test_empty_snippets_no_crash(self):
        results = [{"title": "", "snippet": ""}]
        prompt = build_user_prompt("Product A", results)
        assert "Product A" in prompt


# ── search_serper ─────────────────────────────────

class TestSearchSerper:
    def test_no_api_key_returns_empty_list(self):
        with patch("backend.jan_resolver.get_key", return_value=""):
            result = run(search_serper("test JAN"))
        assert result == []

    def test_success_returns_up_to_5_results(self):
        mock_data = load_serper_mock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"organic": mock_data}
        mock_resp.raise_for_status = MagicMock()
        mock_inner = MagicMock()
        mock_inner.post = AsyncMock(return_value=mock_resp)

        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = run(search_serper("test JAN"))
        assert len(result) <= 5

    def test_api_error_returns_empty_list(self):
        mock_inner = MagicMock()
        mock_inner.post = AsyncMock(side_effect=Exception("network error"))
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = run(search_serper("test JAN"))
        assert result == []


# ── extract_jan_with_claude ───────────────────────

class TestExtractJanWithClaude:
    def _mock_claude_cls(self, response_text: str):
        msg = MagicMock()
        msg.content = [MagicMock(text=response_text)]
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=msg)
        return MagicMock(return_value=client)

    def test_returns_13_digit_jan(self):
        results = [{"title": "t", "snippet": "JAN: 4901234567890"}]
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("anthropic.AsyncAnthropic", self._mock_claude_cls("4901234567890")):
            jan = run(extract_jan_with_claude("Product", results))
        assert jan == "4901234567890"

    def test_not_found_returns_none(self):
        results = [{"title": "t", "snippet": "no info"}]
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("anthropic.AsyncAnthropic", self._mock_claude_cls("NOT_FOUND")):
            jan = run(extract_jan_with_claude("Product", results))
        assert jan is None

    def test_extracts_jan_embedded_in_text(self):
        results = [{"title": "t", "snippet": "s"}]
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("anthropic.AsyncAnthropic",
                   self._mock_claude_cls("The JAN code is 4901234567890.")):
            jan = run(extract_jan_with_claude("Product", results))
        assert jan == "4901234567890"

    def test_no_api_key_returns_none(self):
        results = [{"title": "t", "snippet": "s"}]
        with patch("backend.jan_resolver.get_key", return_value=""):
            jan = run(extract_jan_with_claude("Product", results))
        assert jan is None

    def test_empty_results_returns_none(self):
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"):
            jan = run(extract_jan_with_claude("Product", []))
        assert jan is None

    def test_api_error_returns_none(self):
        results = [{"title": "t", "snippet": "s"}]
        client = MagicMock()
        client.messages.create = AsyncMock(side_effect=Exception("API Error"))
        with patch("backend.jan_resolver.get_key", return_value="DUMMY"), \
             patch("anthropic.AsyncAnthropic", return_value=client):
            jan = run(extract_jan_with_claude("Product", results))
        assert jan is None


# ── resolve_jan integration ───────────────────────

class TestResolveJan:
    def test_jan_found_on_first_try(self):
        serper = load_serper_mock()
        with patch("backend.jan_resolver.search_serper", AsyncMock(return_value=serper)), \
             patch("backend.jan_resolver.extract_jan_with_claude",
                   AsyncMock(return_value="4901234567890")):
            jan = run(resolve_jan("test product brand 500ml x24"))
        assert jan == "4901234567890"

    def test_retries_with_jan_keyword_when_empty(self):
        serper = load_serper_mock()
        # 1st call empty, 2nd call has results
        with patch("backend.jan_resolver.search_serper",
                   AsyncMock(side_effect=[[], serper])), \
             patch("backend.jan_resolver.extract_jan_with_claude",
                   AsyncMock(return_value="4901234567890")):
            jan = run(resolve_jan("test product"))
        assert jan == "4901234567890"

    def test_returns_none_when_not_found(self):
        with patch("backend.jan_resolver.search_serper", AsyncMock(return_value=[])), \
             patch("backend.jan_resolver.extract_jan_with_claude",
                   AsyncMock(return_value=None)):
            jan = run(resolve_jan("unknown product"))
        assert jan is None
