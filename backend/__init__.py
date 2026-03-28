"""
backend パッケージ
フロントエンドへの公開インターフェースを定義する。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from . import asin_cache
from . import db
from . import filter_engine
from . import jan_resolver
from . import keepa_client
from . import price_fetcher
from . import roi_calculator

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# データクラス（フロントエンドへの型契約）
# ──────────────────────────────────────────────
@dataclass
class PriceItem:
    shop_name: str
    unit_price: float       # セット品は割り算済みの単価
    is_set: bool
    set_count: int
    url: str


@dataclass
class ResearchResult:
    asin: str
    title: str
    jan_code: str | None
    amazon_price: float
    amazon_url: str
    rakuten_items: list[PriceItem]   # 最大5件
    yahoo_items: list[PriceItem]     # 最大5件
    roi: float
    profit_rate: float
    researched_at: datetime


# ──────────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────────
def _to_price_items(raw_list: list[dict]) -> list[PriceItem]:
    return [
        PriceItem(
            shop_name=r["shop_name"],
            unit_price=r["unit_price"],
            is_set=r["is_set"],
            set_count=r["set_count"],
            url=r["url"],
        )
        for r in raw_list
    ]


# ──────────────────────────────────────────────
# メインエントリーポイント
# ──────────────────────────────────────────────
async def run_research(rank_min: int, rank_max: int) -> ResearchResult | None:
    """
    1件のリサーチを実行して結果を返す。

    フロー:
      1. DB 初期化（未初期化でもクラッシュしない）
      2. ランク範囲内からランダムに ASIN をピックアップ
      3. Keepa から商品詳細を取得
      4. フィルター1（Amazon出品）・フィルター2（禁止キーワード）を適用
      5. JANコードを取得
      6. 楽天・Yahoo から仕入れ価格を取得（直列）
      7. ROI・利益率を計算
      8. 結果を DB に保存して返す

    Returns:
        ResearchResult。除外・エラー時は None。
    """
    db.init_db()

    # ステップ1: ランダムピックアップ
    asin = await asin_cache.pick_asin(rank_min, rank_max)
    if asin is None:
        logger.warning("利用可能な ASIN がありません。キャッシュを更新してください。")
        return None

    logger.info("リサーチ開始: ASIN=%s", asin)

    # ステップ2: Keepa 商品詳細取得
    product = await keepa_client.get_product(asin)
    if product is None:
        logger.error("商品データ取得失敗: ASIN=%s", asin)
        return None

    title = product.get("title") or ""
    amazon_url = f"https://www.amazon.co.jp/dp/{asin}"
    amazon_price = keepa_client.get_amazon_current_price(product) or 0.0

    # ステップ3: フィルター適用
    passed, reason = await filter_engine.apply_filters(asin, product)
    if not passed:
        logger.info("フィルター除外: ASIN=%s (理由=%s)", asin, reason)
        return None

    # ステップ4: JANコード取得
    jan_code = await jan_resolver.resolve_jan(title)

    # ステップ5: 仕入れ価格リサーチ（直列実行）
    rakuten_raw: list[dict] = []
    yahoo_raw: list[dict] = []
    if jan_code:
        rakuten_raw = await price_fetcher.fetch_rakuten_prices(jan_code)
        yahoo_raw = await price_fetcher.fetch_yahoo_prices(jan_code)

    rakuten_items = _to_price_items(rakuten_raw)
    yahoo_items = _to_price_items(yahoo_raw)

    # 最安値アイテムを仕入れ価格として使用
    all_items = sorted(rakuten_items + yahoo_items, key=lambda x: x.unit_price)
    best_buy_price = all_items[0].unit_price if all_items else 0.0
    best_buy_url = all_items[0].url if all_items else ""

    # ステップ6: ROI・利益率計算
    fba_fee = roi_calculator.calculate_fba_fee(product)
    referral_fee = roi_calculator.get_referral_fee(product, int(amazon_price))
    _profit, profit_rate, roi = roi_calculator.calculate_profit(
        amazon_price, best_buy_price, referral_fee, fba_fee
    )

    result = ResearchResult(
        asin=asin,
        title=title,
        jan_code=jan_code,
        amazon_price=amazon_price,
        amazon_url=amazon_url,
        rakuten_items=rakuten_items,
        yahoo_items=yahoo_items,
        roi=roi,
        profit_rate=profit_rate,
        researched_at=datetime.now(),
    )

    # ステップ7: DB 保存
    db.save_research_result(
        {
            "asin": asin,
            "title": title,
            "jan_code": jan_code,
            "amazon_price": amazon_price,
            "best_buy_url": best_buy_url,
            "best_buy_price": best_buy_price,
            "roi": roi,
            "profit_rate": profit_rate,
        }
    )

    logger.info(
        "リサーチ完了: ASIN=%s, ROI=%.1f%%, 利益率=%.1f%%", asin, roi, profit_rate
    )
    return result
