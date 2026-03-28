"""
楽天・Yahoo!ショッピング API 価格取得
直列実行（仕様 §2-5 に準拠）
"""
import logging
import re

import httpx

from .config_loader import get_key

logger = logging.getLogger(__name__)

# セット品検出パターン
_SET_PATTERNS = [
    r"(\d+)個セット",
    r"(\d+)本セット",
    r"(\d+)枚セット",
    r"(\d+)袋セット",
    r"(\d+)箱セット",
    r"×\s*(\d+)",
    r"(\d+)個入り?",
    r"(\d+)本入り?",
    r"(\d+)枚入り?",
    r"【(\d+)個】",
    r"【(\d+)本】",
    r"【(\d+)枚】",
    r"\((\d+)個\)",
    r"\((\d+)本\)",
]


def detect_set_count(name: str) -> int:
    """
    商品名からセット数を検出する。
    セット品でない場合（または検出失敗）は 1 を返す。
    """
    for pattern in _SET_PATTERNS:
        match = re.search(pattern, name)
        if match:
            count = int(match.group(1))
            if 2 <= count <= 100:  # 妥当な範囲のみ採用
                return count
    return 1


# ──────────────────────────────────────────────
# 楽天 商品検索 API
# ──────────────────────────────────────────────
def _parse_rakuten_item(item: dict) -> dict:
    name = item.get("itemName", "")
    price = float(item.get("itemPrice", 0))
    url = item.get("itemUrl", "")
    shop_name = item.get("shopName", "")
    set_count = detect_set_count(name)
    return {
        "shop_name": shop_name,
        "unit_price": price / set_count,
        "is_set": set_count > 1,
        "set_count": set_count,
        "url": url,
    }


async def fetch_rakuten_prices(jan_code: str) -> list[dict]:
    """
    楽天 APIで JANコードを検索し、単価の安い順に最大5件返す。
    APIキー未設定時は空リストを返す（クラッシュしない）。
    """
    api_key = get_key("rakuten_api_key")
    if not api_key:
        logger.warning("楽天 APIキーが未設定です")
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706",
                params={
                    "applicationId": api_key,
                    "keyword": jan_code,
                    "hits": 30,
                    "sort": "+itemPrice",
                    "formatVersion": 2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("Items", [])
            parsed = [_parse_rakuten_item(item) for item in items]
            parsed.sort(key=lambda x: x["unit_price"])
            logger.info("楽天 価格取得: %d件", len(parsed[:5]))
            return parsed[:5]
    except Exception as e:
        logger.error("楽天 API エラー: %s", e)
        return []


# ──────────────────────────────────────────────
# Yahoo!ショッピング API
# ──────────────────────────────────────────────
def _parse_yahoo_item(item: dict) -> dict:
    name = item.get("name", "")
    price = float(item.get("price", 0))
    url = item.get("url", "")
    seller = item.get("seller") or {}
    shop_name = seller.get("name", "") if isinstance(seller, dict) else ""
    set_count = detect_set_count(name)
    return {
        "shop_name": shop_name,
        "unit_price": price / set_count,
        "is_set": set_count > 1,
        "set_count": set_count,
        "url": url,
    }


async def fetch_yahoo_prices(jan_code: str) -> list[dict]:
    """
    Yahoo!ショッピング API で JANコードを検索し、単価の安い順に最大5件返す。
    APIキー未設定時は空リストを返す（クラッシュしない）。
    """
    client_id = get_key("yahoo_client_id")
    if not client_id:
        logger.warning("Yahoo APIキーが未設定です")
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
                params={
                    "appid": client_id,
                    "jan_code": jan_code,
                    "results": 30,
                    "sort": "+price",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("hits", [])
            parsed = [_parse_yahoo_item(item) for item in items]
            parsed.sort(key=lambda x: x["unit_price"])
            logger.info("Yahoo 価格取得: %d件", len(parsed[:5]))
            return parsed[:5]
    except Exception as e:
        logger.error("Yahoo API エラー: %s", e)
        return []
