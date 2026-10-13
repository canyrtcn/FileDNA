"""FileDNA: modern, English-first / Turkish-second, read-only desktop UI.

UI callbacks execute on Tk's main thread. File hashing is delegated to a worker.
No file deletion or mutation functionality exists in this module.
"""
from __future__ import annotations

import ctypes
import json
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .cli import format_size
from .cleanup import UnsafeSelection, make_plan, move_to_trash, select_extra_paths
from .scanner import ScanCancelled, ScanReport, scan_directory

GITHUB_PROFILE = "https://github.com/canyrtcn"
GITHUB_REPO = "https://github.com/canyrtcn/FileDNA"

# Restrained graphite / amber palette. Keep status green for non-actionable values.
BG = "#121110"
PANEL = "#201d1a"
FIELD = "#29251f"
BORDER = "#493d2d"
FG = "#f3eee6"
MUTED = "#c0b6a8"
DIM = "#9c8b77"
ACCENT = "#f3b544"
HOVER = "#ffd17a"
GREEN = "#8fc5a2"
AMBER = "#e4a338"
BUTTON_DISABLED = "#231f1b"
DARK_INK = "#21170c"
CAPTION_BG = BG
CAPTION_TEXT = FG
CARD_VALUE = "#fff6e7"
HIGHLIGHT = "#6b4b23"

# The first value is English, the second Turkish. Active language is the
# large, primary label; the alternative remains a subtle secondary label.
WORDS = {
    "subtitle": ("Duplicate File Finder", "Kopya Dosya Bulucu"),
    "hero": ("Find identical files without changing your data.", "Verilerinizi değiştirmeden aynı dosyaları bulun."),
    "folder": ("Scan folder", "Taranacak klasör"),
    "browse": ("Browse", "Gözat"),
    "scan": ("Start scan", "Taramayı başlat"),
    "stop": ("Stop", "Durdur"),
    "scanned": ("Files scanned", "İncelenen dosya"),
    "groups": ("Duplicate groups", "Kopya grubu"),
    "copies": ("Extra copies", "Fazladan kopya"),
    "space": ("Reclaimable space", "Kazanılabilir alan"),
    "results": ("Duplicate files", "Bulunan kopyalar"),
    "open": ("Open file location", "Dosya konumunu aç"),
    "export": ("Export JSON", "JSON raporu kaydet"),
    "path": ("Group / file path", "Grup / dosya yolu"),
    "size": ("Size", "Boyut"),
    "count": ("Files", "Dosya"),
    "select_all": ("Select extra copies (Ctrl+A)", "Fazladan kopyaları seç (Ctrl+A)"),
    "select_group": ("Select extras in group", "Gruptaki fazla kopyaları seç"),
    "clear_selection": ("Clear selection (Esc)", "Seçimi temizle (Esc)"),
    "copy_paths": ("Copy paths (Ctrl+C)", "Yolları kopyala (Ctrl+C)"),
    "recycle": ("Move selected to Recycle Bin (Delete)", "Seçilenleri Geri Dönüşüm Kutusuna taşı (Delete)"),
    "recycle_confirm_title": ("Confirm Recycle Bin cleanup", "Geri Dönüşüm Kutusu onayı"),
    "recycle_confirm": ("Move {count} file(s), totaling {size}, to the Recycle Bin?\n"
                        "One verified copy per group will be retained.\n"
                        "There is NO permanent-delete fallback.",
                        "{count} dosya ({size}) Geri Dönüşüm Kutusuna taşınsın mı?\n"
                        "Her grupta doğrulanmış bir kopya kalacak.\n"
                        "Kalıcı silme alternatifi YOK."),
    "recycle_failed": ("Cleanup blocked", "Temizleme engellendi"),
    "recycle_progress": ("Moving to Recycle Bin", "Geri Dönüşüm Kutusuna taşınıyor"),
    "recycle_progress_detail": ("Please wait…", "Lütfen bekleyin…"),
    "recycle_finished": ("Recycle Bin cleanup completed", "Geri Dönüşüm Kutusu temizliği tamamlandı"),
    "recycle_result": ("Moved: {moved}; failed/skipped: {failed}. Results will be rescanned.",
                       "Taşınan: {moved}; başarısız/atlanan: {failed}. Sonuçlar tekrar taranacak."),
    "recycle_none": ("Select one or more file rows first.", "Önce bir veya daha fazla dosya satırı seçin."),
    "busy": ("Wait for the current operation to finish.", "Devam eden işlemin bitmesini bekleyin."),

    "files_in_group": ("files", "dosya"),
    "hash": ("SHA-256", "SHA-256"),
    "empty": ("No scan results yet", "Henüz tarama sonucu yok"),
    "empty_help": ("Choose a folder and start a scan to find matching files.",
                   "Aynı dosyaları bulmak için klasör seçip tarama başlatın."),
    "none": ("No duplicate files found", "Yinelenen dosya bulunamadı"),
    "none_help": ("The selected folder contains no identical copies.",
                  "Seçilen klasörde birebir aynı içerikli kopya yok."),
    "ready": ("Ready to scan", "Taramaya hazır"),
    "discovering": ("Discovering files", "Dosyalar listeleniyor"),
    "hashing": ("Checking file contents", "Dosya içerikleri kontrol ediliyor"),
    "stopping": ("Stopping scan", "Tarama durduruluyor"),
    "cancelled": ("Scan cancelled — files unchanged", "Tarama iptal edildi — dosyalar değişmedi"),
    "failed": ("Scan failed", "Tarama başarısız"),
    "finished": ("Scan complete", "Tarama tamamlandı"),
    "elapsed": ("Elapsed", "Geçen süre"),
    "safe": ("Read-only scanning · Optional confirmed Recycle Bin cleanup",
             "Salt okunur tarama · İsteğe bağlı onaylı Geri Dönüşüm Kutusu temizliği"),
    "invalid": ("Select an existing folder that is not a symbolic link.",
                "Sembolik bağlantı olmayan mevcut bir klasör seçin."),
    "scan_error": ("Scan error", "Tarama hatası"),
    "partial": ("Incomplete scan", "Eksik tarama"),
    "partial_help": ("{count} files could not be read. See the JSON report.",
                     "{count} dosya okunamadı. Ayrıntılar JSON raporunda."),
    "save": ("Save JSON report", "JSON raporunu kaydet"),
    "save_failed": ("Report could not be saved", "Rapor kaydedilemedi"),
    "saved": ("Report saved", "Rapor kaydedildi"),
    "link_error": ("Could not open link", "Bağlantı açılamadı"),
    "help": ("Help", "Yardım"),
    "help_title": ("How to use FileDNA", "FileDNA nasıl kullanılır?"),
    "help_intro": ("Find exact copies without changing your original files.",
                   "Orijinal dosyalarınızı değiştirmeden birebir kopyaları bulun."),
    "help_close": ("Got it", "Anladım"),
    "help_privacy": ("Local scan and optional cleanup", "Yerel tarama ve isteğe bağlı temizleme"),
    "help_privacy_text": ("Scanning changes no files. Only explicitly selected copies can be moved "
                          "to the Recycle Bin after confirmation. JSON reports may include private paths.",
                          "Tarama dosyaları değiştirmez. Yalnızca seçilen kopyalar onay sonrası "
                          "Geri Dönüşüm Kutusuna taşınır. JSON raporları özel yolları içerebilir."),
}



# DWM styling leaves standard Windows minimize, maximize and close controls intact.
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def _colorref(value: str) -> int:
    """Convert #RRGGBB to Windows 0x00BBGGRR."""
    value = value.removeprefix("#")
    if len(value) != 6:
        raise ValueError("Expected six-digit RGB color")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def _apply_windows_caption(window) -> bool:
    """Best effort: color title bar where supported; no frameless workaround."""
    if sys.platform != "win32":
        return False
    try:
        parent_fn = ctypes.windll.user32.GetParent
        parent_fn.argtypes = [ctypes.c_void_p]
        parent_fn.restype = ctypes.c_void_p
        widget_hwnd = int(window.winfo_id())
        hwnd = parent_fn(ctypes.c_void_p(widget_hwnd)) or widget_hwnd
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                  ctypes.c_void_p, ctypes.c_uint]
        set_attribute.restype = ctypes.c_long
        target = ctypes.c_void_p(hwnd)
        dark = ctypes.c_int(1)
        hr = set_attribute(target, _DWMWA_USE_IMMERSIVE_DARK_MODE,
                           ctypes.byref(dark), ctypes.sizeof(dark))
        if hr != 0:
            hr = set_attribute(target, 19, ctypes.byref(dark),
                               ctypes.sizeof(dark))
        caption_color = ctypes.c_int(_colorref(CAPTION_BG))
        caption_text = ctypes.c_int(_colorref(CAPTION_TEXT))
        caption_hr = set_attribute(target, _DWMWA_CAPTION_COLOR,
                                   ctypes.byref(caption_color),
                                   ctypes.sizeof(caption_color))
        text_hr = set_attribute(target, _DWMWA_TEXT_COLOR,
                                ctypes.byref(caption_text),
                                ctypes.sizeof(caption_text))
        return (caption_hr == 0 and text_hr == 0) or hr == 0
    except (AttributeError, OSError, tk.TclError, ValueError):
        return False


HELP_STEPS = {
    "EN": (
        ("Choose a folder", "Browse or paste a folder path. Subfolders are scanned too."),
        ("Start scan", "FileDNA groups files by size and compares SHA-256 checksums."),
        ("Review matches", "Expand groups. Double-click a file to open its location."),
        ("Export JSON", "Save a report; FileDNA does not delete any files."),
    ),
    "TR": (
        ("Klasör seçin", "Gözat ile klasör seçin veya yolu yapıştırın. Alt klasörler de taranır."),
        ("Taramayı başlatın", "FileDNA önce boyutları, sonra SHA-256 özetlerini karşılaştırır."),
        ("Eşleşmelere bakın", "Grupları açın. Dosyanın konumunu açmak için çift tıklayın."),
        ("JSON raporu alın", "Raporu kaydedin; FileDNA hiçbir dosyayı silmez."),
    ),
}


def asset_path(name: str) -> Path:
    """Resolve assets in the source tree or PyInstaller onefile extraction."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "assets" / name


def _rounded_shape(canvas, x0, y0, x1, y1, radius, fill, outline=""):
    """Draw a smooth rounded rectangle on Tk Canvas without a new GUI dependency."""
    if x1 <= x0 or y1 <= y0:
        return
    r = max(0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    # Duplicate control points keep edges straight and round only the corners.
    points = [
        x0 + r, y0, x0 + r, y0,
        x1 - r, y0, x1 - r, y0,
        x1, y0, x1, y0 + r, x1, y0 + r,
        x1, y1 - r, x1, y1 - r,
        x1, y1, x1 - r, y1, x1 - r, y1,
        x0 + r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y1 - r,
        x0, y0 + r, x0, y0 + r,
        x0, y0, x0 + r, y0,
    ]
    canvas.create_polygon(points, smooth=True, splinesteps=16,
                          fill=fill, outline=outline, width=1)


class RoundedPanel(tk.Canvas):
    """Rounded outline with a safe rectangular content area inset from its corners."""

    def __init__(self, parent, *, surface=PANEL, border=BORDER,
                 radius=15, inset=8, height=125, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), height=height,
                         bd=0, highlightthickness=0, **kwargs)
        self._surface = surface
        self._border = border
        self._radius = radius
        self._inset = inset
        self.body = tk.Frame(self, bg=surface)
        self._body_window = self.create_window(inset, inset,
                                                anchor="nw", window=self.body)
        self.bind("<Configure>", self._resize_panel)

    def _resize_panel(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        self.delete("panel-background")
        # Keep the shape behind the embedded widget.
        old = set(self.find_all())
        _rounded_shape(self, 1, 1, w - 1, h - 1, self._radius,
                       self._surface, self._border)
        for item in set(self.find_all()) - old:
            self.addtag_withtag("panel-background", item)
            self.tag_lower(item)
        self.itemconfigure(self._body_window,
                           width=max(1, w - 2 * self._inset),
                           height=max(1, h - 2 * self._inset))


class ActionButton(tk.Canvas):
    """Keyboard-accessible rounded two-line button retaining legacy test hooks."""

    def __init__(self, parent, callback, *, primary=False, width=130):
        super().__init__(parent, bg=parent.cget("bg"), width=width, height=59,
                         bd=0, highlightthickness=0, takefocus=1, cursor="hand2")
        self.callback = callback
        self.primary = primary
        self.enabled = True
        self._hovered = False
        self._title_window = None
        self._sub_window = None
        self.surface = self  # legacy attribute retained for GUI regression tests
        self.main = tk.Label(self, bg=ACCENT if primary else FIELD,
                             fg=DARK_INK if primary else FG,
                             font=("Segoe UI Semibold", 10), bd=0)
        self.small = tk.Label(self, bg=ACCENT if primary else FIELD,
                              fg="#694817" if primary else MUTED,
                              font=("Segoe UI", 8), bd=0)
        self._title_window = self.create_window(width / 2, 22,
                                                  window=self.main, anchor="center")
        self._sub_window = self.create_window(width / 2, 41,
                                                window=self.small, anchor="center")
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", lambda _e: self.click())
        self.bind("<Return>", lambda _e: self.click())
        self.bind("<space>", lambda _e: self.click())
        self.bind("<Enter>", lambda _e: self.paint(True))
        self.bind("<Leave>", lambda _e: self.paint(False))
        for child in (self.main, self.small):
            child.bind("<Button-1>", lambda _e: self.click())
            child.bind("<Enter>", lambda _e: self.paint(True))
            child.bind("<Leave>", lambda _e: self.paint(False))
        self.paint(False)

    def set_text(self, primary: str, secondary: str):
        self.main.configure(text=primary)
        self.small.configure(text=secondary)

    def enable(self, value: bool):
        self.enabled = value
        self.configure(cursor="hand2" if value else "arrow")
        self.paint(False)
        for label in (self.main, self.small):
            label.configure(cursor="hand2" if value else "arrow")

    def paint(self, hover: bool):
        self._hovered = hover if self.enabled else False
        if not self.enabled:
            fill = BUTTON_DISABLED
        elif self.primary:
            fill = HOVER if hover else ACCENT
        else:
            fill = "#393024" if hover else FIELD
        self.main.configure(bg=fill,
                            fg=DARK_INK if self.primary and self.enabled else
                            FG if self.enabled else DIM)
        self.small.configure(bg=fill,
                             fg="#694817" if self.primary and self.enabled else
                             MUTED if self.enabled else DIM)
        self._redraw()

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        self.delete("button-background")
        old = set(self.find_all())
        if not self.enabled:
            fill = BUTTON_DISABLED
        elif self.primary:
            fill = HOVER if self._hovered else ACCENT
        else:
            fill = "#393024" if self._hovered else FIELD
        _rounded_shape(self, 1, 1, w - 1, h - 1, 12, fill,
                       ACCENT if self.primary and self.enabled else BORDER)
        for item in set(self.find_all()) - old:
            self.addtag_withtag("button-background", item)
            self.tag_lower(item)
        self.coords(self._title_window, w / 2, h / 2 - 9)
        self.coords(self._sub_window, w / 2, h / 2 + 10)

    def click(self):
        if self.enabled:
            self.callback()


class FileDNAApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.language = "EN"
        self.title(f"FileDNA v{__version__} | Duplicate File Finder")
        self.geometry("1240x840")
        self.minsize(950, 690)
        self.configure(bg=BG)
        self.folder = tk.StringVar(value=str(Path.home()))
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._report: ScanReport | None = None
        self._row_paths: dict[str, str] = {}
        self._cleanup_running = False
        self._cleanup_thread: threading.Thread | None = None
        self._started: float | None = None
        self._state = "ready"
        self._fraction = 0.0
        self._after_id: str | None = None
        self._is_closing = False
        self._help_window = None
        self._help_text_widgets = []
        self._icon_full = None
        self._icon_small = None
        self._install_icon()
        self._style()
        self._layout()
        self._translate()
        self.after_idle(lambda: _apply_windows_caption(self))
        self._after_id = self.after(90, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _tr(self, key):
        return WORDS[key][0 if self.language == "EN" else 1]

    def _both(self, key):
        a, b = WORDS[key]
        return (a, b) if self.language == "EN" else (b, a)

    @staticmethod
    def _label(parent, text="", *, size=10, color=FG, bold=False, bg=None, **kwargs):
        return tk.Label(parent, text=text, fg=color,
                        bg=bg or parent.cget("bg"),
                        font=("Segoe UI Semibold" if bold else "Segoe UI", size),
                        **kwargs)

    def _install_icon(self):
        ico = asset_path("filedna.ico")
        if sys.platform == "win32" and ico.is_file():
            try:
                self.iconbitmap(str(ico))
            except tk.TclError:
                pass
        png = asset_path("filedna.png")
        if png.is_file():
            try:
                self._icon_full = tk.PhotoImage(file=str(png))
                self._icon_small = self._icon_full.subsample(7, 7)
                self.iconphoto(True, self._icon_full)
            except tk.TclError:
                self._icon_full = None
                self._icon_small = None

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("DNA.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=FG, borderwidth=0, rowheight=34,
                        font=("Segoe UI", 10))
        style.configure("DNA.Treeview.Heading", background=FIELD, foreground=MUTED,
                        borderwidth=0, relief="flat", padding=(12, 13),
                        bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD,
                        font=("Segoe UI Semibold", 10))
        # clam's default heading-state map can show a white background on hover.
        style.map("DNA.Treeview.Heading",
                  background=[("pressed", HIGHLIGHT), ("active", FIELD),
                              ("!active", FIELD)],
                  foreground=[("pressed", FG), ("active", FG), ("!active", MUTED)],
                  relief=[("pressed", "flat"), ("active", "flat")])
        style.map("DNA.Treeview", background=[("selected", "#594020")],
                  foreground=[("selected", FG)])
        style.configure("DNA.Vertical.TScrollbar", background=FIELD,
                        troughcolor=PANEL, arrowcolor=MUTED, borderwidth=0)

    def _layout(self):
        root = tk.Frame(self, bg=BG, padx=26, pady=20)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x")
        if self._icon_small is not None:
            tk.Label(header, image=self._icon_small, bg=BG).pack(side="left", padx=(0, 12))
        else:
            self._label(header, "◈", color=ACCENT, size=24).pack(side="left", padx=(0, 12))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        self._label(brand, "File", size=23, bold=True).pack(side="left")
        self._label(brand, "DNA", size=23, bold=True, color=ACCENT).pack(side="left")
        self._label(header, "│", color=BORDER, size=18).pack(side="left", padx=(13, 10))
        self.subtitle = self._label(header, size=11, color=MUTED)
        self.subtitle.pack(side="left")
        switches = tk.Frame(header, bg=BG)
        switches.pack(side="right")
        self.en = self._label(switches, "EN", color=ACCENT, bold=True, cursor="hand2")
        self.en.pack(side="left")
        self._label(switches, "  /  ", color=DIM).pack(side="left")
        self.tr = self._label(switches, "TR", color=DIM, bold=True, cursor="hand2")
        self.tr.pack(side="left")
        self.help_button = tk.Canvas(header, bg=BG, bd=0,
                                     highlightthickness=0, width=32, height=32,
                                     cursor="hand2", takefocus=1)
        self.help_button.pack(side="right", padx=(0, 20))
        self.help_button.bind("<Button-1>", lambda _event: self._open_help())
        self.help_button.bind("<Return>", lambda _event: self._open_help())
        self.help_button.bind("<space>", lambda _event: self._open_help())
        self.help_button.bind("<Enter>", lambda _event: self._paint_help_button(True))
        self.help_button.bind("<Leave>", lambda _event: self._paint_help_button(False))
        self._paint_help_button(False)
        self.en.bind("<Button-1>", lambda _: self.set_language("EN"))
        self.tr.bind("<Button-1>", lambda _: self.set_language("TR"))
        self.tagline = self._label(root, size=10, color=DIM)
        self.tagline.pack(anchor="w", pady=(10, 16))
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x", pady=(0, 17))

        controls = tk.Frame(root, bg=BG)
        controls.pack(fill="x", pady=(0, 19))
        folder_names = tk.Frame(controls, bg=BG, width=132)
        folder_names.pack(side="left", fill="y", padx=(0, 12))
        folder_names.pack_propagate(False)
        self.folder_title = self._label(folder_names, size=11, bold=True)
        self.folder_title.pack(anchor="w", pady=(9, 0))
        self.folder_sub = self._label(folder_names, size=9, color=DIM)
        self.folder_sub.pack(anchor="w", pady=(3, 0))
        entry_panel = RoundedPanel(controls, surface=FIELD, height=59,
                                   radius=13, inset=8)
        entry_panel.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.folder_input = tk.Entry(entry_panel.body, textvariable=self.folder,
                                     bg=FIELD, fg=FG, insertbackground=FG,
                                     font=("Segoe UI", 10), relief="flat",
                                     highlightthickness=0, borderwidth=0)
        self.folder_input.pack(fill="both", expand=True, padx=8, pady=1)
        self.browse_button = ActionButton(controls, self._browse, width=106)
        self.browse_button.pack(side="left", fill="y", padx=(0, 9))
        self.scan_button = ActionButton(controls, self._start_scan, primary=True, width=143)
        self.scan_button.pack(side="left", fill="y", padx=(0, 9))
        self.stop_button = ActionButton(controls, self._cancel_scan, width=89)
        self.stop_button.pack(side="left", fill="y")
        self.stop_button.enable(False)

        cards = tk.Frame(root, bg=BG)
        cards.pack(fill="x", pady=(0, 23))
        self.metrics = {}
        for index, (key, icon, tint) in enumerate(
            (("scanned", "▤", MUTED), ("groups", "≡", ACCENT),
             ("copies", "▣", AMBER), ("space", "◫", GREEN))
        ):
            cards.grid_columnconfigure(index, weight=1, uniform="metric")
            outline = RoundedPanel(cards, surface=PANEL, radius=16,
                                   inset=8, height=132)
            outline.grid(row=0, column=index, sticky="nsew",
                         padx=(0 if index == 0 else 5, 0 if index == 3 else 5))
            body = outline.body
            body.configure(padx=10, pady=5)
            upper = tk.Frame(body, bg=PANEL)
            upper.pack(fill="x")
            self._label(upper, icon, color=tint, size=22, bg=PANEL).pack(side="left", padx=(0, 12))
            labels = tk.Frame(upper, bg=PANEL)
            labels.pack(side="left")
            title = self._label(labels, size=10, bold=True, bg=PANEL)
            title.pack(anchor="w")
            secondary = self._label(labels, size=9, color=MUTED, bg=PANEL)
            secondary.pack(anchor="w", pady=(2, 0))
            value = self._label(body, "0", size=20, bold=True, bg=PANEL)
            value.pack(anchor="w", pady=(8, 0))
            self.metrics[key] = (title, secondary, value)

        results_row = tk.Frame(root, bg=BG)
        results_row.pack(fill="x", pady=(0, 12))
        results_heading = tk.Frame(results_row, bg=BG)
        results_heading.pack(side="left")
        self.results_title = self._label(results_heading, size=13, bold=True)
        self.results_title.pack(anchor="w")
        self.results_sub = self._label(results_heading, size=9, color=MUTED)
        self.results_sub.pack(anchor="w", pady=(3, 0))
        self.select_button = ActionButton(results_row, self._select_all_extras, width=155)
        self.select_button.pack(side="right", fill="y", padx=(0, 10))
        self.export_button = ActionButton(results_row, self._export_json, width=142)
        self.export_button.pack(side="right", fill="y")
        self.open_button = ActionButton(results_row, self._open_selected, width=174)
        self.open_button.pack(side="right", fill="y", padx=(0, 10))
        self.export_button.enable(False)
        self.open_button.enable(False)
        self.select_button.enable(False)

        table_border = RoundedPanel(root, surface=PANEL, radius=17,
                                    inset=8, height=190)
        table_border.pack(fill="both", expand=True, pady=(0, 15))
        table_container = table_border.body
        self.tree = ttk.Treeview(table_container, columns=("size", "count", "hash"),
                                 show="tree headings", height=6, selectmode="extended",
                                 style="DNA.Treeview")
        self.tree.column("#0", width=500, minwidth=220, stretch=True)
        self.tree.column("size", width=125, stretch=False, anchor="e")
        self.tree.column("count", width=78, stretch=False, anchor="center")
        self.tree.column("hash", width=170, stretch=False)
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview,
                                  style="DNA.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("group", foreground=ACCENT)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection)
        self.tree.bind("<Double-1>", lambda _: self._open_selected())
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Control-a>", self._select_all_extras)
        self.tree.bind("<Control-c>", self._copy_selected_paths)
        self.tree.bind("<Delete>", self._recycle_selected)
        self.tree.bind("<Escape>", self._clear_selection)
        self._context_menu = tk.Menu(
            self, tearoff=False, bg=FIELD, fg=FG,
            activebackground=HIGHLIGHT, activeforeground=FG,
            disabledforeground=DIM, bd=1, relief="flat",
            font=("Segoe UI", 10),
        )
        self.empty = tk.Frame(table_container, bg=PANEL, padx=15, pady=15)
        self._label(self.empty, "⌕", size=48, color=DIM, bg=PANEL).pack()
        self.empty_title = self._label(self.empty, size=14, bold=True, bg=PANEL)
        self.empty_title.pack(pady=(1, 7))
        self.empty_help = self._label(self.empty, size=10, color=MUTED, bg=PANEL)
        self.empty_help.pack()
        self.empty.place(relx=.50, rely=.55, anchor="center")
        self.empty.lift()

        status_border = RoundedPanel(root, surface=PANEL, radius=15,
                                     inset=6, height=66)
        status_border.pack(fill="x", pady=(0, 10))
        status = status_border.body
        status.configure(padx=10, pady=4)
        self._label(status, "◷", size=23, color=ACCENT, bg=PANEL).pack(side="left", padx=(0, 12))
        status_labels = tk.Frame(status, bg=PANEL, width=206, height=42)
        status_labels.pack(side="left")
        status_labels.pack_propagate(False)
        self.status_title = self._label(status_labels, size=10, bold=True, bg=PANEL)
        self.status_title.pack(anchor="w")
        self.status_detail = self._label(status_labels, size=9, color=MUTED, bg=PANEL)
        self.status_detail.pack(anchor="w", pady=(1, 0))
        self.elapsed_value = self._label(status, "—", size=10, color=MUTED, bg=PANEL)
        self.elapsed_value.pack(side="right", padx=(15, 4))
        self.elapsed_label = self._label(status, color=DIM, size=9, bg=PANEL)
        self.elapsed_label.pack(side="right")
        self.percent = self._label(status, "0%", color=MUTED, size=10, bg=PANEL)
        self.percent.pack(side="right", padx=(14, 0))
        self.progress = tk.Canvas(status, height=7, bg=FIELD,
                                  highlightthickness=0, borderwidth=0)
        self.progress.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=(15, 0))
        self.progress.bind("<Configure>", lambda _: self._draw_progress())

        footer = tk.Frame(root, bg=BG)
        footer.pack(fill="x")
        self.footer_version = self._label(footer, color=MUTED, size=9)
        self.footer_version.pack(side="left")
        self._link(footer, "Repository", GITHUB_REPO).pack(side="right", padx=(13, 0))
        self._label(footer, "│", color=BORDER).pack(side="right")
        self._link(footer, "@canyrtcn", GITHUB_PROFILE).pack(side="right", padx=(0, 13))
        self._label(footer, "GitHub", color=MUTED, size=9).pack(side="right", padx=(0, 8))
        self.safe = self._label(footer, color=DIM, size=8)
        self.safe.pack(side="left", padx=(18, 0))

    def _link(self, parent, title, url):
        label = self._label(parent, title, color=ACCENT, size=9, cursor="hand2")
        label.bind("<Button-1>", lambda _: self._open_link(url))
        label.bind("<Enter>", lambda _: label.configure(fg=HOVER))
        label.bind("<Leave>", lambda _: label.configure(fg=ACCENT))
        return label

    def _open_link(self, url):
        try:
            opened = webbrowser.open(url, new=2)
        except Exception:
            opened = False
        if not opened:
            messagebox.showwarning(self._tr("link_error"), url)

    def set_language(self, code):
        if code in ("EN", "TR"):
            self.language = code
            self._translate()

    def _translate(self):
        self.title(f"FileDNA v{__version__} | {self._tr('subtitle')}")
        self.subtitle.configure(text=self._tr("subtitle"))
        self.tagline.configure(text=self._tr("hero"))
        self.en.configure(fg=ACCENT if self.language == "EN" else DIM)
        self.tr.configure(fg=ACCENT if self.language == "TR" else DIM)
        if self._help_window is not None and self._help_window.winfo_exists():
            self._refresh_help()
        self.folder_title.configure(text=self._both("folder")[0])
        self.folder_sub.configure(text=self._both("folder")[1])
        self.select_button.set_text(*self._both("select_all"))
        for button, key in ((self.browse_button, "browse"), (self.scan_button, "scan"),
                            (self.stop_button, "stop"), (self.open_button, "open"),
                            (self.export_button, "export")):
            button.set_text(*self._both(key))
        for key, (title, subtitle, _value) in self.metrics.items():
            main, alternative = self._both(key)
            title.configure(text=main)
            subtitle.configure(text=alternative)
        self.results_title.configure(text=self._tr("results"))
        self.results_sub.configure(text=self._both("results")[1])
        for column, key in (("#0", "path"), ("size", "size"),
                            ("count", "count"), ("hash", "hash")):
            self.tree.heading(column, text=self._tr(key))
        empty_key, help_key = ("none", "none_help") if (self._report is not None
                                  and not self._report.groups) else ("empty", "empty_help")
        self.empty_title.configure(text=self._tr(empty_key))
        self.empty_help.configure(text=self._tr(help_key))
        self.elapsed_label.configure(text=f"{self._tr('elapsed')}: ")
        self.footer_version.configure(text=f"FileDNA  v{__version__}  │  {self._tr('subtitle')}")
        self.safe.configure(text=self._tr("safe"))
        self.status_title.configure(text=self._tr(self._state))
        if self._report is not None:
            for index, item in enumerate(self.tree.get_children(), start=1):
                count = len(self._report.groups[index - 1].paths)
                self.tree.item(item, text=f"#{index} · {count} {self._tr('files_in_group')}")
            if self._state == "finished":
                self.status_detail.configure(
                    text=f"{len(self._report.groups)} {self._tr('groups').lower()}"
                )

    def _paint_help_button(self, hovered: bool):
        self.help_button.delete("all")
        _rounded_shape(self.help_button, 1, 1, 31, 31, 15,
                       HIGHLIGHT if hovered else FIELD, BORDER)
        self.help_button.create_text(16, 16, text="?",
                                     font=("Segoe UI Semibold", 13),
                                     fill=HOVER if hovered else FG)

    def _open_help(self):
        if self._help_window is not None and self._help_window.winfo_exists():
            self._help_window.lift()
            self._help_window.focus_set()
            return
        dialog = tk.Toplevel(self)
        self._help_window = dialog
        dialog.withdraw()
        dialog.title(self._tr("help_title"))
        dialog.configure(bg=BG)
        dialog.geometry("560x520")
        dialog.minsize(485, 480)
        dialog.transient(self)
        dialog.protocol("WM_DELETE_WINDOW", self._dismiss_help)
        container = tk.Frame(dialog, bg=BG, padx=28, pady=23)
        container.pack(fill="both", expand=True)

        self._help_heading = self._label(container, size=18, bold=True)
        self._help_heading.pack(anchor="w")
        self._help_intro = self._label(container, size=10, color=MUTED,
                                       wraplength=480, justify="left")
        self._help_intro.pack(anchor="w", pady=(4, 15))
        self._help_text_widgets = []
        for index in range(4):
            row = tk.Frame(container, bg=BG)
            row.pack(fill="x", pady=(0, 12))
            self._label(row, f"{index + 1:02d}", color=ACCENT,
                        bold=True, size=12).pack(side="left", anchor="n", padx=(0, 14))
            body = tk.Frame(row, bg=BG)
            body.pack(side="left", fill="x", expand=True)
            heading = self._label(body, size=10, bold=True)
            heading.pack(anchor="w")
            detail = self._label(body, size=9, color=MUTED,
                                 wraplength=422, justify="left")
            detail.pack(anchor="w", pady=(2, 0))
            self._help_text_widgets.append((heading, detail))

        self._help_safety = self._label(container, size=9, color=AMBER,
                                       wraplength=480, justify="left")
        self._help_safety.pack(anchor="w", pady=(5, 10))
        self._help_close_button = ActionButton(
            container, self._dismiss_help, primary=True, width=132
        )
        self._help_close_button.pack(anchor="e", pady=(0, 4))
        self._refresh_help()
        dialog.deiconify()
        dialog.lift()
        dialog.focus_set()
        dialog.after_idle(lambda: _apply_windows_caption(dialog)
                          if dialog.winfo_exists() else None)

    def _refresh_help(self):
        dialog = self._help_window
        if dialog is None or not dialog.winfo_exists():
            return
        dialog.title(self._tr("help_title"))
        self._help_heading.configure(text=self._tr("help_title"))
        self._help_intro.configure(text=self._tr("help_intro"))
        for pair, (heading, detail) in zip(self._help_text_widgets,
                                            HELP_STEPS[self.language]):
            pair[0].configure(text=heading)
            pair[1].configure(text=detail)
        self._help_safety.configure(
            text=f"{self._tr('help_privacy')} — {self._tr('help_privacy_text')}"
        )
        self._help_close_button.set_text(self._tr("help_close"), self._tr("help"))

    def _dismiss_help(self):
        dialog = self._help_window
        self._help_window = None
        self._help_text_widgets = []
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()

    def _browse(self):
        chosen = filedialog.askdirectory(title=self._tr("folder"), mustexist=True)
        if chosen:
            self.folder.set(chosen)

    def _start_scan(self):
        if self._cleanup_running or (self._worker is not None and self._worker.is_alive()):
            return
        root = Path(self.folder.get()).expanduser()
        if root.is_symlink() or not root.is_dir():
            messagebox.showerror(self._tr("scan_error"), self._tr("invalid"))
            return
        # Discard terminal events from the previous worker (if any).
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._stop_event = threading.Event()
        self._report = None
        self._row_paths.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for _title, _subtitle, value in self.metrics.values():
            value.configure(text="0")
        self.empty.place(relx=.50, rely=.55, anchor="center")
        self._state = "discovering"
        self.status_title.configure(text=self._tr("discovering"))
        self.status_detail.configure(text="")
        self._started = time.monotonic()
        self._fraction = 0.0
        self._draw_progress()
        self.percent.configure(text="—")
        self.scan_button.enable(False)
        self.browse_button.enable(False)
        self.stop_button.enable(True)
        self.export_button.enable(False)
        self.open_button.enable(False)
        self.folder_input.configure(state="disabled")
        self._worker = threading.Thread(target=self._scan_worker,
                                        args=(root, self._stop_event), daemon=True)
        self._worker.start()

    def _scan_worker(self, root, stop_event):
        try:
            report = scan_directory(root, cancel_event=stop_event,
                                    progress=lambda phase, n, total: self._queue.put(
                                        ("progress", phase, n, total)))
            self._queue.put(("result", report))
        except ScanCancelled:
            self._queue.put(("cancelled",))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _cancel_scan(self):
        self._stop_event.set()
        self._state = "stopping"
        self.status_title.configure(text=self._tr("stopping"))
        self.stop_button.enable(False)

    def _poll(self):
        if self._is_closing:
            return
        try:
            while True:
                event = self._queue.get_nowait()
                if event[0] == "progress":
                    if self._state == "stopping":
                        continue
                    _, phase, n, total = event
                    self._state = "discovering" if phase == "discovering" else "hashing"
                    self.status_title.configure(text=self._tr(self._state))
                    self.status_detail.configure(
                        text=f"{n:,}" if phase == "discovering" else f"{n:,} / {total:,}")
                    if phase == "hashing":
                        self._fraction = n / total if total else 1.0
                        self._draw_progress()
                        self.percent.configure(text=f"{int(self._fraction * 100)}%")
                elif event[0] == "result":
                    self._show_result(event[1])
                elif event[0] == "cancelled":
                    self._finish("cancelled")
                elif event[0] == "error":
                    self._finish("failed")
                    messagebox.showerror(self._tr("scan_error"), event[1])
                elif event[0] == "trash_result":
                    self._finish_cleanup(root=event[1], result=event[2])
                elif event[0] == "trash_error":
                    self._finish_cleanup(error=event[1])
        except queue.Empty:
            pass
        if self._started is not None:
            self.elapsed_value.configure(text=f"{int(time.monotonic() - self._started)}s")
        if self.winfo_exists():
            self._after_id = self.after(90, self._poll)

    def _draw_progress(self):
        self.progress.delete("all")
        width, height = max(1, self.progress.winfo_width()), max(1, self.progress.winfo_height())
        _rounded_shape(self.progress, 0, 0, width, height, height / 2, FIELD)
        if self._fraction:
            filled = min(width, max(height, round(width * self._fraction)))
            _rounded_shape(self.progress, 0, 0, filled, height, height / 2, ACCENT)

    def _finish(self, state):
        self._state = state
        self.status_title.configure(text=self._tr(state))
        self._started = None
        self.scan_button.enable(True)
        self.browse_button.enable(True)
        self.stop_button.enable(False)
        self.folder_input.configure(state="normal")

    def _show_result(self, report):
        self._report = report
        values = {"scanned": report.examined_files, "groups": len(report.groups),
                  "copies": report.duplicate_files, "space": format_size(report.reclaimable_bytes)}
        for key, val in values.items():
            self.metrics[key][2].configure(text=f"{val:,}" if isinstance(val, int) else val)
        for idx, group in enumerate(report.groups, start=1):
            parent = self.tree.insert(
                "", "end",
                text=f"#{idx} · {len(group.paths)} {self._tr('files_in_group')}",
                                      values=(format_size(group.size_bytes), len(group.paths),
                                              group.sha256[:18] + "…"),
                                      tags=("group",), open=idx <= 4)
            for filename in group.paths:
                row = self.tree.insert(parent, "end", text=filename,
                                       values=(format_size(group.size_bytes), "", ""))
                self._row_paths[row] = filename
        if report.groups:
            self.empty.place_forget()
        else:
            self.empty.place(relx=.50, rely=.55, anchor="center")
        self._fraction = 1.0
        self._draw_progress()
        self.percent.configure(text="100%")
        self.export_button.enable(True)
        self.select_button.enable(bool(report.groups))
        self._finish("finished")
        self._translate()
        self.status_detail.configure(text=f"{len(report.groups)} {self._tr('groups').lower()}")
        if report.errors:
            messagebox.showwarning(self._tr("partial"),
                                   self._tr("partial_help").format(count=len(report.errors)))

    def _selected_paths(self):
        """Only actual file rows, never Treeview group/header rows."""
        return [self._row_paths[item] for item in self.tree.selection()
                if item in self._row_paths]

    def _select_all_extras(self, _event=None):
        if self._report is None or self._cleanup_running:
            return "break"
        extra = set(select_extra_paths(self._report))
        rows = [row for row, path in self._row_paths.items() if path in extra]
        self.tree.selection_set(rows)
        if rows:
            self.tree.focus(rows[0])
        return "break"

    def _select_group_extras(self):
        if self._report is None or self._cleanup_running:
            return
        item = getattr(self, "_context_row", "")
        if not item:
            return
        group_row = self.tree.parent(item) or item
        if not self.tree.exists(group_row):
            return
        children = self.tree.get_children(group_row)
        if children:
            self.tree.selection_set(children[1:])

    def _clear_selection(self, _event=None):
        self.tree.selection_remove(self.tree.selection())
        return "break"

    def _copy_selected_paths(self, _event=None):
        chosen = self._selected_paths()
        if chosen:
            self.clipboard_clear()
            self.clipboard_append("\n".join(chosen))
        return "break"

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        self._context_row = item
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
            self.tree.focus(item)
        menu = self._context_menu
        menu.delete(0, "end")
        menu.add_command(label=self._tr("select_all"),
                         command=self._select_all_extras)
        menu.add_command(label=self._tr("select_group"),
                         command=self._select_group_extras,
                         state="normal" if item else "disabled")
        menu.add_command(label=self._tr("clear_selection"),
                         command=self._clear_selection)
        menu.add_separator()
        menu.add_command(label=self._tr("copy_paths"),
                         command=self._copy_selected_paths,
                         state="normal" if self._selected_paths() else "disabled")
        menu.add_command(label=self._tr("open"),
                         command=self._open_selected,
                         state="normal" if self._selected_paths() else "disabled")
        menu.add_separator()
        menu.add_command(label=self._tr("recycle"),
                         command=self._recycle_selected,
                         state="normal" if self._selected_paths() and
                         self._report is not None and not self._cleanup_running
                         else "disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _recycle_selected(self, _event=None):
        if self._cleanup_running or (
            self._worker is not None and self._worker.is_alive()
        ):
            messagebox.showwarning(self._tr("recycle_failed"), self._tr("busy"))
            return "break"
        if self._report is None:
            return "break"
        selected = self._selected_paths()
        if not selected:
            messagebox.showinfo(self._tr("recycle_failed"), self._tr("recycle_none"))
            return "break"
        try:
            plan = make_plan(self._report, selected)
        except UnsafeSelection as exc:
            messagebox.showwarning(self._tr("recycle_failed"),
                                   self._tr("keep_one") + "\n" + str(exc))
            return "break"
        message = self._tr("recycle_confirm").format(
            count=len(plan.paths), size=format_size(plan.bytes_total)
        )
        if not messagebox.askyesno(self._tr("recycle_confirm_title"), message,
                                   icon="warning", default="no"):
            return "break"
        self._cleanup_running = True
        self._state = "recycle_progress"
        self.status_title.configure(text=self._tr("recycle_progress"))
        self.status_detail.configure(text=f"{len(plan.paths)} · {self._tr('recycle_progress_detail')}")
        self.scan_button.enable(False)
        self.browse_button.enable(False)
        self.stop_button.enable(False)
        self.open_button.enable(False)
        self.export_button.enable(False)
        self.select_button.enable(False)
        self.folder_input.configure(state="disabled")
        report = self._report
        self._cleanup_thread = threading.Thread(
            target=self._trash_worker, args=(report, plan), daemon=True
        )
        self._cleanup_thread.start()
        return "break"

    def _trash_worker(self, report, plan):
        try:
            result = move_to_trash(report, plan)
            self._queue.put(("trash_result", report.root, result))
        except Exception as exc:
            self._queue.put(("trash_error", str(exc)))

    def _finish_cleanup(self, error=None, root=None, result=None):
        self._cleanup_running = False
        self._state = "ready"
        self.scan_button.enable(True)
        self.browse_button.enable(True)
        self.stop_button.enable(False)
        self.export_button.enable(self._report is not None)
        self.select_button.enable(self._report is not None and bool(self._report.groups))
        self.folder_input.configure(state="normal")
        if error is not None:
            self.status_title.configure(text=self._tr("recycle_failed"))
            messagebox.showerror(self._tr("recycle_failed"), error)
            return
        text = self._tr("recycle_result").format(
            moved=len(result.moved), failed=len(result.errors)
        )
        if result.errors:
            details = "\n".join(f"{Path(p).name}: {msg}"
                                for p, msg in list(result.errors.items())[:3])
            messagebox.showwarning(self._tr("recycle_finished"),
                                   text + "\n\n" + details)
        else:
            messagebox.showinfo(self._tr("recycle_finished"), text)
        self.folder.set(root)
        self._start_scan()

    def _on_selection(self, _event=None):
        selected = self.tree.selection()
        self.open_button.enable(not self._cleanup_running and any(
            row in self._row_paths for row in selected))

    def _open_selected(self):
        selected = self.tree.selection()
        filename = next((self._row_paths[row] for row in selected
                         if row in self._row_paths), None)
        if not filename:
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", filename])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", filename])
            else:
                subprocess.Popen(["xdg-open", str(Path(filename).parent)])
        except OSError as exc:
            messagebox.showerror(self._tr("scan_error"), str(exc))

    def _export_json(self):
        if self._report is None:
            return
        destination = filedialog.asksaveasfilename(title=self._tr("save"),
                         defaultextension=".json", initialfile="filedna-report.json",
                         filetypes=[("JSON", "*.json")])
        if not destination:
            return
        try:
            Path(destination).write_text(json.dumps(self._report.to_dict(),
                                    indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(self._tr("save_failed"), str(exc))
        else:
            self.status_detail.configure(text=f"{self._tr('saved')}: {destination}")

    def _close(self):
        if self._is_closing:
            return
        self._is_closing = True
        self._stop_event.set()
        self._dismiss_help()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self.destroy()


def main():
    FileDNAApp().mainloop()


if __name__ == "__main__":
    main()
