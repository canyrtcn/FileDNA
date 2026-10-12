"""FileDNA desktop GUI, implemented with Python's standard-library Tkinter."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import format_size
from .scanner import ScanCancelled, ScanReport, scan_directory

BG = "#0d111a"
SURFACE = "#171e2c"
SURFACE_ALT = "#1e293b"
LINE = "#2b394d"
FG = "#eff5ff"
MUTED = "#94a3b8"
ACCENT = "#4c9cf6"
ACCENT_HOVER = "#70b2ff"
GREEN = "#4adea8"


class FileDNAApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FileDNA  |  Duplicate File Finder")
        self.geometry("1050x725")
        self.minsize(780, 525)
        self.configure(bg=BG)
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._cancel = threading.Event()
        self._worker: threading.Thread | None = None
        self._report: ScanReport | None = None
        self._rows_to_paths: dict[str, str] = {}
        self.folder = tk.StringVar(value=str(Path.home()))
        self.status = tk.StringVar(value="Klasör seçip taramayı başlatın.")
        self._create_style()
        self._create_layout()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Card.TLabel", background=SURFACE, foreground=FG)
        style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
        style.configure("Header.TLabel", background=BG, foreground=FG, font=("Segoe UI Semibold", 24))
        style.configure("Metric.TLabel", background=SURFACE, foreground=FG, font=("Segoe UI Semibold", 22))
        style.configure("TEntry", fieldbackground=SURFACE_ALT, foreground=FG, bordercolor=LINE,
                        insertcolor=FG, padding=(10, 9))
        style.map("TEntry", bordercolor=[("focus", ACCENT)])
        style.configure("Primary.TButton", background=ACCENT, foreground="#071526", borderwidth=0,
                        padding=(16, 9), font=("Segoe UI Semibold", 10))
        style.map("Primary.TButton", background=[("active", ACCENT_HOVER), ("disabled", LINE)],
                  foreground=[("disabled", MUTED)])
        style.configure("Secondary.TButton", background=SURFACE_ALT, foreground=FG, borderwidth=0,
                        padding=(12, 9), font=("Segoe UI", 10))
        style.map("Secondary.TButton", background=[("active", LINE), ("disabled", SURFACE)])
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=FG,
                        borderwidth=0, rowheight=29, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=SURFACE_ALT, foreground=MUTED,
                        relief="flat", padding=8, font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#24476f")], foreground=[("selected", FG)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=SURFACE_ALT,
                        bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)

    def _create_layout(self) -> None:
        main = ttk.Frame(self, padding=(28, 23))
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="FileDNA", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="SHA-256  •  Read-only  •  Local", style="Muted.TLabel").pack(
            side="right", pady=(13, 0))
        ttk.Label(main, text="Dosyalarınızı silmeden gerçek kopyaları tespit edin.",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 22))

        picker = ttk.Frame(main)
        picker.pack(fill="x")
        self.folder_entry = ttk.Entry(picker, textvariable=self.folder)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(picker, text="Gözat", style="Secondary.TButton",
                   command=self._browse).pack(side="left", padx=(9, 0))
        self.scan_button = ttk.Button(picker, text="Taramayı Başlat", style="Primary.TButton",
                                      command=self._start_scan)
        self.scan_button.pack(side="left", padx=(9, 0))
        self.cancel_button = ttk.Button(picker, text="Durdur", style="Secondary.TButton",
                                        command=self._stop_scan, state="disabled")
        self.cancel_button.pack(side="left", padx=(9, 0))

        metrics = ttk.Frame(main)
        metrics.pack(fill="x", pady=(22, 18))
        self.metric_values: dict[str, ttk.Label] = {}
        for i, (key, heading) in enumerate((
            ("files", "İncelenen Dosya"),
            ("groups", "Kopya Grubu"),
            ("duplicates", "Fazladan Kopya"),
            ("space", "Kazanılabilir Alan"),
        )):
            metrics.columnconfigure(i, weight=1, uniform="metrics")
            card = ttk.Frame(metrics, style="Card.TFrame", padding=(16, 13))
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            ttk.Label(card, text=heading, style="CardMuted.TLabel").pack(anchor="w")
            lbl = ttk.Label(card, text="—", style="Metric.TLabel")
            lbl.pack(anchor="w", pady=(7, 0))
            self.metric_values[key] = lbl

        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=(2, 7))
        ttk.Label(bar, text="BULUNAN KOPYALAR", foreground=MUTED,
                  font=("Segoe UI Semibold", 10)).pack(side="left")
        self.export_button = ttk.Button(bar, text="JSON Raporu Kaydet", style="Secondary.TButton",
                                        command=self._export, state="disabled")
        self.export_button.pack(side="right")
        self.open_button = ttk.Button(bar, text="Dosyanın Konumunu Aç", style="Secondary.TButton",
                                      command=self._open_selected, state="disabled")
        self.open_button.pack(side="right", padx=(0, 8))

        table_wrapper = ttk.Frame(main, style="Card.TFrame")
        table_wrapper.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table_wrapper, columns=("size", "hash"), show="tree headings")
        self.tree.heading("#0", text="Grup / Dosya Yolu")
        self.tree.heading("size", text="Boyut")
        self.tree.heading("hash", text="SHA-256")
        self.tree.column("#0", width=520, minwidth=230, stretch=True)
        self.tree.column("size", width=115, anchor="e", stretch=False)
        self.tree.column("hash", width=170, stretch=False)
        scrollbar = ttk.Scrollbar(table_wrapper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("group", foreground=GREEN)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection)
        self.tree.bind("<Double-1>", lambda _: self._open_selected())

        footer = ttk.Frame(main)
        footer.pack(fill="x", pady=(12, 0))
        self.progress = ttk.Progressbar(footer, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(main, text="GÜVENLİ MOD   •   FileDNA dosyaları taşımaz, değiştirmez veya silmez.",
                  foreground=GREEN, font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 0))

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Taranacak klasörü seçin", mustexist=True)
        if folder:
            self.folder.set(folder)

    def _start_scan(self) -> None:
        path = Path(self.folder.get()).expanduser()
        if path.is_symlink() or not path.is_dir():
            messagebox.showerror("Geçersiz klasör", "Lütfen mevcut, sembolik bağ olmayan bir klasör seçin.")
            return
        self._cancel = threading.Event()
        self._report = None
        self._rows_to_paths.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for lbl in self.metric_values.values():
            lbl.config(text="—")
        self.progress.configure(value=0, mode="indeterminate")
        self.progress.start(12)
        self.status.set("Dosyalar listeleniyor…")
        self.scan_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.export_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.folder_entry.configure(state="disabled")
        self._worker = threading.Thread(target=self._scan_worker, args=(path, self._cancel), daemon=True)
        self._worker.start()

    def _scan_worker(self, root: Path, cancel: threading.Event) -> None:
        try:
            report = scan_directory(root, cancel_event=cancel, progress=lambda p, n, t: self._queue.put(
                ("progress", p, n, t)))
            self._queue.put(("result", report))
        except ScanCancelled:
            self._queue.put(("cancelled",))
        except Exception as exc:  # show a readable error instead of silently killing the worker
            self._queue.put(("error", str(exc)))

    def _stop_scan(self) -> None:
        self._cancel.set()
        self.status.set("Tarama durduruluyor…")
        self.cancel_button.configure(state="disabled")

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg[0] == "progress":
                    _, phase, current, total = msg
                    if phase == "discovering":
                        self.status.set(f"Dosyalar listeleniyor… {current:,} dosya")
                    elif phase == "hashing":
                        if str(self.progress.cget("mode")) != "determinate":
                            self.progress.stop()
                            self.progress.configure(mode="determinate")
                        self.progress.configure(value=(100 * current / total) if total else 100)
                        self.status.set(f"SHA-256 hesaplanıyor… {current:,} / {total:,}")
                elif msg[0] == "result":
                    self._show_result(msg[1])
                elif msg[0] == "cancelled":
                    self._finish_scan("Tarama iptal edildi. Hiçbir dosya değiştirilmedi.")
                elif msg[0] == "error":
                    self._finish_scan("Tarama başarısız oldu.")
                    messagebox.showerror("Tarama hatası", msg[1])
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._poll_queue)

    def _finish_scan(self, message: str) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100 if self._report else 0)
        self.status.set(message)
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.folder_entry.configure(state="normal")

    def _show_result(self, report: ScanReport) -> None:
        self._report = report
        self.metric_values["files"].configure(text=f"{report.examined_files:,}")
        self.metric_values["groups"].configure(text=f"{len(report.groups):,}")
        self.metric_values["duplicates"].configure(text=f"{report.duplicate_files:,}")
        self.metric_values["space"].configure(text=format_size(report.reclaimable_bytes))
        for i, group in enumerate(report.groups, 1):
            group_id = self.tree.insert("", "end", text=f"#{i}  •  {len(group.paths)} eşleşen dosya",
                                        values=(format_size(group.size_bytes), group.sha256[:18] + "…"),
                                        tags=("group",), open=i <= 5)
            for file in group.paths:
                row = self.tree.insert(group_id, "end", text=file,
                                       values=(format_size(group.size_bytes), ""))
                self._rows_to_paths[row] = file
        self.export_button.configure(state="normal")
        suffix = f" • {len(report.errors)} okuma hatası" if report.errors else ""
        self._finish_scan(f"Tarama tamamlandı. {len(report.groups)} kopya grubu bulundu{suffix}.")
        if report.errors:
            messagebox.showwarning("Eksik tarama", f"{len(report.errors)} dosya/klasör okunamadı. "
                                   "Ayrıntılar JSON raporunun errors alanında yer alıyor.")

    def _on_selection(self, _: tk.Event) -> None:
        selection = self.tree.selection()
        is_file = bool(selection and selection[0] in self._rows_to_paths)
        self.open_button.configure(state="normal" if is_file else "disabled")

    def _open_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        path = self._rows_to_paths.get(selection[0])
        if not path:
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
        except OSError as exc:
            messagebox.showerror("Konum açılamadı", str(exc))

    def _export(self) -> None:
        if self._report is None:
            return
        destination = filedialog.asksaveasfilename(
            title="JSON raporu kaydet", defaultextension=".json",
            initialfile="filedna-report.json", filetypes=[("JSON", "*.json")],
        )
        if not destination:
            return
        try:
            Path(destination).write_text(json.dumps(self._report.to_dict(), ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Rapor kaydedilemedi", str(exc))
        else:
            self.status.set(f"Rapor kaydedildi: {destination}")

    def _on_close(self) -> None:
        self._cancel.set()
        self.destroy()


def main() -> None:
    app = FileDNAApp()
    app.mainloop()


if __name__ == "__main__":
    main()
