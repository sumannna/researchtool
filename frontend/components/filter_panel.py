"""
フィルター設定パネル
ランク範囲・カテゴリ選択を提供する。
"""
from __future__ import annotations
import customtkinter as ctk
from frontend.styles import font, BG_SECONDARY, TEXT_SECONDARY

CATEGORY_LIST = [
    ("ドラッグストア",       2189494051),
    ("ビューティー",         57035011),
    ("ホーム＆キッチン",     3828871),
    ("食品・飲料・お酒",     2189514051),
    ("ペット用品",           2201396051),
    ("スポーツ＆アウトドア", 14304371),
    ("おもちゃ",             13312011),
    ("文房具・オフィス用品", 2189707051),
    ("DIY・工具",            2189641051),
    ("カー用品",             2151999051),
]


class FilterPanel(ctk.CTkFrame):
    """ランク範囲入力 + カテゴリチェックボックス"""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", BG_SECONDARY)
        super().__init__(master, **kwargs)
        self._cat_vars: dict[int, ctk.BooleanVar] = {}
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="リサーチ設定", font=font(13, bold=True)
        ).pack(anchor="w", padx=10, pady=(10, 4))

        # ── ランク範囲 ──────────────────────────────
        rank_frame = ctk.CTkFrame(self, fg_color="transparent")
        rank_frame.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(rank_frame, text="ランク範囲", font=font(11), text_color=TEXT_SECONDARY).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 2)
        )
        ctk.CTkLabel(rank_frame, text="最小", font=font(11)).grid(row=1, column=0, padx=(0, 4))
        self._rank_min = ctk.CTkEntry(rank_frame, width=70, font=font(11))
        self._rank_min.insert(0, "100")
        self._rank_min.grid(row=1, column=1, padx=2)

        ctk.CTkLabel(rank_frame, text="〜", font=font(11)).grid(row=1, column=2, padx=4)

        ctk.CTkLabel(rank_frame, text="最大", font=font(11)).grid(row=1, column=3, padx=(0, 4))
        self._rank_max = ctk.CTkEntry(rank_frame, width=70, font=font(11))
        self._rank_max.insert(0, "5000")
        self._rank_max.grid(row=1, column=4, padx=2)

        # ── カテゴリ ────────────────────────────────
        ctk.CTkLabel(
            self, text="カテゴリ", font=font(11), text_color=TEXT_SECONDARY
        ).pack(anchor="w", padx=10, pady=(10, 2))

        cat_scroll = ctk.CTkScrollableFrame(self, height=200, fg_color="transparent")
        cat_scroll.pack(fill="x", padx=10, pady=(0, 6))

        for name, node_id in CATEGORY_LIST:
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(
                cat_scroll, text=name, variable=var, font=font(11)
            ).pack(anchor="w", pady=1)
            self._cat_vars[node_id] = var

    # ── 公開プロパティ ────────────────────────────

    @property
    def rank_min(self) -> int:
        try:
            return max(1, int(self._rank_min.get()))
        except ValueError:
            return 100

    @property
    def rank_max(self) -> int:
        try:
            return max(self.rank_min, int(self._rank_max.get()))
        except ValueError:
            return 5000

    @property
    def selected_categories(self) -> list[str]:
        """チェックされているカテゴリ名のリスト"""
        name_map = {node_id: name for name, node_id in CATEGORY_LIST}
        return [
            name_map[nid] for nid, var in self._cat_vars.items() if var.get()
        ]

    def save_to_config(self):
        from backend.config_loader import load_config, save_config
        config = load_config()
        config["last_rank_min"] = self.rank_min
        config["last_rank_max"] = self.rank_max
        save_config(config)

    def load_from_config(self):
        from backend.config_loader import load_config
        config = load_config()
        self._rank_min.delete(0, "end")
        self._rank_min.insert(0, str(config.get("last_rank_min", 100)))
        self._rank_max.delete(0, "end")
        self._rank_max.insert(0, str(config.get("last_rank_max", 5000)))
