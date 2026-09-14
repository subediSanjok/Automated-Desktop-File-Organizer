"""Modern Tkinter Graphical User Interface for Automated Desktop File Organizer."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from src.config import (
    AppConfig,
    get_desktop_dir,
    get_downloads_dir,
    load_config,
    save_config,
)
from src.history import MoveHistoryManager, MoveRecord
from src.organizer import FileOrganizer
from src.watcher import FileWatcher


class TkinterLogHandler(logging.Handler):
    """Thread-safe logging handler that pushes log records into a queue for Tkinter."""

    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.log_queue.put((record.levelno, msg))


class FileOrganizerGUI:
    """Main Application GUI Window."""

    def __init__(self, root: tk.Tk, config_path: Optional[Path | str] = None) -> None:
        self.root = root
        self.root.title("Automated Desktop & Downloads File Organizer")
        self.root.geometry("1020x750")
        self.root.minsize(850, 620)

        self.config_path = Path(config_path) if config_path else Path("config.json")
        self.config = load_config(self.config_path)

        # Logging setup
        self.log_queue: queue.Queue = queue.Queue()
        self.logger = logging.getLogger("gui_organizer")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            queue_handler = TkinterLogHandler(self.log_queue)
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
            queue_handler.setFormatter(formatter)
            self.logger.addHandler(queue_handler)

        # History Manager & Organizer
        self.history_manager = MoveHistoryManager()
        self.organizer = FileOrganizer(
            config=self.config,
            logger=self.logger,
            history_manager=self.history_manager,
        )
        self.watcher: Optional[FileWatcher] = None
        self.is_watching = False
        self.files_organized_count = 0
        self.category_counts: Dict[str, int] = {}

        # Configure styles & theme
        self._setup_theme()

        # Build UI layout
        self._build_header()
        self._build_tabs()

        # Start periodic background log reader
        self.root.after(100, self._process_log_queue)

        # Intercept window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_theme(self) -> None:
        """Configure modern visual styles for ttk widgets."""
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Color palette
        self.bg_color = "#f4f6f9"
        self.card_bg = "#ffffff"
        self.primary_color = "#2563eb"
        self.accent_green = "#10b981"
        self.accent_amber = "#f59e0b"
        self.accent_red = "#ef4444"
        self.text_dark = "#1e293b"
        self.text_muted = "#64748b"

        self.root.configure(bg=self.bg_color)

        self.style.configure(".", background=self.bg_color, foreground=self.text_dark, font=("Segoe UI", 10))
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.text_dark, background=self.bg_color)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground=self.text_muted, background=self.bg_color)
        self.style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.text_dark, background=self.card_bg)
        
        # Action Buttons
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.primary_color, foreground="#ffffff")
        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), background=self.accent_green, foreground="#ffffff")
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background=self.accent_red, foreground="#ffffff")
        self.style.configure("TNotebook", background=self.bg_color)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 8])

    def _build_header(self) -> None:
        """Create header banner."""
        header_frame = ttk.Frame(self.root, padding="16 12 16 8")
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(
            header_frame,
            text="📁 Automated Desktop & Downloads File Organizer",
            style="Header.TLabel",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(
            header_frame,
            text="Clean, categorize, monitor, or revert your folders safely with 1-click controls",
            style="SubHeader.TLabel",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

    def _build_tabs(self) -> None:
        """Create Notebook tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        # 1. Main Dashboard Tab
        self.tab_dashboard = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_dashboard, text=" ⚡ Dashboard & Live Monitor ")
        self._build_dashboard_tab()

        # 2. Undo & History Tab
        self.tab_history = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_history, text=" ↺ Undo & History ")
        self._build_history_tab()

        # 3. Category Rules Tab
        self.tab_categories = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_categories, text=" 📂 Categories & Rules ")
        self._build_categories_tab()

        # 4. Settings Tab
        self.tab_settings = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_settings, text=" ⚙️ Settings ")
        self._build_settings_tab()

    # ==========================================
    # DASHBOARD TAB
    # ==========================================
    def _build_dashboard_tab(self) -> None:
        # Top section: Target Directory & Presets Card
        dir_card = ttk.Frame(self.tab_dashboard, style="Card.TFrame", padding=14)
        dir_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(dir_card, text="Target Folder to Organize", style="Section.TLabel").pack(anchor="w")

        # Preset Buttons row
        presets_frame = ttk.Frame(dir_card, style="Card.TFrame")
        presets_frame.pack(fill=tk.X, pady=(8, 8))

        ttk.Label(presets_frame, text="Quick Presets: ", font=("Segoe UI", 9, "bold"), background=self.card_bg).pack(side=tk.LEFT)
        
        btn_desktop = ttk.Button(presets_frame, text="🖥️ Desktop", command=self._select_desktop)
        btn_desktop.pack(side=tk.LEFT, padx=4)

        btn_downloads = ttk.Button(presets_frame, text="📥 Downloads", command=self._select_downloads)
        btn_downloads.pack(side=tk.LEFT, padx=4)

        # Directory Entry and Browse
        input_frame = ttk.Frame(dir_card, style="Card.TFrame")
        input_frame.pack(fill=tk.X, pady=(4, 6))

        self.dir_var = tk.StringVar(value=str(self.config.watch_directory))
        self.dir_entry = ttk.Entry(input_frame, textvariable=self.dir_var, font=("Segoe UI", 10))
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_browse = ttk.Button(input_frame, text="Browse...", command=self._browse_directory)
        btn_browse.pack(side=tk.LEFT, padx=(0, 4))

        btn_open = ttk.Button(input_frame, text="Open in Explorer", command=self._open_in_explorer)
        btn_open.pack(side=tk.LEFT)

        # Controls & Status Card
        ctrl_card = ttk.Frame(self.tab_dashboard, style="Card.TFrame", padding=14)
        ctrl_card.pack(fill=tk.X, pady=(0, 10))

        # Status row
        status_row = ttk.Frame(ctrl_card, style="Card.TFrame")
        status_row.pack(fill=tk.X, pady=(0, 10))

        self.status_indicator = tk.Label(
            status_row,
            text="● Live Watcher Inactive",
            font=("Segoe UI", 10, "bold"),
            fg="#ef4444",
            bg=self.card_bg,
        )
        self.status_indicator.pack(side=tk.LEFT)

        self.stats_label = tk.Label(
            status_row,
            text="Organized in Session: 0 files",
            font=("Segoe UI", 10),
            fg=self.text_muted,
            bg=self.card_bg,
        )
        self.stats_label.pack(side=tk.RIGHT)

        # Action Buttons row
        btn_row = ttk.Frame(ctrl_card, style="Card.TFrame")
        btn_row.pack(fill=tk.X)

        self.btn_toggle_watcher = tk.Button(
            btn_row,
            text="🟢 Start Live Watcher",
            font=("Segoe UI", 10, "bold"),
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._toggle_watcher,
        )
        self.btn_toggle_watcher.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_organize_now = tk.Button(
            btn_row,
            text="⚡ Organize Files Now",
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._batch_organize_now,
        )
        self.btn_organize_now.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_revert_last = tk.Button(
            btn_row,
            text="↺ Undo Last Batch",
            font=("Segoe UI", 10, "bold"),
            bg="#f59e0b",
            fg="#ffffff",
            activebackground="#d97706",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._revert_last_batch,
        )
        self.btn_revert_last.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_revert_all = tk.Button(
            btn_row,
            text="↺ Revert Entire Folder",
            font=("Segoe UI", 10),
            bg="#64748b",
            fg="#ffffff",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._revert_entire_folder,
        )
        self.btn_revert_all.pack(side=tk.LEFT)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(ctrl_card, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(10, 0))

        # Log & Activity Card
        log_card = ttk.Frame(self.tab_dashboard, style="Card.TFrame", padding=14)
        log_card.pack(fill=tk.BOTH, expand=True)

        log_header = ttk.Frame(log_card, style="Card.TFrame")
        log_header.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(log_header, text="Live Activity Log", style="Section.TLabel").pack(side=tk.LEFT)
        
        btn_clear_log = ttk.Button(log_header, text="Clear Log", command=self._clear_log)
        btn_clear_log.pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            log_card,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            relief="flat",
            padx=8,
            pady=8,
        )
        log_scroll = ttk.Scrollbar(log_card, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure Log Text Color Tags
        self.log_text.tag_config("INFO", foreground="#38bdf8")
        self.log_text.tag_config("SUCCESS", foreground="#4ade80")
        self.log_text.tag_config("WARNING", foreground="#facc15")
        self.log_text.tag_config("ERROR", foreground="#f87171")
        self.log_text.tag_config("CRITICAL", foreground="#f43f5e")

    # ==========================================
    # UNDO & HISTORY TAB
    # ==========================================
    def _build_history_tab(self) -> None:
        hist_card = ttk.Frame(self.tab_history, style="Card.TFrame", padding=14)
        hist_card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            hist_card,
            text="Organization History & Revert Options",
            style="Section.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        desc_lbl = ttk.Label(
            hist_card,
            text="Select previous moves or batches below to revert files back to their original root folder.",
            font=("Segoe UI", 9),
            foreground=self.text_muted,
            background=self.card_bg,
        )
        desc_lbl.pack(anchor="w", pady=(0, 10))

        # Treeview for history
        tree_frame = ttk.Frame(hist_card, style="Card.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("time", "batch", "file", "category", "status")
        self.hist_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=14)
        self.hist_tree.heading("time", text="Date / Time")
        self.hist_tree.heading("batch", text="Batch ID")
        self.hist_tree.heading("file", text="File Name")
        self.hist_tree.heading("category", text="Organized Folder")
        self.hist_tree.heading("status", text="Status")

        self.hist_tree.column("time", width=140, stretch=False)
        self.hist_tree.column("batch", width=120, stretch=False)
        self.hist_tree.column("file", width=260, stretch=True)
        self.hist_tree.column("category", width=130, stretch=False)
        self.hist_tree.column("status", width=100, stretch=False)

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=tree_scroll.set)

        self.hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(hist_card, style="Card.TFrame")
        btn_frame.pack(fill=tk.X)

        btn_revert_sel_batch = ttk.Button(
            btn_frame,
            text="↺ Revert Selected Batch",
            command=self._revert_selected_history_batch,
        )
        btn_revert_sel_batch.pack(side=tk.LEFT, padx=(0, 8))

        btn_revert_all_dir = ttk.Button(
            btn_frame,
            text="↺ Revert Entire Monitored Folder",
            command=self._revert_entire_folder,
        )
        btn_revert_all_dir.pack(side=tk.LEFT, padx=(0, 8))

        btn_refresh_hist = ttk.Button(
            btn_frame,
            text="Refresh History",
            command=self._refresh_history_tree,
        )
        btn_refresh_hist.pack(side=tk.RIGHT)

        self._refresh_history_tree()

    def _refresh_history_tree(self) -> None:
        for item in self.hist_tree.get_children():
            self.hist_tree.delete(item)

        records = self.history_manager.records
        for r in reversed(records[-200:]):
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.timestamp))
            fname = Path(r.dest_path).name
            status = "Reverted" if r.reverted else "Organized"
            self.hist_tree.insert(
                "",
                tk.END,
                values=(time_str, r.batch_id, fname, r.category, status),
            )

    def _revert_selected_history_batch(self) -> None:
        selected = self.hist_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a row from the history table.")
            return

        batch_id = self.hist_tree.item(selected[0])["values"][1]
        if messagebox.askyesno("Confirm Undo", f"Revert all files belonging to batch '{batch_id}'?"):
            self._execute_batch_revert(batch_id)

    # ==========================================
    # CATEGORIES TAB
    # ==========================================
    def _build_categories_tab(self) -> None:
        cat_card = ttk.Frame(self.tab_categories, style="Card.TFrame", padding=14)
        cat_card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(cat_card, text="Configured Categories and File Extensions", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        # Treeview for categories
        tree_frame = ttk.Frame(cat_card, style="Card.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("category", "extensions")
        self.cat_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        self.cat_tree.heading("category", text="Folder / Category Name")
        self.cat_tree.heading("extensions", text="Assigned Extensions")
        self.cat_tree.column("category", width=180, stretch=False)
        self.cat_tree.column("extensions", width=600, stretch=True)

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=tree_scroll.set)

        self.cat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.cat_tree.bind("<<TreeviewSelect>>", self._on_category_select)

        # Editor Frame
        edit_frame = ttk.Frame(cat_card, style="Card.TFrame")
        edit_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(edit_frame, text="Category:", background=self.card_bg, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.cat_name_var = tk.StringVar()
        self.cat_name_entry = ttk.Entry(edit_frame, textvariable=self.cat_name_var, width=20)
        self.cat_name_entry.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(edit_frame, text="Extensions (comma-separated, e.g. .pdf, .docx):", background=self.card_bg, font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=4, pady=4, sticky="w")
        self.cat_ext_var = tk.StringVar()
        self.cat_ext_entry = ttk.Entry(edit_frame, textvariable=self.cat_ext_var)
        self.cat_ext_entry.grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        edit_frame.columnconfigure(3, weight=1)

        # Action buttons
        btn_frame = ttk.Frame(cat_card, style="Card.TFrame")
        btn_frame.pack(fill=tk.X)

        btn_add_update = ttk.Button(btn_frame, text="Save / Update Category", command=self._save_category_item)
        btn_add_update.pack(side=tk.LEFT, padx=(0, 6))

        btn_delete = ttk.Button(btn_frame, text="Delete Selected", command=self._delete_category_item)
        btn_delete.pack(side=tk.LEFT, padx=(0, 6))

        btn_save_disk = ttk.Button(btn_frame, text="💾 Save to config.json", command=self._save_all_to_config_file)
        btn_save_disk.pack(side=tk.RIGHT)

        self._refresh_categories_tree()

    # ==========================================
    # SETTINGS TAB
    # ==========================================
    def _build_settings_tab(self) -> None:
        settings_card = ttk.Frame(self.tab_settings, style="Card.TFrame", padding=14)
        settings_card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(settings_card, text="General & Stability Settings", style="Section.TLabel").pack(anchor="w", pady=(0, 12))

        # Default fallback category
        f1 = ttk.Frame(settings_card, style="Card.TFrame")
        f1.pack(fill=tk.X, pady=6)
        ttk.Label(f1, text="Default Fallback Category:", width=30, background=self.card_bg).pack(side=tk.LEFT)
        self.default_cat_var = tk.StringVar(value=self.config.default_category)
        ttk.Entry(f1, textvariable=self.default_cat_var, width=25).pack(side=tk.LEFT)

        # Ignored extensions
        f2 = ttk.Frame(settings_card, style="Card.TFrame")
        f2.pack(fill=tk.X, pady=6)
        ttk.Label(f2, text="Ignored Temporary Extensions:", width=30, background=self.card_bg).pack(side=tk.LEFT)
        self.ignored_ext_var = tk.StringVar(value=", ".join(self.config.ignored_extensions))
        ttk.Entry(f2, textvariable=self.ignored_ext_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Stability interval
        f3 = ttk.Frame(settings_card, style="Card.TFrame")
        f3.pack(fill=tk.X, pady=6)
        ttk.Label(f3, text="File Stability Check Interval (sec):", width=30, background=self.card_bg).pack(side=tk.LEFT)
        self.stab_interval_var = tk.DoubleVar(value=self.config.stability.check_interval_seconds)
        ttk.Entry(f3, textvariable=self.stab_interval_var, width=10).pack(side=tk.LEFT)

        # Stability checks
        f4 = ttk.Frame(settings_card, style="Card.TFrame")
        f4.pack(fill=tk.X, pady=6)
        ttk.Label(f4, text="Consecutive Stable Checks:", width=30, background=self.card_bg).pack(side=tk.LEFT)
        self.stab_checks_var = tk.IntVar(value=self.config.stability.stable_checks)
        ttk.Entry(f4, textvariable=self.stab_checks_var, width=10).pack(side=tk.LEFT)

        # Save settings button
        btn_save_settings = ttk.Button(
            settings_card,
            text="💾 Save Settings to config.json",
            command=self._save_all_to_config_file,
        )
        btn_save_settings.pack(anchor="w", pady=(16, 0))

    # ==========================================
    # LOG & STATS MANAGEMENT
    # ==========================================
    def _process_log_queue(self) -> None:
        """Poll the log queue and insert new entries into the GUI text widget."""
        while not self.log_queue.empty():
            levelno, msg = self.log_queue.get_nowait()
            tag = "INFO"
            if levelno >= logging.CRITICAL:
                tag = "CRITICAL"
            elif levelno >= logging.ERROR:
                tag = "ERROR"
            elif levelno >= logging.WARNING:
                tag = "WARNING"
            elif "Moved" in msg or "Reverted" in msg or "Restored" in msg or "completed" in msg or "started" in msg:
                tag = "SUCCESS"

            self.log_text.insert(tk.END, msg + "\n", tag)
            self.log_text.see(tk.END)

        self.root.after(100, self._process_log_queue)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _update_stats_display(self) -> None:
        self.stats_label.config(text=f"Organized in Session: {self.files_organized_count} files")

    # ==========================================
    # DIRECTORY ACTIONS & PRESETS
    # ==========================================
    def _select_desktop(self) -> None:
        desktop = get_desktop_dir()
        self.dir_var.set(str(desktop))
        self._update_active_watch_directory(desktop)

    def _select_downloads(self) -> None:
        downloads = get_downloads_dir()
        self.dir_var.set(str(downloads))
        self._update_active_watch_directory(downloads)

    def _browse_directory(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get())
        if chosen:
            self.dir_var.set(chosen)
            self._update_active_watch_directory(Path(chosen))

    def _update_active_watch_directory(self, new_dir: Path) -> None:
        self.config.watch_directory = new_dir
        self.organizer.config.watch_directory = new_dir
        self.logger.info(f"Active target directory switched to: {new_dir}")
        if self.is_watching:
            self.logger.info("Restarting watcher for the newly selected directory...")
            self._stop_watcher()
            self._start_watcher()

    def _open_in_explorer(self) -> None:
        path = self.dir_var.get()
        if os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
        else:
            messagebox.showwarning("Directory Not Found", f"The directory does not exist:\n{path}")

    # ==========================================
    # WATCHER CONTROL
    # ==========================================
    def _toggle_watcher(self) -> None:
        if self.is_watching:
            self._stop_watcher()
        else:
            self._start_watcher()

    def _start_watcher(self) -> None:
        target_dir = Path(self.dir_var.get())
        if not target_dir.exists():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create watch directory: {e}")
                return

        self.config.watch_directory = target_dir
        self.organizer.config = self.config

        self.watcher = FileWatcher(config=self.config, organizer=self.organizer, logger=self.logger)
        try:
            self.watcher.start()
            self.is_watching = True
            self.status_indicator.config(text="🟢 Live Watcher Active", fg="#10b981")
            self.btn_toggle_watcher.config(
                text="🔴 Stop Live Watcher",
                bg="#ef4444",
                activebackground="#dc2626",
            )
        except Exception as e:
            self.logger.error(f"Failed to start file watcher: {e}")
            messagebox.showerror("Watcher Error", f"Failed to start file watcher:\n{e}")

    def _stop_watcher(self) -> None:
        if self.watcher:
            try:
                self.watcher.stop()
            except Exception as e:
                self.logger.error(f"Error stopping watcher: {e}")
            self.watcher = None

        self.is_watching = False
        self.status_indicator.config(text="● Live Watcher Inactive", fg="#ef4444")
        self.btn_toggle_watcher.config(
            text="🟢 Start Live Watcher",
            bg="#10b981",
            activebackground="#059669",
        )

    # ==========================================
    # BATCH SWEEP
    # ==========================================
    def _batch_organize_now(self) -> None:
        target_dir = Path(self.dir_var.get())
        if not target_dir.exists() or not target_dir.is_dir():
            messagebox.showerror("Error", f"Target directory does not exist:\n{target_dir}")
            return

        self.btn_organize_now.config(state=tk.DISABLED)
        self.progress_var.set(0)

        def run_batch() -> None:
            def progress(current: int, total: int, filename: str) -> None:
                percent = (current / total) * 100 if total > 0 else 100
                self.root.after(0, lambda: self.progress_var.set(percent))

            moved = self.organizer.organize_directory(target_dir, progress_callback=progress)
            self.files_organized_count += len(moved)

            def finish() -> None:
                self.progress_var.set(100)
                self.btn_organize_now.config(state=tk.NORMAL)
                self._update_stats_display()
                self._refresh_history_tree()
                messagebox.showinfo(
                    "Organization Complete",
                    f"Successfully organized {len(moved)} files in:\n{target_dir}",
                )

            self.root.after(0, finish)

        threading.Thread(target=run_batch, daemon=True).start()

    # ==========================================
    # REVERT / UNDO HANDLERS
    # ==========================================
    def _revert_last_batch(self) -> None:
        batches = self.history_manager.get_batches()
        if not batches:
            messagebox.showinfo("Nothing to Undo", "No recorded organization batches found.")
            return

        last_batch = batches[0]
        records = self.history_manager.get_records_for_batch(last_batch)
        if not records:
            messagebox.showinfo("Nothing to Undo", "The last batch was already reverted.")
            return

        if messagebox.askyesno(
            "Confirm Undo",
            f"Undo the most recent batch ({len(records)} files) and restore them to their original locations?",
        ):
            self._execute_batch_revert(last_batch)

    def _execute_batch_revert(self, batch_id: str) -> None:
        self.progress_var.set(0)

        def run_revert() -> None:
            def progress(current: int, total: int, filename: str) -> None:
                percent = (current / total) * 100 if total > 0 else 100
                self.root.after(0, lambda: self.progress_var.set(percent))

            restored = self.organizer.revert_batch(batch_id, progress_callback=progress)

            def finish() -> None:
                self.progress_var.set(100)
                self._refresh_history_tree()
                messagebox.showinfo(
                    "Revert Complete",
                    f"Successfully restored {len(restored)} files to their original folder.",
                )

            self.root.after(0, finish)

        threading.Thread(target=run_revert, daemon=True).start()

    def _revert_entire_folder(self) -> None:
        target_dir = Path(self.dir_var.get())
        if not target_dir.exists() or not target_dir.is_dir():
            messagebox.showerror("Error", f"Directory does not exist: {target_dir}")
            return

        confirm = messagebox.askyesno(
            "Confirm Full Revert",
            f"This will move ALL files from categorized subfolders (Documents, Images, etc.)\n"
            f"back to the main root folder:\n{target_dir}\n\n"
            f"Empty category folders will be removed.\nDo you want to proceed?",
        )
        if not confirm:
            return

        self.progress_var.set(0)

        def run_dir_revert() -> None:
            def progress(current: int, total: int, filename: str) -> None:
                percent = (current / total) * 100 if total > 0 else 100
                self.root.after(0, lambda: self.progress_var.set(percent))

            restored = self.organizer.revert_directory(target_dir, progress_callback=progress)

            def finish() -> None:
                self.progress_var.set(100)
                self._refresh_history_tree()
                messagebox.showinfo(
                    "Full Folder Revert Complete",
                    f"Successfully restored {len(restored)} files back into:\n{target_dir}",
                )

            self.root.after(0, finish)

        threading.Thread(target=run_dir_revert, daemon=True).start()

    # ==========================================
    # CATEGORIES MANAGEMENT
    # ==========================================
    def _refresh_categories_tree(self) -> None:
        for item in self.cat_tree.get_children():
            self.cat_tree.delete(item)

        for cat, exts in self.config.categories.items():
            self.cat_tree.insert("", tk.END, values=(cat, ", ".join(exts)))

    def _on_category_select(self, _event: tk.Event) -> None:
        selected = self.cat_tree.selection()
        if not selected:
            return
        item = self.cat_tree.item(selected[0])
        cat, exts = item["values"]
        self.cat_name_var.set(str(cat))
        self.cat_ext_var.set(str(exts))

    def _save_category_item(self) -> None:
        cat_name = self.cat_name_var.get().strip()
        raw_exts = self.cat_ext_var.get().strip()

        if not cat_name:
            messagebox.showwarning("Missing Name", "Please enter a category name.")
            return

        ext_list = [
            e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
            for e in raw_exts.split(",")
            if e.strip()
        ]

        self.config.categories[cat_name] = ext_list
        self.config._rebuild_lookup_cache()
        self._refresh_categories_tree()
        self.logger.info(f"Updated category '{cat_name}' with {len(ext_list)} extensions.")

    def _delete_category_item(self) -> None:
        selected = self.cat_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a category from the list to delete.")
            return

        cat_name = self.cat_tree.item(selected[0])["values"][0]
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete category '{cat_name}'?"):
            if cat_name in self.config.categories:
                del self.config.categories[cat_name]
                self.config._rebuild_lookup_cache()
                self._refresh_categories_tree()
                self.cat_name_var.set("")
                self.cat_ext_var.set("")
                self.logger.info(f"Deleted category '{cat_name}'.")

    # ==========================================
    # SAVE SETTINGS TO DISK
    # ==========================================
    def _save_all_to_config_file(self) -> None:
        try:
            self.config.watch_directory = Path(self.dir_var.get())
            self.config.default_category = self.default_cat_var.get().strip() or "Others"
            
            raw_ignored = self.ignored_ext_var.get()
            self.config.ignored_extensions = [
                e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
                for e in raw_ignored.split(",")
                if e.strip()
            ]
            self.config.stability.check_interval_seconds = float(self.stab_interval_var.get())
            self.config.stability.stable_checks = int(self.stab_checks_var.get())
            self.config._rebuild_lookup_cache()

            saved_path = save_config(self.config, self.config_path)
            self.logger.info(f"Configuration successfully saved to: {saved_path.resolve()}")
            messagebox.showinfo("Saved", f"Configuration successfully saved to:\n{saved_path.resolve()}")
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            messagebox.showerror("Save Error", f"Failed to save configuration:\n{e}")

    # ==========================================
    # WINDOW CLOSE HANDLER
    # ==========================================
    def _on_closing(self) -> None:
        if self.is_watching:
            self._stop_watcher()
        self.root.destroy()


def launch_gui(config_path: Optional[Path | str] = None) -> None:
    """Entry point to start the Tkinter GUI."""
    root = tk.Tk()
    _app = FileOrganizerGUI(root, config_path=config_path)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
