"""
カラー・フォント定数
"""
import customtkinter as ctk

# ── テーマ ──────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_FAMILY = "Yu Gothic UI"

# ── カラー ──────────────────────────────────────
BG_PRIMARY    = "#1a1a2e"
BG_SECONDARY  = "#16213e"
BG_CARD       = "#0f3460"
BG_CARD_ALT   = "#112244"
ACCENT        = "#e94560"
TEXT_PRIMARY  = "#ffffff"
TEXT_SECONDARY= "#a0aec0"
TEXT_LINK     = "#63b3ed"
SUCCESS       = "#48bb78"
WARNING       = "#ed8936"
DANGER        = "#fc8181"
BORDER        = "#2d3748"

# ── フォントヘルパー ─────────────────────────────
def font(size: int = 12, bold: bool = False) -> ctk.CTkFont:
    weight = "bold" if bold else "normal"
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
