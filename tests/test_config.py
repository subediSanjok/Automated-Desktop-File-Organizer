"""Unit tests for configuration loading and validation."""

import json
from pathlib import Path
from src.config import AppConfig, load_config


def test_default_config() -> None:
    config = AppConfig()
    assert config.watch_directory == Path(r"C:\FileOrganizerTest")
    assert config.default_category == "Others"
    assert ".crdownload" in config.ignored_extensions
    assert ".pdf" in config.categories["Documents"]
    assert config.get_category_for_extension(".pdf") == "Documents"
    assert config.get_category_for_extension(".xyz") == "Others"


def test_category_case_insensitivity() -> None:
    config = AppConfig()
    assert config.get_category_for_extension(".PDF") == "Documents"
    assert config.get_category_for_extension("pdf") == "Documents"
    assert config.get_category_for_extension(".JpEg") == "Images"
    assert config.get_category_for_extension(".MP4") == "Videos"
    assert config.get_category_for_extension(".MP3") == "Music"
    assert config.get_category_for_extension(".ZIP") == "Archives"
    assert config.get_category_for_extension(".EXE") == "Applications"
    assert config.get_category_for_extension(".PY") == "Code"
    assert config.get_category_for_extension(".UNKNOWN") == "Others"
    assert config.get_category_for_extension("") == "Others"


def test_ignored_extensions() -> None:
    config = AppConfig()
    assert config.is_ignored_extension(".crdownload") is True
    assert config.is_ignored_extension("CRDOWNLOAD") is True
    assert config.is_ignored_extension(".part") is True
    assert config.is_ignored_extension(".tmp") is True
    assert config.is_ignored_extension(".pdf") is False
    assert config.is_ignored_extension("") is False


def test_load_config_from_custom_file(tmp_path: Path) -> None:
    custom_config_path = tmp_path / "custom_config.json"
    data = {
        "watch_directory": str(tmp_path / "watch"),
        "default_category": "Misc",
        "ignored_extensions": [".customtmp"],
        "stability": {
            "check_interval_seconds": 0.1,
            "stable_checks": 1,
            "max_retries": 3,
        },
        "categories": {
            "Docs": [".pdf"],
            "Pics": [".png"],
        },
    }
    with open(custom_config_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    loaded = load_config(custom_config_path)
    assert loaded.watch_directory == tmp_path / "watch"
    assert loaded.default_category == "Misc"
    assert loaded.is_ignored_extension(".customtmp") is True
    assert loaded.stability.check_interval_seconds == 0.1
    assert loaded.get_category_for_extension(".pdf") == "Docs"
    assert loaded.get_category_for_extension(".png") == "Pics"
    assert loaded.get_category_for_extension(".unknown") == "Misc"


def test_load_config_nonexistent_returns_defaults() -> None:
    loaded = load_config(Path("nonexistent_path_to_config_file.json"))
    assert isinstance(loaded, AppConfig)
    assert loaded.watch_directory == Path(r"C:\FileOrganizerTest")
