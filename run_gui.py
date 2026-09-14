"""Quick launcher for the Automated Desktop & Downloads File Organizer GUI."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.gui import launch_gui

if __name__ == "__main__":
    launch_gui()
