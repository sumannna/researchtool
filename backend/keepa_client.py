"""
Keepa API 通信・トークン管理
公式 keepa Python ライブラリを使用する（直接 HTTP リクエストは書かない）
"""
import asyncio
import logging
import time

import keepa

from .config_loader import get_key

logger = logging.getLogger(__name__)

# モジュールレベルのシングルトン API インスタンス
_api: "keepa.Keepa | None" = None


def _get_api() -> "keepa.Keepa":
    global _api
    if _api is None:
        api_key = get_key("keepa_api_key")
        if not api_key:
            raise ValueError(
                "Keepa APIキーが設定されていません。設定ダイアログから入力してください。"
            )
        _api = keepa.Keepa(api_key)
        logger.info("Keepa APIクライアント初期化完了")
    return _api


def reset_api():
    """APIキー更新時にシングルトンをリセットする"""
    global _api
    _api = None
    logger.info("Keepa APIクライアントをリセットしました")


def _ensure_tokens():
    """
    トークン残量を確認し、不足している場合は待機する。
    keepa ライブラリの wait=True（デフォルト）で自動制御されるが、
    明示的に残量が少ない場合は追加で待機する。
    """
    try:
        api = _get_api()
        remaining = api.tokens_left
        logger.debug("Keepaトークン残量: %d", remaining)
        if remaining < 10:
            logger.warning(
                "Keepaトークン残量不足 (残量: %d)。60秒待機します。", remaining
            )
            time.sleep(60)
    except ValueError:
        raise
    except Exception as e:
        logger.warning("トークン残量確認エラー: %s", e)


def _query_product_sync(asin: str) -> "dict | None":
    """商品詳細を同期的に取得する（内部使用）"""
    try:
        _ensure_tokens()
        api = _get_api()
        products = api.query(
            asin,
            domain="JP",
            offers=20,           # 出品者情報を取得（Amazon出品チェックに必要）
            only_live_offers=True,  # 現在出品中のもののみ
            history=False,       # 価格履歴不要でトークン節約
            stats=30,            # 直近30日の統計
        )
        if products:
            return products[0]
        return None
    except ValueError:
        raise
    except Exception as e:
        logger.error("Keepa商品取得エラー (ASIN: %s): %s", asin, e)
        return None


def _best_sellers_sync(category_node_id: int) -> list[str]:
    """ベストセラーASINリストを同期的に取得する（内部使用）"""
    try:
        _ensure_tokens()
        api = _get_api()
        asin_list = api.best_sellers_query(category=category_node_id, domain="JP")
        result = list(asin_list) if asin_list is not None else []
        logger.info(
            "ベストセラー取得完了: カテゴリ=%d, %d件", category_node_id, len(result)
        )
        return result
    except ValueError:
        raise
    except Exception as e:
        logger.error(
            "Keepaベストセラー取得エラー (カテゴリ: %d): %s", category_node_id, e
        )
        return []


async def get_product(asin: str) -> "dict | None":
    """商品詳細を非同期で取得する"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _query_product_sync, asin)


async def best_sellers_query(category_node_id: int) -> list[str]:
    """ベストセラーASINリストを非同期で取得する"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _best_sellers_sync, category_node_id)


def get_amazon_current_price(product: dict) -> "float | None":
    """
    Keepa商品データから現在の Amazon 販売価格（円）を返す。

    Keepa CSV[0] = Amazon価格履歴。
    フォーマット: [ts1, price1, ts2, price2, ...] （奇数インデックスが価格）
    -1 は「現在出品なし」を意味する。
    Amazon.co.jp (JP) ドメインでは価格はそのまま円単位。
    """
    csv = product.get("csv")
    if not csv or not csv[0]:
        return None
    amazon_csv = csv[0]
    if len(amazon_csv) < 2:
        return None
    # 最後の要素が最新価格
    latest_price = amazon_csv[-1]
    if latest_price == -1:
        return None
    return float(latest_price)
