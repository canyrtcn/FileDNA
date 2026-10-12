"""FileDNA: modern, English-first / Turkish-second, read-only desktop UI.

UI callbacks execute on Tk's main thread. File hashing is delegated to a worker.
No file deletion or mutation functionality exists in this module.
"""
from __future__ import annotations

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
from .scanner import ScanCancelled, ScanReport, scan_directory

GITHUB_PROFILE = "https://github.com/canyrtcn"
GITHUB_REPO = "https://github.com/canyrtcn/FileDNA"

BG = "#0d131d"
PANEL = "#151e2b"
FIELD = "#1a2637"
BORDER = "#29384b"
FG = "#f1f4f8"
MUTED = "#9eafc5"
DIM = "#74869d"
ACCENT = "#428ce5"
HOVER = "#5c9ded"
GREEN = "#67cba3"
AMBER = "#e6b667"

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
    "safe": ("Read-only · Files are never deleted or modified",
             "Salt okunur · Dosyalar silinmez veya değiştirilmez"),
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
}


def asset_path(name: str) -> Path:
    """Resolve assets in the source tree or PyInstaller onefile extraction."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "assets" / name


class ActionButton(tk.Frame):
    """A two-line clickable button, with deliberate active and disabled states."""
    def __init__(self, parent, callback, *, primary=False, width=130):
        super().__init__(parent, bg=BORDER, width=width)
        self.pack_propagate(False)
        self.callback = callback
        self.primary = primary
        self.enabled = True
        self.surface = tk.Frame(self, bg=ACCENT if primary else FIELD)
        self.surface.pack(fill="both", expand=True, padx=1, pady=1)
        self.main = tk.Label(self.surface, bg=self.surface["bg"], fg=FG,
                             font=("Segoe UI Semibold", 10))
        self.main.pack(pady=(9, 0))
        self.small = tk.Label(self.surface, bg=self.surface["bg"],
                              fg="#e3efff" if primary else MUTED,
                              font=("Segoe UI", 8))
        self.small.pack(pady=(1, 9))
        for child in (self, self.surface, self.main, self.small):
            child.bind("<Button-1>", lambda _: self.click())
            child.bind("<Enter>", lambda _: self.paint(True))
            child.bind("<Leave>", lambda _: self.paint(False))
        self.paint(False)

    def set_text(self, primary: str, secondary: str):
        self.main.config(text=primary)
        self.small.config(text=secondary)

    def enable(self, value: bool):
        self.enabled = value
        self.paint(False)
        for label in (self.main, self.small):
            label.configure(cursor="hand2" if value else "arrow")

    def paint(self, hover: bool):
        background = (HOVER if hover else ACCENT) if self.primary else ("#223956" if hover else FIELD)
        if not self.enabled:
            background = BG
        self.surface.configure(bg=background)
        self.main.configure(bg=background, fg=FG if self.enabled else DIM)
        self.small.configure(bg=background,
                             fg=("#e3efff" if self.primary else MUTED) if self.enabled else DIM)

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
        self._started: float | None = None
        self._state = "ready"
        self._fraction = 0.0
        self._after_id: str | None = None
        self._icon_full = None
        self._icon_small = None
        self._install_icon()
        self._style()
        self._layout()
        self._translate()
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
                        font=("Segoe UI Semibold", 10))
        style.map("DNA.Treeview", background=[("selected", "#223956")],
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
        self._label(header, "FileDNA", size=23, bold=True).pack(side="left")
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
        entry_border = tk.Frame(controls, bg=BORDER, height=59)
        entry_border.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry_border.pack_propagate(False)
        self.folder_input = tk.Entry(entry_border, textvariable=self.folder,
                                     bg=FIELD, fg=FG, insertbackground=FG,
                                     font=("Segoe UI", 10), relief="flat",
                                     highlightthickness=0, borderwidth=0)
        self.folder_input.pack(fill="both", expand=True, padx=1, pady=1, ipadx=14)
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
            outline = tk.Frame(cards, bg=BORDER, height=125)
            outline.grid(row=0, column=index, sticky="nsew",
                         padx=(0 if index == 0 else 5, 0 if index == 3 else 5))
            body = tk.Frame(outline, bg=PANEL, padx=18, pady=13)
            body.pack(fill="both", expand=True, padx=1, pady=1)
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
        self.export_button = ActionButton(results_row, self._export_json, width=142)
        self.export_button.pack(side="right", fill="y")
        self.open_button = ActionButton(results_row, self._open_selected, width=174)
        self.open_button.pack(side="right", fill="y", padx=(0, 10))
        self.export_button.enable(False)
        self.open_button.enable(False)

        table_border = tk.Frame(root, bg=BORDER)
        table_border.pack(fill="both", expand=True, pady=(0, 15))
        table_container = tk.Frame(table_border, bg=PANEL)
        table_container.pack(fill="both", expand=True, padx=1, pady=1)
        self.tree = ttk.Treeview(table_container, columns=("size", "count", "hash"),
                                 show="tree headings", height=6, style="DNA.Treeview")
        self.tree.column("#0", width=500, minwidth=220, stretch=True)
        self.tree.column("size", width=125, stretch=False, anchor="e")
        self.tree.column("count", width=78, stretch=False, anchor="center")
        self.tree.column("hash", width=170, stretch=False)
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview,
                                  style="DNA.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("group", foreground=GREEN)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection)
        self.tree.bind("<Double-1>", lambda _: self._open_selected())
        self.empty = tk.Frame(table_container, bg=PANEL, padx=15, pady=15)
        self._label(self.empty, "⌕", size=48, color=DIM, bg=PANEL).pack()
        self.empty_title = self._label(self.empty, size=14, bold=True, bg=PANEL)
        self.empty_title.pack(pady=(1, 7))
        self.empty_help = self._label(self.empty, size=10, color=MUTED, bg=PANEL)
        self.empty_help.pack()
        self.empty.place(relx=.50, rely=.55, anchor="center")
        self.empty.lift()

        status_border = tk.Frame(root, bg=BORDER, height=65)
        status_border.pack(fill="x", pady=(0, 10))
        status_border.pack_propagate(False)
        status = tk.Frame(status_border, bg=PANEL, padx=15, pady=10)
        status.pack(fill="both", expand=True, padx=1, pady=1)
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
        self.folder_title.configure(text=self._both("folder")[0])
        self.folder_sub.configure(text=self._both("folder")[1])
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

    def _browse(self):
        chosen = filedialog.askdirectory(title=self._tr("folder"), mustexist=True)
        if chosen:
            self.folder.set(chosen)

    def _start_scan(self):
        if self._worker is not None and self._worker.is_alive():
            return
        root = Path(self.folder.get()).expanduser()
        if root.is_symlink() or not root.is_dir():
            messagebox.showerror(self._tr("scan_error"), self._tr("invalid"))
            return
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
        try:
            while True:
                event = self._queue.get_nowait()
                if event[0] == "progress":
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
        except queue.Empty:
            pass
        if self._started is not None:
            self.elapsed_value.configure(text=f"{int(time.monotonic() - self._started)}s")
        if self.winfo_exists():
            self._after_id = self.after(90, self._poll)

    def _draw_progress(self):
        self.progress.delete("all")
        width, height = max(1, self.progress.winfo_width()), max(1, self.progress.winfo_height())
        self.progress.create_rectangle(0, 0, width, height, fill=FIELD, outline="")
        if self._fraction:
            self.progress.create_rectangle(0, 0, round(width * self._fraction),
                                           height, fill=ACCENT, outline="")

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
            parent = self.tree.insert("", "end", text=f"#{idx} · {len(group.paths)} files",
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
        self._finish("finished")
        self._translate()
        self.status_detail.configure(text=f"{len(report.groups)} {self._tr('groups').lower()}")
        if report.errors:
            messagebox.showwarning(self._tr("partial"),
                                   self._tr("partial_help").format(count=len(report.errors)))

    def _on_selection(self, _event=None):
        selected = self.tree.selection()
        self.open_button.enable(bool(selected and selected[0] in self._row_paths))

    def _open_selected(self):
        selected = self.tree.selection()
        filename = self._row_paths.get(selected[0]) if selected else None
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
        self._stop_event.set()
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
