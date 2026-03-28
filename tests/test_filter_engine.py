"""
filter_engine のユニットテスト
外部API・DB呼び出しはモックで代替する。
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from backend.filter_engine import is_amazon_selling, has_forbidden_keyword, apply_filters

MOCK_DIR = Path(__file__).parent / "mock_responses"


def load_mock(name: str) -> dict:
    with open(MOCK_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# ── is_amazon_selling ─────────────────────────────

class TestIsAmazonSelling:
    def test_csv_が_minus1_ならAmazon出品なし(self):
        product = {"csv": [[1609459200, -1]], "liveOffersOrder": [], "offers": []}
        assert is_amazon_selling(product) is False

    def test_csv_に正の価格があればAmazon出品中(self):
        product = {"csv": [[1609459200, 1980]], "liveOffersOrder": [], "offers": []}
        assert is_amazon_selling(product) is True

    def test_isAmazonフラグがTrueならAmazon出品中(self):
        product = {
            "csv": [[1609459200, -1]],
            "liveOffersOrder": [0],
            "offers": [{"isAmazon": True, "isFBA": False}],
        }
        assert is_amazon_selling(product) is True

    def test_isAmazonフラグがFalseでcsvもマイナス1ならFalse(self):
        product = {
            "csv": [[1609459200, -1]],
            "liveOffersOrder": [0],
            "offers": [{"isAmazon": False, "isFBA": True}],
        }
        assert is_amazon_selling(product) is False

    def test_csv_が空のとき(self):
        product = {"csv": [], "liveOffersOrder": [], "offers": []}
        assert is_amazon_selling(product) is False

    def test_csv_がNoneのとき(self):
        product = {"csv": None, "liveOffersOrder": [], "offers": []}
        assert is_amazon_selling(product) is False

    def test_フィールドが全くないとき(self):
        assert is_amazon_selling({}) is False

    def test_liveOffersOrderのインデックスが範囲外でもクラッシュしない(self):
        product = {
            "csv": [[1609459200, -1]],
            "liveOffersOrder": [99],
            "offers": [{"isAmazon": True}],
        }
        # index 99 は offers に存在しない → クラッシュしない
        assert is_amazon_selling(product) is False

    def test_モックJSONのproductはAmazon出品なし(self):
        product = load_mock("keepa_product.json")
        assert is_amazon_selling(product) is False


# ── has_forbidden_keyword ──────────────────────────

class TestHasForbiddenKeyword:
    def test_タイトルにキーワードが含まれる(self):
        product = {"title": "第2類医薬品 テスト商品", "categoryTree": []}
        assert has_forbidden_keyword(product, ["第2類医薬品"]) == "第2類医薬品"

    def test_カテゴリにキーワードが含まれる(self):
        product = {
            "title": "普通の商品",
            "categoryTree": [{"name": "劇物・危険物"}],
        }
        assert has_forbidden_keyword(product, ["劇物"]) == "劇物"

    def test_キーワードが含まれない(self):
        product = {"title": "普通のシャンプー", "categoryTree": [{"name": "ビューティー"}]}
        assert has_forbidden_keyword(product, ["劇物", "危険物"]) is None

    def test_大文字小文字を無視する(self):
        product = {"title": "KIKEN BUTSU 商品", "categoryTree": []}
        assert has_forbidden_keyword(product, ["kiken butsu"]) == "kiken butsu"

    def test_キーワードリストが空のとき(self):
        product = {"title": "第2類医薬品 テスト", "categoryTree": []}
        assert has_forbidden_keyword(product, []) is None

    def test_タイトルがNoneでもクラッシュしない(self):
        product = {"title": None, "categoryTree": []}
        assert has_forbidden_keyword(product, ["医薬品"]) is None

    def test_categoryTreeがNoneでもクラッシュしない(self):
        product = {"title": "普通の商品", "categoryTree": None}
        assert has_forbidden_keyword(product, ["劇物"]) is None


# ── apply_filters (async) ─────────────────────────

class TestApplyFilters:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_Amazon出品中は除外される(self):
        product = {"csv": [[1609459200, 1980]], "liveOffersOrder": [], "offers": []}
        with patch("backend.filter_engine.db.mark_excluded") as mock_excl:
            passed, reason = self._run(apply_filters("B0TEST0001", product))
        assert passed is False
        assert reason == "amazon_selling"
        mock_excl.assert_called_once_with("B0TEST0001", "amazon_selling")

    def test_禁止キーワードにヒットすると除外される(self):
        product = {
            "csv": [[1609459200, -1]],
            "liveOffersOrder": [],
            "offers": [],
            "title": "第2類医薬品 テスト",
            "categoryTree": [],
        }
        config = {"forbidden_keywords": ["第2類医薬品"]}
        with patch("backend.filter_engine.db.mark_excluded") as mock_excl, \
             patch("backend.filter_engine.load_config", return_value=config):
            passed, reason = self._run(apply_filters("B0TEST0002", product))
        assert passed is False
        assert reason == "forbidden_keyword"
        mock_excl.assert_called_once_with("B0TEST0002", "forbidden_keyword")

    def test_全フィルター通過(self):
        product = {
            "csv": [[1609459200, -1]],
            "liveOffersOrder": [],
            "offers": [],
            "title": "普通の商品",
            "categoryTree": [],
        }
        config = {"forbidden_keywords": []}
        with patch("backend.filter_engine.db.mark_excluded") as mock_excl, \
             patch("backend.filter_engine.load_config", return_value=config):
            passed, reason = self._run(apply_filters("B0TEST0003", product))
        assert passed is True
        assert reason is None
        mock_excl.assert_not_called()

    def test_フィルター1が除外されたらフィルター2は実行されない(self):
        """Amazon出品中の商品に対して禁止キーワードチェックを実行しないことを確認"""
        product = {
            "csv": [[1609459200, 1980]],
            "liveOffersOrder": [],
            "offers": [],
            "title": "第2類医薬品 Amazon直売商品",
            "categoryTree": [],
        }
        config = {"forbidden_keywords": ["第2類医薬品"]}
        with patch("backend.filter_engine.db.mark_excluded") as mock_excl, \
             patch("backend.filter_engine.load_config", return_value=config) as mock_cfg:
            passed, reason = self._run(apply_filters("B0TEST0004", product))
        assert passed is False
        assert reason == "amazon_selling"
        # load_config は呼ばれないはず（フィルター1で早期リターン）
        mock_cfg.assert_not_called()
