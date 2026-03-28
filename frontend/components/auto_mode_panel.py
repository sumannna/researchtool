"""
自動リサーチモード設定・カウントダウン表示
"""
from __future__ import annotations
import threading
from datetime import datetime, timedelta
from typing import Callable
import customtkinter as ctk
from backend.config_loader import load_config, save_config
from frontend.styles import font, BG_SECONDARY, TEXT_SECONDARY, SUCCESS, WARNING


class AutoModePanel(ctk.CTkFrame):
    """
    自動リサーチモードの ON/OFF・設定・カウントダウン表示。
    on_execute が呼ばれると1バッチ分のリサーチを実行する想定。
    """

    def __init__(
        self,
        master,
        on_execute: Callable[[int], None] | None = None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", BG_SECONDARY)
        super().__init__(master, **kwargs)
        self._on_execute = on_execute
        self._timer: threading.Timer | None = None
        self._next_run: datetime | None = None
        self._running = False
        self._build()
        self._load_config()

    # ── UI 構築 ────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="自動リサーチ", font=font(13, bold=True)
        ).pack(anchor="w", padx=10, pady=(10, 4))

        # ON/OFF スイッチ
        switch_row = ctk.CTkFrame(self, fg_color="transparent")
        switch_row.pack(fill="x", padx=10, pady=2)
        self._switch_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            switch_row,
            text="自動モード",
            variable=self._switch_var,
            font=font(12),
            command=self._on_toggle,
        ).pack(side="left")

        # 設定行（間隔・件数）
        cfg_row = ctk.CTkFrame(self, fg_color="transparent")
        cfg_row.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(cfg_row, text="間隔", font=font(11), text_color=TEXT_SECONDARY).pack(
            side="left"
        )
        self._interval_var = ctk.StringVar(value="60")
        ctk.CTkEntry(cfg_row, textvariable=self._interval_var, width=52, font=font(11)).pack(
            side="left", padx=(2, 2)
        )
        ctk.CTkLabel(cfg_row, text="分　件数", font=font(11), text_color=TEXT_SECONDARY).pack(
            side="left"
        )
        self._batch_var = ctk.StringVar(value="5")
        ctk.CTkEntry(cfg_row, textvariable=self._batch_var, width=40, font=font(11)).pack(
            side="left", padx=(2, 2)
        )
        ctk.CTkLabel(cfg_row, text="件", font=font(11), text_color=TEXT_SECONDARY).pack(
            side="left"
        )

        # カウントダウン
        self._countdown_label = ctk.CTkLabel(
            self, text="自動モード: 停止中", font=font(11), text_color=TEXT_SECONDARY
        )
        self._countdown_label.pack(anchor="w", padx=10, pady=2)

        # 今すぐ実行ボタン
        ctk.CTkButton(
            self,
            text="今すぐ実行",
            font=font(11),
            height=28,
            command=self._execute_now,
        ).pack(anchor="w", padx=10, pady=(2, 8))

    # ── 内部ロジック ───────────────────────────────

    def _load_config(self):
        config = load_config()
        ar = config.get("auto_research", {})
        self._switch_var.set(ar.get("enabled", False))
        self._interval_var.set(str(ar.get("interval_minutes", 60)))
        self._batch_var.set(str(ar.get("batch_size", 5)))
        if ar.get("enabled"):
            self._start_timer()

    def _save_config(self):
        config = load_config()
        config["auto_research"] = {
            "enabled": self._switch_var.get(),
            "interval_minutes": self._interval_minutes,
            "batch_size": self._batch_size,
        }
        save_config(config)

    @property
    def _interval_minutes(self) -> int:
        try:
            return max(1, int(self._interval_var.get()))
        except ValueError:
            return 60

    @property
    def _batch_size(self) -> int:
        try:
            return max(1, min(20, int(self._batch_var.get())))
        except ValueError:
            return 5

    def _on_toggle(self):
        if self._switch_var.get():
            self._start_timer()
        else:
            self._stop_timer()
        self._save_config()

    def _start_timer(self):
        self._running = True
        interval_sec = self._interval_minutes * 60
        self._next_run = datetime.now() + timedelta(seconds=interval_sec)
        self._schedule_timer(interval_sec)
        self._update_countdown()

    def _stop_timer(self):
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._next_run = None
        self._countdown_label.configure(
            text="自動モード: 停止中", text_color=TEXT_SECONDARY
        )

    def _schedule_timer(self, seconds: float):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(seconds, self._on_timer_fire)
        self._timer.daemon = True
        self._timer.start()

    def _on_timer_fire(self):
        # threading.Timer のスレッドから呼ばれるため、UI 操作は after() でメインスレッドへ渡す
        if not self._running:
            return
        # 次回スケジュール（先に設定してから実行を依頼）
        interval_sec = self._interval_minutes * 60
        self._next_run = datetime.now() + timedelta(seconds=interval_sec)
        self._schedule_timer(interval_sec)
        # バッチ件数をメインスレッドへ渡して一括実行を依頼
        n = self._batch_size
        if self._on_execute:
            self.after(0, lambda: self._on_execute(n))

    def _execute_now(self):
        """スケジュールをリセットして即時実行"""
        if self._running:
            self._stop_timer()
            self._start_timer()
        n = self._batch_size
        if self._on_execute:
            self.after(0, lambda: self._on_execute(n))

    def _update_countdown(self):
        """1秒ごとにカウントダウンラベルを更新する"""
        if not self._running or self._next_run is None:
            return
        remaining = self._next_run - datetime.now()
        total_sec = int(remaining.total_seconds())
        if total_sec < 0:
            total_sec = 0
        mm, ss = divmod(total_sec, 60)
        self._countdown_label.configure(
            text=f"次回自動実行まで {mm:02d}:{ss:02d}",
            text_color=SUCCESS,
        )
        # after は tk スレッドで呼ぶ必要があるため after() を使う
        self.after(1000, self._update_countdown)

    def stop(self):
        """アプリ終了時に呼ぶ"""
        self._stop_timer()
