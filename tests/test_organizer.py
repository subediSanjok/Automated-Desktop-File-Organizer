"""Integration and unit tests for FileOrganizer and FileWatcher."""

import time
from pathlib import Path
import pytest

from src.config import AppConfig, StabilityConfig
from src.logger import setup_logger
from src.organizer import FileOrganizer
from src.watcher import FileWatcher


@pytest.fixture
def test_env(tmp_path: Path):
    """Creates an isolated test environment with custom AppConfig and Organizer."""
    watch_dir = tmp_path / "watch_test"
    watch_dir.mkdir()

    config = AppConfig(
        watch_directory=watch_dir,
        default_category="Others",
        ignored_extensions=[".crdownload", ".part", ".tmp"],
        stability=StabilityConfig(
            check_interval_seconds=0.01,
            stable_checks=1,
            max_retries=3,
        ),
        categories={
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
            "Spreadsheets": [".xls", ".xlsx", ".csv"],
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"],
            "Videos": [".mp4", ".mkv", ".avi", ".mov", ".webm"],
            "Music": [".mp3", ".wav", ".flac", ".aac"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Applications": [".exe", ".msi"],
            "Code": [".py", ".js", ".html", ".css", ".json"],
        },
    )

    logger = setup_logger(name="test_logger", log_file=tmp_path / "test.log")
    organizer = FileOrganizer(config=config, logger=logger)
    return watch_dir, config, organizer, logger


def test_organize_all_categories(test_env) -> None:
    watch_dir, _, organizer, _ = test_env

    sample_files = {
        "report.pdf": "Documents",
        "data.csv": "Spreadsheets",
        "photo.JPG": "Images",
        "clip.mp4": "Videos",
        "song.mp3": "Music",
        "backup.zip": "Archives",
        "installer.exe": "Applications",
        "script.py": "Code",
        "unknown_file.xyz": "Others",
    }

    for filename, expected_category in sample_files.items():
        file_path = watch_dir / filename
        file_path.write_text("test content", encoding="utf-8")

        result = organizer.organize_file(file_path)
        assert result is not None
        assert result.exists()
        assert result.parent == watch_dir / expected_category
        assert result.name.lower() == filename.lower()
        assert not file_path.exists()


def test_ignore_temporary_download_files(test_env) -> None:
    watch_dir, _, organizer, _ = test_env

    temp_files = ["download.crdownload", "video.part", "session.tmp"]
    for temp_name in temp_files:
        temp_path = watch_dir / temp_name
        temp_path.write_text("downloading...", encoding="utf-8")

        result = organizer.organize_file(temp_path)
        assert result is None
        # File should NOT be moved
        assert temp_path.exists()


def test_ignore_directories(test_env) -> None:
    watch_dir, _, organizer, _ = test_env

    subfolder = watch_dir / "SubFolder"
    subfolder.mkdir()

    result = organizer.organize_file(subfolder)
    assert result is None
    assert subfolder.exists()


def test_ignore_files_inside_subcategories(test_env) -> None:
    watch_dir, _, organizer, _ = test_env

    doc_dir = watch_dir / "Documents"
    doc_dir.mkdir()
    nested_file = doc_dir / "nested_doc.pdf"
    nested_file.write_text("content", encoding="utf-8")

    # File is in a subdirectory, organizer should ignore it to prevent loops
    result = organizer.organize_file(nested_file)
    assert result is None
    assert nested_file.exists()


def test_duplicate_file_handling(test_env) -> None:
    watch_dir, _, organizer, _ = test_env

    # 1. First file
    f1 = watch_dir / "statement.pdf"
    f1.write_text("first version", encoding="utf-8")
    res1 = organizer.organize_file(f1)
    assert res1 == watch_dir / "Documents" / "statement.pdf"
    assert res1.read_text(encoding="utf-8") == "first version"

    # 2. Duplicate file with exact same name
    f2 = watch_dir / "statement.pdf"
    f2.write_text("second version", encoding="utf-8")
    res2 = organizer.organize_file(f2)
    assert res2 == watch_dir / "Documents" / "statement_1.pdf"
    assert res2.read_text(encoding="utf-8") == "second version"

    # 3. Third duplicate
    f3 = watch_dir / "statement.pdf"
    f3.write_text("third version", encoding="utf-8")
    res3 = organizer.organize_file(f3)
    assert res3 == watch_dir / "Documents" / "statement_2.pdf"
    assert res3.read_text(encoding="utf-8") == "third version"

    # Verify first file is preserved intact
    assert res1.read_text(encoding="utf-8") == "first version"


def test_missing_file_handled_gracefully(test_env) -> None:
    watch_dir, _, organizer, _ = test_env
    ghost = watch_dir / "ghost.pdf"
    # Do not create file on disk
    result = organizer.organize_file(ghost)
    assert result is None


def test_realtime_watchdog_watcher_integration(test_env) -> None:
    """Test full real-time watchdog file detection and moving in background."""
    watch_dir, config, organizer, logger = test_env

    watcher = FileWatcher(config=config, organizer=organizer, logger=logger)
    watcher.start()

    try:
        # Create files inside monitored directory
        f1 = watch_dir / "live_doc.docx"
        f1.write_text("live doc content", encoding="utf-8")

        f2 = watch_dir / "live_image.png"
        f2.write_text("live png content", encoding="utf-8")

        # Give background watcher worker time to detect and process
        timeout = 5.0
        start = time.time()
        expected_dest1 = watch_dir / "Documents" / "live_doc.docx"
        expected_dest2 = watch_dir / "Images" / "live_image.png"

        while time.time() - start < timeout:
            if expected_dest1.exists() and expected_dest2.exists():
                break
            time.sleep(0.2)

        assert expected_dest1.exists(), "live_doc.docx was not moved to Documents"
        assert expected_dest2.exists(), "live_image.png was not moved to Images"
        assert not f1.exists()
        assert not f2.exists()
    finally:
        watcher.stop()
