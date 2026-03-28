"""
クリックでブラウザを開く URL ラベル
"""
import webbrowser
import customtkinter as ctk
from frontend.styles import TEXT_LINK, font


class UrlLabel(ctk.CTkLabel):
    """クリックするとデフォルトブラウザで URL を開くラベル"""

    def __init__(self, master, url: str = "", text: str = "", **kwargs):
        kwargs.setdefault("text_color", TEXT_LINK)
        kwargs.setdefault("font", font(11))
        kwargs.setdefault("cursor", "hand2")
        super().__init__(master, text=text or url, **kwargs)
        self._url = url
        self.bind("<Button-1>", self._open)
        # ホバー時に下線風の色変化
        self.bind("<Enter>", lambda _: self.configure(text_color="#90cdf4"))
        self.bind("<Leave>", lambda _: self.configure(text_color=TEXT_LINK))

    def set_url(self, url: str, text: str = ""):
        self._url = url
        self.configure(text=text or url)

    def _open(self, _event=None):
        if self._url:
            webbrowser.open(self._url)
