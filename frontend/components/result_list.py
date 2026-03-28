"""
リサーチ結果リスト（スクロール対応・上から積み上げ表示）
"""
from __future__ import annotations
from datetime import datetime
import customtkinter as ctk
from backend import ResearchResult, PriceItem
from frontend.styles import (
    font, BG_CARD, BG_CARD_ALT, BG_SECONDARY,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_LINK,
    SUCCESS, WARNING, DANGER, ACCENT,
)
from frontend.components.url_label import UrlLabel


class ResultCard(ctk.CTkFrame):
    """1件のリサーチ結果を表示するカード"""

    def __init__(self, master, result: ResearchResult, **kwargs):
        kwargs.setdefault("fg_color", BG_CARD)
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)
        self._result = result
        self._amazon_price = result.amazon_price
        # 費用 = 販売価格 × (1 - profit_rate/100) - best_buy_price
        best = self._best_buy_price(result)
        implied = self._amazon_price * (1 - result.profit_rate / 100) - best if self._amazon_price > 0 else 0
        self._implied_fees = max(0.0, implied)
        self._build()

    # ── 構築 ─────────────────────────────────────

    def _build(self):
        r = self._result
        pad = {"padx": 12, "pady": 3}

        # ヘッダー行（タイトル + 日時）
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", **pad)
        ctk.CTkLabel(
            hdr,
            text=f"[{r.asin}]  {r.title[:60]}{'…' if len(r.title) > 60 else ''}",
            font=font(12, bold=True),
            text_color=TEXT_PRIMARY,
            wraplength=600,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            hdr,
            text=r.researched_at.strftime("%m/%d %H:%M"),
            font=font(10),
            text_color=TEXT_SECONDARY,
        ).pack(side="right")

        # Amazon 価格 + URL
        amz_row = ctk.CTkFrame(self, fg_color="transparent")
        amz_row.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(
            amz_row, text="Amazon: ", font=font(11), text_color=TEXT_SECONDARY
        ).pack(side="left")
        ctk.CTkLabel(
            amz_row,
            text=f"¥{r.amazon_price:,.0f}" if r.amazon_price else "価格不明",
            font=font(12, bold=True),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))
        UrlLabel(amz_row, url=r.amazon_url, text="Amazonで見る").pack(side="left")

        # JAN コード
        if r.jan_code:
            ctk.CTkLabel(
                self,
                text=f"JAN: {r.jan_code}",
                font=font(11),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=12, pady=1)
        else:
            ctk.CTkLabel(
                self,
                text="⚠ JANコード取得不可 — 仕入れ価格リサーチ不可",
                font=font(11),
                text_color=WARNING,
            ).pack(anchor="w", padx=12, pady=1)

        # 価格テーブル
        if r.rakuten_items or r.yahoo_items:
            self._price_frame = ctk.CTkFrame(self, fg_color=BG_CARD_ALT, corner_radius=6)
            self._price_frame.pack(fill="x", padx=12, pady=(4, 2))
            self._price_rows: list[tuple[ctk.CTkLabel, PriceItem]] = []
            self._build_price_table(r.rakuten_items, "楽天")
            self._build_price_table(r.yahoo_items, "Yahoo")
        else:
            self._price_frame = None
            self._price_rows = []

        # ROI・利益率
        roi_row = ctk.CTkFrame(self, fg_color="transparent")
        roi_row.pack(fill="x", padx=12, pady=(4, 8))

        self._profit_label = ctk.CTkLabel(roi_row, text="", font=font(11))
        self._profit_label.pack(side="left", padx=(0, 16))
        self._roi_label = ctk.CTkLabel(roi_row, text="", font=font(12, bold=True))
        self._roi_label.pack(side="left", padx=(0, 12))
        self._rate_label = ctk.CTkLabel(roi_row, text="", font=font(12, bold=True))
        self._rate_label.pack(side="left")

        self.apply_discount(0.0, 0.0)  # 初期表示

    def _build_price_table(self, items: list[PriceItem], source: str):
        if not items:
            return
        ctk.CTkLabel(
            self._price_frame,
            text=f"  {source}",
            font=font(11, bold=True),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=8, pady=(4, 1))
        for item in items:
            row = ctk.CTkFrame(self._price_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            price_lbl = ctk.CTkLabel(row, text="", font=font(11), width=90, anchor="e")
            price_lbl.pack(side="left", padx=(0, 6))
            set_info = f"({item.set_count}個セット→単価)" if item.is_set else ""
            ctk.CTkLabel(
                row,
                text=f"{item.shop_name[:20]}  {set_info}",
                font=font(10),
                text_color=TEXT_SECONDARY,
            ).pack(side="left", padx=(0, 6))
            UrlLabel(row, url=item.url, text="購入").pack(side="left")
            self._price_rows.append((price_lbl, item))

    # ── 割引適用 ──────────────────────────────────

    def apply_discount(self, amount_yen: float, rate_pct: float):
        """割引を適用して表示価格・ROI・利益率を更新する"""
        factor = 1.0 - rate_pct / 100.0

        # 価格ラベル更新
        for lbl, item in self._price_rows:
            discounted = item.unit_price * factor - amount_yen
            discounted = max(0.0, discounted)
            lbl.configure(text=f"¥{discounted:,.0f}")

        # ROI・利益率再計算
        r = self._result
        if not r.jan_code:
            self._roi_label.configure(text="ROI: -", text_color=TEXT_SECONDARY)
            self._rate_label.configure(text="利益率: -", text_color=TEXT_SECONDARY)
            self._profit_label.configure(text="", text_color=TEXT_SECONDARY)
            return

        best_orig = self._best_buy_price(r)
        best_disc = max(0.0, best_orig * factor - amount_yen) if best_orig > 0 else 0.0

        if best_disc > 0 and self._amazon_price > 0:
            profit = self._amazon_price - best_disc - self._implied_fees
            profit_rate = profit / self._amazon_price * 100
            roi = profit / best_disc * 100
        else:
            profit = profit_rate = roi = 0.0

        profit_color = SUCCESS if profit > 0 else DANGER
        self._profit_label.configure(
            text=f"利益額: ¥{profit:,.0f}", text_color=profit_color
        )
        roi_color = SUCCESS if roi >= 20 else (WARNING if roi >= 0 else DANGER)
        self._roi_label.configure(text=f"ROI: {roi:.1f}%", text_color=roi_color)
        rate_color = SUCCESS if profit_rate >= 15 else (WARNING if profit_rate >= 0 else DANGER)
        self._rate_label.configure(text=f"利益率: {profit_rate:.1f}%", text_color=rate_color)

    @staticmethod
    def _best_buy_price(r: ResearchResult) -> float:
        all_items = r.rakuten_items + r.yahoo_items
        if not all_items:
            return 0.0
        return min(i.unit_price for i in all_items)


class ResultList(ctk.CTkScrollableFrame):
    """リサーチ結果を上から積み上げ表示するスクロールリスト"""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._cards: list[ResultCard] = []

    def add_result(self, result: ResearchResult, discount_amount: float = 0.0, discount_rate: float = 0.0):
        """先頭に結果カードを追加する"""
        card = ResultCard(self, result)
        # before=None は TclError を起こすため、既存カードがある場合のみ before を渡す
        if self._cards:
            card.pack(fill="x", pady=4, before=self._cards[0])
        else:
            card.pack(fill="x", pady=4)
        card.apply_discount(discount_amount, discount_rate)
        self._cards.insert(0, card)

    def apply_discount_all(self, amount: float, rate: float):
        """全カードに割引を適用する"""
        for card in self._cards:
            card.apply_discount(amount, rate)

    def clear(self):
        for card in self._cards:
            card.destroy()
        self._cards.clear()
