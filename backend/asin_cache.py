"""
ASINキャッシュ取得・DB保存・週次スケジューリング
"""
import logging
from datetime import datetime, timedelta

from . import db
from . import keepa_client

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_DAYS = 7

# カテゴリ名 → Keepa node ID マッピング（Amazon.co.jp）
CATEGORY_MAP: dict[str, int] = {
    "ドラッグストア":       2189494051,
    "ビューティー":         57035011,
    "ホーム＆キッチン":     3828871,
    "食品・飲料・お酒":     2189514051,
    "ペット用品":           2201396051,
    "スポーツ＆アウトドア": 14304371,
    "おもちゃ":             13312011,
    "文房具・オフィス用品": 2189707051,
    "DIY・工具":            2189641051,
    "カー用品":             2151999051,
}


def needs_refresh(category_name: str) -> bool:
    """週次更新が必要かどうかを判定する"""
    last_fetch = db.get_last_fetch(category_name)
    if last_fetch is None:
        return True
    return datetime.now() - last_fetch > timedelta(days=REFRESH_INTERVAL_DAYS)


async def refresh_cache(category_node_id: int, category_name: str):
    """
    指定カテゴリの ASINキャッシュを Keepa から取得して DB に保存する。
    ベストセラーランキングのインデックスを sales_rank として使用する。
    """
    logger.info("ASINキャッシュ更新開始: %s (node_id=%d)", category_name, category_node_id)
    asin_list = await keepa_client.best_sellers_query(category_node_id)
    if not asin_list:
        logger.warning("ASINリストが空です: %s", category_name)
        return

    # インデックス（1始まり）を sales_rank として保存
    records = [
        (asin, category_name, idx + 1) for idx, asin in enumerate(asin_list)
    ]
    db.bulk_upsert_asins(records)
    db.log_cache_fetch(category_name, len(asin_list))
    logger.info("キャッシュ更新完了: %s, %d件保存", category_name, len(asin_list))


async def refresh_if_needed(category_names: list[str]):
    """
    週次更新が必要なカテゴリのみ順次更新する。
    カテゴリ名が CATEGORY_MAP にない場合はスキップする。
    """
    for name in category_names:
        if not needs_refresh(name):
            logger.debug("キャッシュ更新不要: %s", name)
            continue
        node_id = CATEGORY_MAP.get(name)
        if node_id is None:
            logger.warning("不明なカテゴリ名: %s", name)
            continue
        await refresh_cache(node_id, name)


async def pick_asin(rank_min: int, rank_max: int) -> "str | None":
    """
    ランク範囲内から未ピックアップ・未除外の ASIN をランダムに1件選ぶ。
    選択後に picked フラグを立てて再度選ばれないようにする。
    """
    asin = db.pick_random_asin(rank_min, rank_max)
    if asin is None:
        logger.warning(
            "ランク範囲 %d-%d に利用可能な ASIN がありません。"
            "先にキャッシュを更新してください。",
            rank_min,
            rank_max,
        )
    return asin
