"""
フィルター1（Amazon直接出品チェック）・フィルター2（禁止キーワードチェック）
"""
import logging

from . import db
from .config_loader import load_config

logger = logging.getLogger(__name__)


def is_amazon_selling(product: dict) -> bool:
    """
    Amazon.co.jp が現在出品中かどうかを判定する。

    方法1: csv[0]（Amazon価格履歴）の最新値が -1 でなければ出品中。
    方法2: offers の isAmazon フラグ（より確実）。
    """
    # 方法1: Amazon価格履歴の最新値チェック
    csv_list = product.get("csv") or []
    csv_amazon = csv_list[0] if csv_list else None
    if csv_amazon and len(csv_amazon) >= 2:
        latest_price = csv_amazon[-1]
        if latest_price != -1:
            return True

    # 方法2: liveOffersOrder + offers の isAmazon フラグ
    live_order = product.get("liveOffersOrder") or []
    offers = product.get("offers") or []
    for idx in live_order:
        if isinstance(idx, int) and idx < len(offers):
            if offers[idx].get("isAmazon", False):
                return True

    return False


def has_forbidden_keyword(product: dict, keywords: list[str]) -> "str | None":
    """
    禁止キーワードをチェックする。
    商品タイトルまたはカテゴリに含まれる場合、そのキーワードを返す。
    """
    if not keywords:
        return None

    title = (product.get("title") or "").lower()
    category_list = product.get("categoryTree") or []
    category_text = " ".join(
        c.get("name", "") for c in category_list if isinstance(c, dict)
    ).lower()
    check_text = f"{title} {category_text}"

    for kw in keywords:
        if kw.lower() in check_text:
            logger.info("禁止キーワード検出: '%s' (タイトル: %.50s)", kw, title)
            return kw
    return None


async def apply_filters(asin: str, product: dict) -> tuple[bool, "str | None"]:
    """
    フィルター1・2を順次適用する。
    除外対象は DB に記録して以降のピックアップ対象から恒久除外する。

    Returns:
        (passed, exclude_reason)
        passed=True の場合は全フィルター通過。
    """
    # フィルター1: Amazon出品チェック
    if is_amazon_selling(product):
        logger.info("フィルター1除外 (Amazon出品中): %s", asin)
        db.mark_excluded(asin, "amazon_selling")
        return False, "amazon_selling"

    # フィルター2: 禁止キーワードチェック
    config = load_config()
    keywords = config.get("forbidden_keywords") or []
    found_kw = has_forbidden_keyword(product, keywords)
    if found_kw:
        logger.info("フィルター2除外 (禁止キーワード '%s'): %s", found_kw, asin)
        db.mark_excluded(asin, "forbidden_keyword")
        return False, "forbidden_keyword"

    return True, None
