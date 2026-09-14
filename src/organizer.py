"""Core FileOrganizer module for categorizing and moving files safely."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from src.config import AppConfig
from src.file_utils import (
    ensure_directory_exists,
    get_unique_destination,
    is_file_stable,
    normalize_extension,
    safe_move_file,
)
from src.history import MoveHistoryManager, MoveRecord
from src.logger import setup_logger


class FileOrganizer:
    """Orchestrates file inspection, category resolution, duplicate handling, and safe moving."""

    def __init__(
        self,
        config: AppConfig,
        logger: Optional[logging.Logger] = None,
        history_manager: Optional[MoveHistoryManager] = None,
    ) -> None:
        self.config = config
        self.logger = logger or setup_logger()
        self.history_manager = history_manager or MoveHistoryManager()
        self.active_batch_id: str = f"batch_{uuid.uuid4().hex[:8]}"

    def organize_file(self, file_path: Path | str) -> Optional[Path]:
        """Process a single file: validate, wait for stability, categorize, and move.

        Args:
            file_path: Path to the target file.

        Returns:
            The final destination Path if moved successfully, None otherwise.
        """
        path = Path(file_path)

        # 1. Existence and type validation
        if not path.exists():
            self.logger.debug(f"File no longer exists: {path.name}")
            return None

        if path.is_dir():
            self.logger.debug(f"Ignoring directory: {path.name}")
            return None

        # 2. Check if file is directly in the monitored directory (and not in a subfolder)
        try:
            monitored_dir = self.config.watch_directory.resolve()
            parent_dir = path.resolve().parent
            if parent_dir != monitored_dir:
                self.logger.debug(
                    f"Skipping file not in root watch directory: {path}"
                )
                return None
        except Exception as e:
            self.logger.debug(f"Path resolution error for {path}: {e}")

        # 3. Check for ignored/temporary extensions
        ext = normalize_extension(path)
        if self.config.is_ignored_extension(ext):
            self.logger.info(f"Ignoring temporary download file: {path.name}")
            return None

        self.logger.info(f"Detected file: {path.name}")

        # 4. Check download/write stability
        is_stable = is_file_stable(
            path,
            check_interval_seconds=self.config.stability.check_interval_seconds,
            stable_checks=self.config.stability.stable_checks,
            max_retries=self.config.stability.max_retries,
        )
        if not is_stable:
            self.logger.warning(
                f"File {path.name} did not stabilize within retry limit. Skipping."
            )
            return None

        # 5. Resolve category
        category = self.config.get_category_for_extension(ext)
        self.logger.info(f"Category resolved: {category}")

        # 6. Target category directory
        target_dir = self.config.watch_directory / category
        ensure_directory_exists(target_dir)

        # 7. Unique destination resolution (duplicate handling)
        dest_path = get_unique_destination(target_dir, path.name)
        if dest_path.name != path.name:
            self.logger.info(
                f"Duplicate detected. New filename: {dest_path.name}"
            )

        # 8. Safe move execution
        try:
            final_path = safe_move_file(path, dest_path)
            self.logger.info(
                f"Moved {path.name} -> {category}/{final_path.name}"
            )
            # Record move for undo/revert support
            self.history_manager.add_record(
                source_path=path,
                dest_path=final_path,
                category=category,
                batch_id=self.active_batch_id,
            )
            return final_path
        except FileNotFoundError:
            self.logger.warning(
                f"Failed to move file: {path.name}. Reason: File was removed before move."
            )
        except PermissionError as e:
            self.logger.error(
                f"Failed to move file: {path.name}. Reason: Permission denied ({e})"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to move file: {path.name}. Reason: {e}"
            )

        return None

    def organize_directory(
        self,
        target_dir: Optional[Path | str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Perform a batch sweep of all loose files in the directory.

        Args:
            target_dir: Directory to organize. Defaults to config.watch_directory.
            progress_callback: Optional callback invoked as (current_index, total_count, filename).

        Returns:
            List of successfully moved destination Paths.
        """
        dir_path = Path(target_dir) if target_dir else self.config.watch_directory
        if not dir_path.exists() or not dir_path.is_dir():
            self.logger.warning(f"Target directory does not exist: {dir_path}")
            return []

        # New batch ID for this sweep
        self.active_batch_id = f"batch_{uuid.uuid4().hex[:8]}"

        # Temporarily update watch_directory for parent checks if custom dir is supplied
        original_watch_dir = self.config.watch_directory
        self.config.watch_directory = dir_path

        moved_files: List[Path] = []
        try:
            # Find all direct files in the target folder (ignoring subdirectories)
            candidates = [p for p in dir_path.iterdir() if p.is_file()]
            total = len(candidates)
            self.logger.info(f"Starting batch organize of {dir_path}: {total} loose files found.")

            for idx, file_path in enumerate(candidates, start=1):
                if progress_callback:
                    progress_callback(idx, total, file_path.name)

                result = self.organize_file(file_path)
                if result:
                    moved_files.append(result)

            self.logger.info(f"Batch organize completed: {len(moved_files)}/{total} files organized.")
        finally:
            self.config.watch_directory = original_watch_dir

        return moved_files

    def revert_move(self, record: MoveRecord) -> Optional[Path]:
        """Revert a single move record back to its source directory.

        Args:
            record: MoveRecord containing source and destination paths.

        Returns:
            Restored path if moved back successfully, None otherwise.
        """
        dest = Path(record.dest_path)
        orig_source = Path(record.source_path)

        if not dest.exists() or not dest.is_file():
            self.logger.warning(f"Cannot revert {dest.name}: File does not exist at destination.")
            return None

        # Determine target directory (the parent of the original source)
        target_dir = orig_source.parent
        ensure_directory_exists(target_dir)

        # Get unique name in target directory to avoid overwriting anything
        restore_dest = get_unique_destination(target_dir, orig_source.name)

        try:
            final_restored = safe_move_file(dest, restore_dest)
            self.logger.info(f"Reverted: {dest.name} -> {final_restored}")
            return final_restored
        except Exception as e:
            self.logger.error(f"Failed to revert {dest.name}: {e}")
            return None

    def revert_batch(
        self,
        batch_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Revert all files from a specific batch (or the most recent batch).

        Args:
            batch_id: Batch ID to revert. If None, uses the most recent active batch.
            progress_callback: Optional callback invoked as (current_index, total_count, filename).

        Returns:
            List of successfully restored Paths.
        """
        if not batch_id:
            batches = self.history_manager.get_batches()
            if not batches:
                self.logger.info("No recorded move batches to revert.")
                return []
            batch_id = batches[0]

        records = self.history_manager.get_records_for_batch(batch_id)
        if not records:
            self.logger.info(f"No active move records found for batch '{batch_id}'.")
            return []

        self.logger.info(f"Reverting batch '{batch_id}' ({len(records)} files)...")
        restored: List[Path] = []
        reverted_records: List[MoveRecord] = []

        total = len(records)
        for idx, rec in enumerate(records, start=1):
            if progress_callback:
                progress_callback(idx, total, Path(rec.dest_path).name)

            res = self.revert_move(rec)
            if res:
                restored.append(res)
                reverted_records.append(rec)

        self.history_manager.mark_reverted(reverted_records)
        self.logger.info(f"Revert completed: {len(restored)}/{total} files restored.")
        return restored

    def revert_directory(
        self,
        target_dir: Optional[Path | str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Sweep all files from category subfolders back to the root directory.

        Also cleans up any empty category subfolders.

        Args:
            target_dir: Monitored folder. Defaults to config.watch_directory.
            progress_callback: Optional callback (current, total, filename).

        Returns:
            List of restored file Paths.
        """
        root_dir = Path(target_dir) if target_dir else self.config.watch_directory
        if not root_dir.exists() or not root_dir.is_dir():
            self.logger.warning(f"Target directory does not exist: {root_dir}")
            return []

        # Find category directories (all configured categories + default_category)
        known_categories = set(self.config.categories.keys())
        known_categories.add(self.config.default_category)

        candidate_files: List[Path] = []
        category_folders: List[Path] = []

        for sub in root_dir.iterdir():
            if sub.is_dir() and sub.name in known_categories:
                category_folders.append(sub)
                for f in sub.iterdir():
                    if f.is_file():
                        candidate_files.append(f)

        total = len(candidate_files)
        self.logger.info(f"Reverting entire directory {root_dir}: {total} files found across category folders.")

        restored: List[Path] = []
        for idx, file_path in enumerate(candidate_files, start=1):
            if progress_callback:
                progress_callback(idx, total, file_path.name)

            restore_dest = get_unique_destination(root_dir, file_path.name)
            try:
                res = safe_move_file(file_path, restore_dest)
                restored.append(res)
                self.logger.info(f"Restored: {file_path.parent.name}/{file_path.name} -> {res.name}")
            except Exception as e:
                self.logger.error(f"Failed to restore {file_path.name}: {e}")

        # Clean up empty category folders
        for cat_dir in category_folders:
            try:
                # Remove if empty
                if not any(cat_dir.iterdir()):
                    cat_dir.rmdir()
                    self.logger.info(f"Removed empty category folder: {cat_dir.name}")
            except Exception as e:
                self.logger.debug(f"Could not remove folder {cat_dir.name}: {e}")

        self.logger.info(f"Directory revert finished: {len(restored)}/{total} files restored.")
        return restored

