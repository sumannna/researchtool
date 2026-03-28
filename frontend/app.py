"""
メインウィンドウ・画面遷移
asyncio ループを daemon スレッドで起動し、
asyncio.run_coroutine_threadsafe でバックエンドを非同期呼び出しする。
"""
from __future__ import annotations

import asyncio
import logging
import threading

import customtkinter as ctk

import backend
from backend import asin_cache
from backend.config_loader import load_config, save_config
from frontend.styles import (
    font, BG_PRIMARY, BG_SECONDARY, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS, WARNING, DANGER,
)
from frontend.components.filter_panel import FilterPanel
from frontend.components.discount_input import DiscountInput
from frontend.components.auto_mode_panel import AutoModePanel
from frontend.components.result_list import ResultList
from frontend.components.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


# ── asyncio バックグラウンドループ ──────────────────
_async_loop = asyncio.new_event_loop()

def _run_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_loop_thread = threading.Thread(target=_run_loop, args=(_async_loop,), daemon=True)
_loop_thread.start()


def submit_async(coro):
    """コルーチンをバックグラウンドループに投げる"""
    return asyncio.run_coroutine_threadsafe(coro, _async_loop)


# ── メインアプリ ────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("せどりリサーチツール")
        config = load_config()
        w = config.get("window", {}).get("width", 1200)
        h = config.get("window", {}).get("height", 800)
        self.geometry(f"{w}x{h}")
        self.configure(fg_color=BG_PRIMARY)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._is_researching = False
        self._research_queue = 0   # 残り実行件数（バッチ管理用）
        self._build_ui()
        self._filter_panel.load_from_config()
        logger.info("アプリ起動")

    # ── UI 構築 ─────────────────────────────────────

    def _build_ui(self):
        # ── トップバー ──
        top = ctk.CTkFrame(self, fg_color=BG_SECONDARY, height=48, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(
            top, text="せどりリサーチツール", font=font(18, bold=True), text_color=ACCENT
        ).pack(side="left", padx=16)
        ctk.CTkButton(
            top, text="⚙ 設定", font=font(12), width=80,
            fg_color="transparent", hover_color="gray30",
            command=self._open_settings,
        ).pack(side="right", padx=8)

        # ── メインエリア（左サイドバー + 右コンテンツ）──
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # 左サイドバー
        sidebar = ctk.CTkScrollableFrame(main, width=280, fg_color=BG_SECONDARY)
        sidebar.pack(side="left", fill="y", padx=(8, 4), pady=8)

        # フィルターパネル
        self._filter_panel = FilterPanel(sidebar, fg_color="transparent")
        self._filter_panel.pack(fill="x", pady=(0, 8))

        # キャッシュ更新ボタン
        ctk.CTkButton(
            sidebar, text="🔄 キャッシュ更新", font=font(12),
            fg_color="gray30", hover_color="gray40",
            command=self._refresh_cache,
        ).pack(fill="x", pady=(0, 4))

        # リサーチ実行ボタン
        self._research_btn = ctk.CTkButton(
            sidebar, text="▶ リサーチ実行", font=font(13, bold=True),
            fg_color=ACCENT, hover_color="#c73652", height=40,
            command=lambda: self._start_batch(1),
        )
        self._research_btn.pack(fill="x", pady=4)

        # 割引入力
        self._discount = DiscountInput(
            sidebar, on_change=self._on_discount_change, fg_color="transparent"
        )
        self._discount.pack(fill="x", pady=8)

        # 自動リサーチパネル
        self._auto_panel = AutoModePanel(
            sidebar, on_execute=self._start_batch, fg_color="transparent"
        )
        self._auto_panel.pack(fill="x", pady=4)

        # 右エリア（結果リスト）
        right = ctk.CTkFrame(main, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        self._result_list = ResultList(right)
        self._result_list.pack(fill="both", expand=True)

        # ── ステータスバー ──
        self._status_bar = ctk.CTkFrame(self, fg_color=BG_SECONDARY, height=32, corner_radius=0)
        self._status_bar.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(
            self._status_bar, text="準備完了", font=font(11), text_color=TEXT_SECONDARY
        )
        self._status_label.pack(side="left", padx=12)

    # ── アクション ───────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self)

    def _set_status(self, text: str, color: str = TEXT_SECONDARY):
        self._status_label.configure(text=text, text_color=color)

    def _set_busy(self, busy: bool):
        self._is_researching = busy
        state = "disabled" if busy else "normal"
        self._research_btn.configure(state=state)

    def _refresh_cache(self):
        """選択カテゴリのASINキャッシュを更新する"""
        categories = self._filter_panel.selected_categories
        if not categories:
            self._set_status("カテゴリを1つ以上選択してください", WARNING)
            return
        self._set_status("キャッシュ更新中...", TEXT_SECONDARY)
        self._set_busy(True)

        future = submit_async(asin_cache.refresh_if_needed(categories))

        def _done(fut):
            try:
                fut.result()
                self.after(0, lambda: self._set_status("キャッシュ更新完了", SUCCESS))
            except Exception as e:
                logger.error("キャッシュ更新エラー: %s", e)
                self.after(0, lambda: self._set_status(f"キャッシュ更新エラー: {e}", DANGER))
            finally:
                self.after(0, lambda: self._set_busy(False))

        future.add_done_callback(_done)

    def _start_batch(self, n: int):
        """
        n 件のリサーチをキューに積んで開始する。
        手動ボタン（n=1）・自動モード（n=batch_size）共通のエントリーポイント。
        既にリサーチ中の場合はキューに追加するだけで、完了後に自動的に続きを処理する。
        """
        self._research_queue += n
        if not self._is_researching:
            self._run_next()

    def _run_next(self):
        """キューから1件取り出してリサーチを実行する"""
        if self._research_queue <= 0:
            return
        self._research_queue -= 1
        rank_min = self._filter_panel.rank_min
        rank_max = self._filter_panel.rank_max
        self._filter_panel.save_to_config()
        self._set_busy(True)
        remaining = self._research_queue
        self._set_status(
            f"リサーチ中... (残り {remaining} 件)" if remaining else "リサーチ中...",
            TEXT_SECONDARY,
        )

        future = submit_async(backend.run_research(rank_min, rank_max))

        def _done(fut):
            try:
                result = fut.result()
                self.after(0, lambda: self._on_research_done(result))
            except ValueError as e:
                # APIキー未設定など — キューをクリアして中断
                self._research_queue = 0
                self.after(0, lambda: self._set_status(f"設定エラー: {e}", DANGER))
                self.after(0, lambda: self._set_busy(False))
            except Exception as e:
                logger.error("リサーチエラー: %s", e)
                self.after(0, lambda: self._set_status(f"エラー: {e}", DANGER))
                self.after(0, lambda: self._set_busy(False))

        future.add_done_callback(_done)

    def _on_research_done(self, result: "backend.ResearchResult | None"):
        self._set_busy(False)
        if result is None:
            self._set_status("リサーチ対象なし（フィルター除外またはASIN不足）", WARNING)
        else:
            self._result_list.add_result(
                result,
                discount_amount=self._discount.amount,
                discount_rate=self._discount.rate,
            )
            status = f"完了: {result.title[:40]}…  ROI: {result.roi:.1f}%"
            color = SUCCESS if result.roi >= 20 else (WARNING if result.roi >= 0 else DANGER)
            self._set_status(status, color)
        # キューに残りがあれば次を実行
        if self._research_queue > 0:
            self._run_next()

    def _on_discount_change(self, amount: float, rate: float):
        self._result_list.apply_discount_all(amount, rate)

    # ── 終了処理 ─────────────────────────────────────

    def _on_close(self):
        self._auto_panel.stop()
        # ウィンドウサイズを保存
        config = load_config()
        config["window"] = {"width": self.winfo_width(), "height": self.winfo_height()}
        save_config(config)
        _async_loop.call_soon_threadsafe(_async_loop.stop)
        self.destroy()
