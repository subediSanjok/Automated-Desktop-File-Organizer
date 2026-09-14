"""Configuration loader and validator for Automated Desktop File Organizer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class StabilityConfig:
    """Settings for download completion and file write stability."""
    check_interval_seconds: float = 1.0
    stable_checks: int = 2
    max_retries: int = 5


@dataclass
class AppConfig:
    """Full application configuration schema."""
    watch_directory: Path = field(default_factory=lambda: Path(r"C:\FileOrganizerTest"))
    default_category: str = "Others"
    ignored_extensions: List[str] = field(
        default_factory=lambda: [".crdownload", ".part", ".tmp"]
    )
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    categories: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
            "Spreadsheets": [".xls", ".xlsx", ".csv"],
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"],
            "Videos": [".mp4", ".mkv", ".avi", ".mov", ".webm"],
            "Music": [".mp3", ".wav", ".flac", ".aac"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Applications": [".exe", ".msi"],
            "Code": [
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".java",
                ".html",
                ".css",
                ".json",
            ],
        }
    )

    # Inverted map for O(1) extension -> category lookups
    _ext_to_category: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.watch_directory = Path(self.watch_directory)
        self.ignored_extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in self.ignored_extensions
        ]
        self._rebuild_lookup_cache()

    def _rebuild_lookup_cache(self) -> None:
        """Rebuild normalized lowercase extension lookup dictionary."""
        self._ext_to_category = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                norm_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
                self._ext_to_category[norm_ext] = category

    def get_category_for_extension(self, ext: str) -> str:
        """Resolve the category name for a given extension.

        Args:
            ext: File extension (with or without leading dot, any casing).

        Returns:
            Resolved category name, or default_category if unmatched.
        """
        if not ext:
            return self.default_category
        norm_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        return self._ext_to_category.get(norm_ext, self.default_category)

    def is_ignored_extension(self, ext: str) -> bool:
        """Check if an extension belongs to ignored/temporary file types.

        Args:
            ext: File extension.

        Returns:
            True if ignored, False otherwise.
        """
        if not ext:
            return False
        norm_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        return norm_ext in self.ignored_extensions


def load_config(config_path: Optional[Path | str] = None) -> AppConfig:
    """Load and parse application configuration from a JSON file.

    Args:
        config_path: Path to config.json. Defaults to config.json in root.

    Returns:
        AppConfig populated instance.
    """
    if config_path is None:
        config_path = Path("config.json")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return AppConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)

        stability_data = data.get("stability", {})
        stability = StabilityConfig(
            check_interval_seconds=float(
                stability_data.get("check_interval_seconds", 1.0)
            ),
            stable_checks=int(stability_data.get("stable_checks", 2)),
            max_retries=int(stability_data.get("max_retries", 5)),
        )

        return AppConfig(
            watch_directory=Path(data.get("watch_directory", r"C:\FileOrganizerTest")),
            default_category=str(data.get("default_category", "Others")),
            ignored_extensions=list(
                data.get("ignored_extensions", [".crdownload", ".part", ".tmp"])
            ),
            stability=stability,
            categories=dict(data.get("categories", {})),
        )
    except Exception as e:
        # Fallback to safe defaults if corrupt
        print(f"Warning: Failed to parse config from {config_path} ({e}). Using defaults.")
        return AppConfig()


def save_config(config: AppConfig, config_path: Optional[Path | str] = None) -> Path:
    """Save application configuration to a JSON file.

    Args:
        config: AppConfig instance to serialize.
        config_path: Destination path. Defaults to `config.json`.

    Returns:
        Path to the saved configuration file.
    """
    if config_path is None:
        config_path = Path("config.json")
    else:
        config_path = Path(config_path)

    data = {
        "watch_directory": str(config.watch_directory),
        "default_category": config.default_category,
        "ignored_extensions": config.ignored_extensions,
        "stability": {
            "check_interval_seconds": config.stability.check_interval_seconds,
            "stable_checks": config.stability.stable_checks,
            "max_retries": config.stability.max_retries,
        },
        "categories": config.categories,
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return config_path


def get_desktop_dir() -> Path:
    """Get the standard Windows Desktop directory for the current user."""
    desktop = Path.home() / "Desktop"
    return desktop if desktop.exists() else Path.home()


def get_downloads_dir() -> Path:
    """Get the standard Windows Downloads directory for the current user."""
    downloads = Path.home() / "Downloads"
    return downloads if downloads.exists() else Path.home()

