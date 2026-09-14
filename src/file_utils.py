"""File utility functions for Automated Desktop File Organizer."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable, Optional


def normalize_extension(file_path: Path | str) -> str:
    """Extract and normalize a file's extension to lowercase with leading dot.

    Args:
        file_path: Path or filename string.

    Returns:
        Normalized extension, e.g. '.pdf', or empty string '' if none.
    """
    path = Path(file_path)
    suffix = path.suffix
    return suffix.lower() if suffix else ""


def get_unique_destination(target_dir: Path | str, filename: str) -> Path:
    """Generate a non-colliding destination path by appending _1, _2, etc.

    Never overwrites an existing file.
    Examples:
        report.pdf -> report.pdf (if not exists)
        report.pdf -> report_1.pdf (if report.pdf exists)
        report.pdf -> report_2.pdf (if report.pdf & report_1.pdf exist)

    Args:
        target_dir: Destination directory.
        filename: Original file name.

    Returns:
        A unique destination Path that does not currently exist.
    """
    dest_dir = Path(target_dir)
    original_path = Path(filename)
    stem = original_path.stem
    suffix = original_path.suffix

    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_directory_exists(directory: Path | str) -> Path:
    """Ensure that the given directory exists, creating parents if necessary.

    Args:
        directory: Directory path to create.

    Returns:
        Path object of the directory.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_file_stable(
    file_path: Path | str,
    check_interval_seconds: float=1.0,
    stable_checks: int=2,
    max_retries: int=5,
    sleep_fn: Callable[[float], None]=time.sleep,
) -> bool:
    """Check if a file's size is stable and no longer actively written/downloaded.

    Args:
        file_path: Path to the target file.
        check_interval_seconds: Interval in seconds between size checks.
        stable_checks: Number of consecutive identical size checks required.
        max_retries: Maximum number of retry attempts before giving up.
        sleep_fn: Sleep function (injectable for unit testing).

    Returns:
        True if file is stable and ready to move, False if unstable or missing.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return False

    last_size: Optional[int] = None
    consecutive_stable_count = 0
    attempts = 0

    while attempts < max_retries:
        try:
            if not path.exists():
                return False
            current_size = path.stat().st_size
        except (OSError, FileNotFoundError):
            return False

        if last_size is not None and current_size == last_size:
            consecutive_stable_count += 1
            if consecutive_stable_count >= stable_checks:
                return True
        else:
            consecutive_stable_count = 0

        last_size = current_size
        attempts += 1

        if attempts < max_retries:
            sleep_fn(check_interval_seconds)

    return False


def safe_move_file(source: Path | str, destination: Path | str) -> Path:
    """Safely move a file from source to destination without data loss or overwriting.

    Validates that:
    - Source exists and is a file.
    - Source and destination are different files.
    - Destination does not already exist.
    - Destination directory exists or is created.

    Args:
        source: Source file path.
        destination: Destination file path.

    Returns:
        Path to the moved file at destination.

    Raises:
        FileNotFoundError: If source does not exist.
        IsADirectoryError: If source is a directory.
        FileExistsError: If destination already exists.
        ValueError: If source and destination are the same path.
        OSError: For other I/O errors.
    """
    src = Path(source).resolve()
    dest = Path(destination).resolve()

    if not src.exists():
        raise FileNotFoundError(f"Source file does not exist: {src}")

    if not src.is_file():
        raise IsADirectoryError(f"Source is a directory, not a file: {src}")

    if src == dest:
        raise ValueError(f"Source and destination are the same path: {src}")

    if dest.exists():
        raise FileExistsError(f"Destination file already exists: {dest}")

    ensure_directory_exists(dest.parent)
    shutil.move(str(src), str(dest))
    return dest
