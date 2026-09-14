"""Unit and integration tests for GUI, batch sweep, and configuration persistence."""

import os
import tkinter as tk
from pathlib import Path
from src.config import (
    AppConfig,
    StabilityConfig,
    get_desktop_dir,
    get_downloads_dir,
    load_config,
    save_config,
)
from src.organizer import FileOrganizer
from src.gui import FileOrganizerGUI, TkinterLogHandler
import queue
import logging


def test_get_desktop_and_downloads_dir() -> None:
    desktop = get_desktop_dir()
    downloads = get_downloads_dir()
    assert isinstance(desktop, Path)
    assert isinstance(downloads, Path)
    assert desktop.exists()
    assert downloads.exists()


def test_save_and_load_config_roundtrip(tmp_path: Path) -> None:
    custom_path = tmp_path / "saved_config.json"
    cfg = AppConfig(
        watch_directory=tmp_path / "my_watch",
        default_category="Unsorted",
        ignored_extensions=[".temp", ".crdownload"],
        stability=StabilityConfig(
            check_interval_seconds=0.5,
            stable_checks=3,
            max_retries=7,
        ),
        categories={
            "PDFs": [".pdf"],
            "Images": [".jpg", ".png"],
        },
    )

    saved = save_config(cfg, custom_path)
    assert saved.exists()

    loaded = load_config(custom_path)
    assert loaded.watch_directory == tmp_path / "my_watch"
    assert loaded.default_category == "Unsorted"
    assert loaded.is_ignored_extension(".temp")
    assert loaded.stability.check_interval_seconds == 0.5
    assert loaded.stability.stable_checks == 3
    assert loaded.categories["PDFs"] == [".pdf"]


def test_batch_organize_directory(tmp_path: Path) -> None:
    watch_dir = tmp_path / "batch_watch"
    watch_dir.mkdir()

    cfg = AppConfig(
        watch_directory=watch_dir,
        stability=StabilityConfig(check_interval_seconds=0.01, stable_checks=1, max_retries=2),
        categories={
            "Documents": [".docx", ".pdf"],
            "Pictures": [".png"],
        },
    )
    organizer = FileOrganizer(config=cfg)

    # Create loose files
    f1 = watch_dir / "doc1.pdf"
    f1.write_text("sample pdf", encoding="utf-8")
    f2 = watch_dir / "pic1.png"
    f2.write_text("sample png", encoding="utf-8")
    f3 = watch_dir / "temp.crdownload"
    f3.write_text("downloading", encoding="utf-8")

    # Create subfolder with file (should be untouched)
    sub = watch_dir / "ExistingSub"
    sub.mkdir()
    sub_file = sub / "nested.pdf"
    sub_file.write_text("nested", encoding="utf-8")

    progress_records = []

    def on_progress(curr: int, total: int, fname: str) -> None:
        progress_records.append((curr, total, fname))

    moved = organizer.organize_directory(watch_dir, progress_callback=on_progress)

    # 2 files moved (doc1.pdf and pic1.png). temp.crdownload ignored, subfolder untouched.
    assert len(moved) == 2
    assert (watch_dir / "Documents" / "doc1.pdf").exists()
    assert (watch_dir / "Pictures" / "pic1.png").exists()
    assert (watch_dir / "temp.crdownload").exists()
    assert sub_file.exists()
    assert len(progress_records) >= 3


def test_tkinter_log_handler() -> None:
    log_q = queue.Queue()
    handler = TkinterLogHandler(log_q)
    logger = logging.getLogger("test_q_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test log message")
    assert not log_q.empty()
    levelno, msg = log_q.get_nowait()
    assert levelno == logging.INFO
    assert "Test log message" in msg


def test_gui_initialization_headless(tmp_path: Path) -> None:
    """Test GUI instantiation and initial state without opening window."""
    cfg_file = tmp_path / "test_gui_config.json"
    save_config(AppConfig(watch_directory=tmp_path), cfg_file)

    root = tk.Tk()
    root.withdraw()  # Hide window for test
    try:
        app = FileOrganizerGUI(root, config_path=cfg_file)
        assert app.is_watching is False
        assert app.dir_var.get() == str(tmp_path)
        assert len(app.config.categories) > 0

        # Test preset switching
        app._select_desktop()
        assert str(get_desktop_dir()) in app.dir_var.get()

        app._select_downloads()
        assert str(get_downloads_dir()) in app.dir_var.get()
    finally:
        root.destroy()
