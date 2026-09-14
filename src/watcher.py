"""Watchdog event monitoring and threaded worker dispatch for Automated Desktop File Organizer."""

from __future__ import annotations

import logging
import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Set

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from src.config import AppConfig
from src.file_utils import ensure_directory_exists
from src.organizer import FileOrganizer


class FileOrganizerEventHandler(FileSystemEventHandler):
    """Handles filesystem events and enqueues newly available files."""

    def __init__(
        self,
        event_queue: queue.Queue[Path],
        logger: logging.Logger,
    ) -> None:
        super().__init__()
        self.event_queue = event_queue
        self.logger = logger

    def on_created(self, event: FileSystemEvent) -> None:
        """Triggered when a file or directory is created."""
        if event.is_directory:
            return
        path = Path(os.fsdecode(event.src_path))
        self.event_queue.put(path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Triggered when a file is renamed/moved (e.g. download completed)."""
        if event.is_directory:
            return
        # In Watchdog, dest_path is the new file path after rename
        dest_path = getattr(event, "dest_path", None)
        if dest_path:
            path = Path(os.fsdecode(dest_path))
            self.event_queue.put(path)


class FileWatcher:
    """Manages directory observer lifecycle and background event processing worker pool."""

    def __init__(
        self,
        config: AppConfig,
        organizer: FileOrganizer,
        logger: Optional[logging.Logger] = None,
        max_workers: int = 4,
    ) -> None:
        self.config = config
        self.organizer = organizer
        self.logger = logger or organizer.logger
        self.max_workers = max_workers
        self.event_queue: queue.Queue[Path] = queue.Queue()
        self.observer: Optional[BaseObserver] = None
        self.executor: Optional[ThreadPoolExecutor] = None
        self.dispatcher_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._in_flight: Set[Path] = set()
        self._lock = threading.Lock()

    def _process_file(self, file_path: Path) -> None:
        """Worker task processing a single file."""
        try:
            self.organizer.organize_file(file_path)
        except Exception as e:
            self.logger.error(f"Unexpected error processing {file_path}: {e}")
        finally:
            with self._lock:
                self._in_flight.discard(file_path.resolve())
            self.event_queue.task_done()

    def _dispatcher_loop(self) -> None:
        """Dispatcher thread distributing queue items to thread pool workers."""
        while not self._stop_event.is_set():
            try:
                file_path = self.event_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                resolved = file_path.resolve()
            except Exception:
                resolved = file_path

            with self._lock:
                if resolved in self._in_flight:
                    self.event_queue.task_done()
                    continue
                self._in_flight.add(resolved)

            if self.executor and not self._stop_event.is_set():
                self.executor.submit(self._process_file, file_path)

    def start(self) -> None:
        """Start the directory watcher and background worker pool."""
        watch_path = ensure_directory_exists(self.config.watch_directory)

        self._stop_event.clear()
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="FileOrganizerWorker",
        )
        self.dispatcher_thread = threading.Thread(
            target=self._dispatcher_loop,
            name="FileOrganizerDispatcher",
            daemon=True,
        )
        self.dispatcher_thread.start()

        # Start watchdog observer
        event_handler = FileOrganizerEventHandler(self.event_queue, self.logger)
        observer: BaseObserver = Observer()
        # recursive=False ensures subcategory folders do not trigger recursive events
        observer.schedule(event_handler, str(watch_path), recursive=False)
        observer.start()
        self.observer = observer

        self.logger.info(f"Organizer started. Monitoring: {watch_path.resolve()}")

    def stop(self) -> None:
        """Gracefully stop the observer and wait for tasks to finish."""
        self.logger.info("Stopping organizer...")

        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5)

        self._stop_event.set()
        if self.dispatcher_thread and self.dispatcher_thread.is_alive():
            self.dispatcher_thread.join(timeout=2)

        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=False)

        self.logger.info("Organizer stopped cleanly.")
