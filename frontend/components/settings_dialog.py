"""
APIキー入力ダイアログ
"""
from __future__ import annotations
import customtkinter as ctk
from backend import keepa_client
from backend.config_loader import load_config, save_config
from frontend.styles import font, BG_PRIMARY, BG_SECONDARY, ACCENT


_FIELDS = [
    ("keepa_api_key",  "Keepa API キー"),
    ("claude_api_key", "Claude API キー"),
    ("serper_api_key", "Serper API キー"),
    ("rakuten_api_key","楽天 API キー"),
    ("yahoo_client_id","Yahoo クライアント ID"),
]


class SettingsDialog(ctk.CTkToplevel):
    """APIキー・各種設定を入力・保存するモーダルダイアログ"""

    def __init__(self, master):
        super().__init__(master)
        self.title("設定")
        self.geometry("520x420")
        self.resizable(False, False)
        self.grab_set()  # モーダル
        self.configure(fg_color=BG_PRIMARY)
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._build()
        self._load()

    def _build(self):
        ctk.CTkLabel(
            self, text="API キー設定", font=font(16, bold=True)
        ).pack(pady=(16, 8))

        frame = ctk.CTkFrame(self, fg_color=BG_SECONDARY, corner_radius=8)
        frame.pack(fill="x", padx=20, pady=4)

        for row, (key, label) in enumerate(_FIELDS):
            ctk.CTkLabel(frame, text=label, font=font(12), width=160, anchor="e").grid(
                row=row, column=0, padx=(12, 8), pady=6, sticky="e"
            )
            entry = ctk.CTkEntry(
                frame, width=280, font=font(12), show="●", placeholder_text="未設定"
            )
            entry.grid(row=row, column=1, padx=(0, 8), pady=6)

            # 表示/非表示トグル
            toggle = ctk.CTkButton(
                frame,
                text="表示",
                width=48,
                font=font(10),
                command=lambda e=entry: self._toggle_show(e),
            )
            toggle.grid(row=row, column=2, padx=(0, 12), pady=6)
            self._entries[key] = entry

        # 禁止キーワード
        kw_frame = ctk.CTkFrame(self, fg_color=BG_SECONDARY, corner_radius=8)
        kw_frame.pack(fill="x", padx=20, pady=(8, 4))
        ctk.CTkLabel(
            kw_frame, text="禁止キーワード（改行区切り）", font=font(12)
        ).pack(anchor="w", padx=12, pady=(6, 2))
        self._kw_box = ctk.CTkTextbox(kw_frame, height=80, font=font(11))
        self._kw_box.pack(fill="x", padx=12, pady=(0, 8))

        # ボタン行
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(
            btn_frame, text="保存", font=font(13, bold=True),
            fg_color=ACCENT, hover_color="#c73652",
            command=self._save,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            btn_frame, text="キャンセル", font=font(13),
            fg_color="gray30", hover_color="gray40",
            command=self.destroy,
        ).pack(side="right", padx=4)

    def _load(self):
        config = load_config()
        for key, entry in self._entries.items():
            val = config.get(key, "")
            entry.delete(0, "end")
            if val:
                entry.insert(0, val)
        keywords: list[str] = config.get("forbidden_keywords", [])
        self._kw_box.delete("1.0", "end")
        self._kw_box.insert("1.0", "\n".join(keywords))

    def _save(self):
        config = load_config()
        for key, entry in self._entries.items():
            val = entry.get().strip()
            if val:
                config[key] = val
        kw_text = self._kw_box.get("1.0", "end").strip()
        config["forbidden_keywords"] = [
            kw.strip() for kw in kw_text.splitlines() if kw.strip()
        ]
        save_config(config)
        keepa_client.reset_api()  # APIキー変更を反映
        self.destroy()

    @staticmethod
    def _toggle_show(entry: ctk.CTkEntry):
        entry.configure(show="" if entry.cget("show") else "●")
