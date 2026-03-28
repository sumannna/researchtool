"""
config.json の読み書きユーティリティ
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

DEFAULT_CONFIG: dict = {
    "keepa_api_key": "",
    "claude_api_key": "",
    "serper_api_key": "",
    "rakuten_api_key": "",
    "yahoo_client_id": "",
    "forbidden_keywords": [],
    "auto_research": {
        "enabled": False,
        "interval_minutes": 60,
        "batch_size": 5,
    },
    "window": {
        "width": 1200,
        "height": 800,
    },
    "last_rank_min": 100,
    "last_rank_max": 5000,
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        return merged
    except Exception as e:
        logger.error("config.json 読み込み失敗: %s", e)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("config.json 保存失敗: %s", e)


def get_key(key: str) -> str:
    return load_config().get(key, "") or ""


def update_key(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)
