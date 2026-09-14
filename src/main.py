"""Application entry point for Automated Desktop File Organizer."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any

from src.config import load_config
from src.gui import launch_gui
from src.logger import setup_logger
from src.organizer import FileOrganizer
from src.watcher import FileWatcher


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated Desktop File Organizer: Continuously monitors and organizes files by extension."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.json",
        help="Path to the JSON configuration file (default: config.json)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Graphical User Interface (GUI)",
    )
    return parser.parse_args()


def main() -> int:
    """Main execution function."""
    args = parse_args()

    # If --gui requested, launch graphical interface
    if args.gui:
        launch_gui(config_path=args.config)
        return 0

    # Load configuration
    config_path = Path(args.config)
    config = load_config(config_path)

    # Initialize logger
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("   AUTOMATED DESKTOP FILE ORGANIZER")
    logger.info("=" * 60)
    logger.info(f"Loaded configuration from: {config_path.resolve()}")
    logger.info(f"Target Watch Directory:   {config.watch_directory.resolve()}")
    logger.info(f"Default Category:         {config.default_category}")
    logger.info(f"Configured Categories:    {len(config.categories)}")
    logger.info("=" * 60)

    # Instantiate organizer and watcher
    organizer = FileOrganizer(config=config, logger=logger)
    watcher = FileWatcher(config=config, organizer=organizer, logger=logger)

    # Signal handling for clean exit
    shutdown_requested = False

    def handle_shutdown(_signum: int, _frame: Any) -> None:
        nonlocal shutdown_requested
        if not shutdown_requested:
            shutdown_requested = True
            logger.info("Shutdown signal received (Ctrl+C / SIGTERM). Exiting...")
            watcher.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # Start watcher
    try:
        watcher.start()
        while not shutdown_requested:
            time.sleep(0.5)
    except KeyboardInterrupt:
        handle_shutdown(signal.SIGINT, None)
    except Exception as e:
        logger.critical(f"Fatal unexpected error: {e}", exc_info=True)
        watcher.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
