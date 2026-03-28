"""
SQLite CRUD・スキーマ定義
"""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "sedori.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """DBスキーマを初期化する"""
    with db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS asin_cache (
                asin          TEXT PRIMARY KEY,
                category      TEXT,
                sales_rank    INTEGER,
                fetched_at    DATETIME,
                picked        BOOLEAN DEFAULT 0,
                excluded      BOOLEAN DEFAULT 0,
                exclude_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS research_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                asin          TEXT,
                title         TEXT,
                jan_code      TEXT,
                amazon_price  REAL,
                best_buy_url  TEXT,
                best_buy_price REAL,
                roi           REAL,
                profit_rate   REAL,
                researched_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS cache_fetch_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                category      TEXT,
                fetched_at    DATETIME,
                asin_count    INTEGER
            );
        """)
    logger.info("DB初期化完了: %s", DB_PATH)


def bulk_upsert_asins(asins: list[tuple[str, str, int]]):
    """(asin, category, sales_rank) のリストを一括挿入・更新"""
    now = datetime.now().isoformat()
    with db_connection() as conn:
        conn.executemany(
            """
            INSERT INTO asin_cache (asin, category, sales_rank, fetched_at, picked, excluded)
            VALUES (?, ?, ?, ?, 0, 0)
            ON CONFLICT(asin) DO UPDATE SET
                category=excluded.category,
                sales_rank=excluded.sales_rank,
                fetched_at=excluded.fetched_at
            """,
            [(a, c, r, now) for a, c, r in asins],
        )


def pick_random_asin(rank_min: int, rank_max: int) -> str | None:
    """ランク範囲内から未ピックアップ・未除外のASINをランダムに1件取得し picked フラグを立てる"""
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT asin FROM asin_cache
            WHERE sales_rank BETWEEN ? AND ?
              AND picked = 0
              AND excluded = 0
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (rank_min, rank_max),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE asin_cache SET picked = 1 WHERE asin = ?", (row["asin"],)
            )
            return row["asin"]
        return None


def mark_excluded(asin: str, reason: str):
    """ASINを恒久除外フラグ付きで更新する"""
    with db_connection() as conn:
        conn.execute(
            "UPDATE asin_cache SET excluded = 1, exclude_reason = ? WHERE asin = ?",
            (reason, asin),
        )


def save_research_result(result: dict):
    """リサーチ結果をDBに保存する"""
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO research_results
                (asin, title, jan_code, amazon_price, best_buy_url, best_buy_price,
                 roi, profit_rate, researched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["asin"],
                result.get("title"),
                result.get("jan_code"),
                result.get("amazon_price"),
                result.get("best_buy_url"),
                result.get("best_buy_price"),
                result.get("roi"),
                result.get("profit_rate"),
                datetime.now().isoformat(),
            ),
        )


def log_cache_fetch(category: str, asin_count: int):
    """キャッシュ取得ログを記録する"""
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO cache_fetch_log (category, fetched_at, asin_count) VALUES (?, ?, ?)",
            (category, datetime.now().isoformat(), asin_count),
        )


def get_last_fetch(category: str) -> datetime | None:
    """カテゴリの最終キャッシュ取得日時を返す"""
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT fetched_at FROM cache_fetch_log
            WHERE category = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (category,),
        ).fetchone()
        if row:
            return datetime.fromisoformat(row["fetched_at"])
        return None
