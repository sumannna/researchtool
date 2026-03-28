"""
割引入力フォーム
割引額（円）または割引率（%）を入力すると on_change コールバックを呼ぶ。
"""
from __future__ import annotations
from typing import Callable
import customtkinter as ctk
from frontend.styles import font, BG_SECONDARY, TEXT_SECONDARY


class DiscountInput(ctk.CTkFrame):
    """
    割引額・割引率の入力フォーム。

    on_change(amount_yen: float, rate_pct: float) が変更のたびに呼ばれる。
    """

    def __init__(
        self,
        master,
        on_change: Callable[[float, float], None] | None = None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", BG_SECONDARY)
        super().__init__(master, **kwargs)
        self._on_change = on_change
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="割引設定", font=font(12, bold=True)
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(6, 2))

        # 割引額
        ctk.CTkLabel(self, text="割引額", font=font(11), text_color=TEXT_SECONDARY).grid(
            row=1, column=0, padx=(8, 2), pady=4, sticky="e"
        )
        self._amount_var = ctk.StringVar(value="0")
        self._amount_entry = ctk.CTkEntry(
            self, textvariable=self._amount_var, width=80, font=font(11)
        )
        self._amount_entry.grid(row=1, column=1, padx=2, pady=4)
        ctk.CTkLabel(self, text="円", font=font(11)).grid(row=1, column=2, padx=(2, 12))

        # 割引率
        ctk.CTkLabel(self, text="割引率", font=font(11), text_color=TEXT_SECONDARY).grid(
            row=1, column=3, padx=(4, 2), pady=4, sticky="e"
        )
        self._rate_var = ctk.StringVar(value="0")
        self._rate_entry = ctk.CTkEntry(
            self, textvariable=self._rate_var, width=80, font=font(11)
        )
        self._rate_entry.grid(row=1, column=4, padx=2, pady=4)
        ctk.CTkLabel(self, text="%", font=font(11)).grid(row=1, column=5, padx=(2, 8))

        # トレース登録
        self._amount_var.trace_add("write", self._notify)
        self._rate_var.trace_add("write", self._notify)

    def _notify(self, *_):
        try:
            amount = float(self._amount_var.get() or 0)
        except ValueError:
            amount = 0.0
        try:
            rate = float(self._rate_var.get() or 0)
        except ValueError:
            rate = 0.0
        rate = max(0.0, min(rate, 100.0))
        if self._on_change:
            self._on_change(amount, rate)

    @property
    def amount(self) -> float:
        try:
            return float(self._amount_var.get() or 0)
        except ValueError:
            return 0.0

    @property
    def rate(self) -> float:
        try:
            v = float(self._rate_var.get() or 0)
            return max(0.0, min(v, 100.0))
        except ValueError:
            return 0.0

    def reset(self):
        self._amount_var.set("0")
        self._rate_var.set("0")
