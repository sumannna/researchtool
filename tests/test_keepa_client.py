"""
keepa_client のユニットテスト
実 Keepa API は呼ばず、keepa ライブラリ自体をモックする。
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from backend.keepa_client import get_amazon_current_price, reset_api

MOCK_DIR = Path(__file__).parent / "mock_responses"


def load_mock(name: str) -> dict:
    with open(MOCK_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# ── get_amazon_current_price ──────────────────────

class TestGetAmazonCurrentPrice:
    def test_最新価格が正の値なら返す(self):
        product = {"csv": [[1609459200, 1980, 1620000000, 2200]]}
        assert get_amazon_current_price(product) == 2200.0

    def test_最新価格が_minus1_ならNone(self):
        product = {"csv": [[1609459200, 1980, 1620000000, -1]]}
        assert get_amazon_current_price(product) is None

    def test_csvが空リストならNone(self):
        product = {"csv": []}
        assert get_amazon_current_price(product) is None

    def test_csvがNoneならNone(self):
        product = {"csv": None}
        assert get_amazon_current_price(product) is None

    def test_csvフィールドがないならNone(self):
        product = {}
        assert get_amazon_current_price(product) is None

    def test_csv_0がNoneならNone(self):
        product = {"csv": [None]}
        assert get_amazon_current_price(product) is None

    def test_csv_0が要素1件のみならNone(self):
        product = {"csv": [[1609459200]]}
        assert get_amazon_current_price(product) is None

    def test_正の価格はfloatで返す(self):
        product = {"csv": [[1609459200, 980]]}
        price = get_amazon_current_price(product)
        assert isinstance(price, float)
        assert price == 980.0

    def test_モックJSONのproductはAmazon価格なし(self):
        product = load_mock("keepa_product.json")
        price = get_amazon_current_price(product)
        assert price is None  # csv[0]の末尾が -1

    def test_価格0はNoneではなく0を返す(self):
        # 0円はありえないが、keepa の仕様上 0 は有効値と扱う
        product = {"csv": [[1609459200, 0]]}
        price = get_amazon_current_price(product)
        # 0 は falsy だが -1 ではないので None ではない
        assert price == 0.0


# ── reset_api ─────────────────────────────────────

class TestResetApi:
    def test_reset後にAPIインスタンスがNoneになる(self):
        import backend.keepa_client as kc
        # ダミーのインスタンスをセット
        kc._api = MagicMock()
        reset_api()
        assert kc._api is None

    def test_APIキー未設定でget_productを呼ぶとValueError(self):
        import asyncio
        import backend.keepa_client as kc
        reset_api()
        with patch("backend.keepa_client.get_key", return_value=""):
            with pytest.raises(ValueError, match="Keepa APIキー"):
                asyncio.run(kc.get_product("B0TEST0001"))
