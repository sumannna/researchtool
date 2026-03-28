"""
エントリーポイント（exe 起動時）
"""
import logging
import logging.handlers
import sys
from pathlib import Path


def _setup_logging():
    log_path = Path(__file__).parent / "app.log"
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    root_logger.addHandler(stream)


def main():
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== せどりリサーチツール 起動 ===")

    try:
        from backend.db import init_db
        init_db()
    except Exception as e:
        logger.error("DB初期化エラー: %s", e)

    try:
        from frontend.app import App
        app = App()
        app.mainloop()
    except Exception as e:
        logger.critical("アプリ起動エラー: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
