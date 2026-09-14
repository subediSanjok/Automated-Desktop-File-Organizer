"""Live verification script running directly against C:\\FileOrganizerTest."""

import os
import shutil
import sys
import time
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.logger import setup_logger
from src.organizer import FileOrganizer
from src.watcher import FileWatcher


def run_live_verification() -> bool:
    test_dir = Path(r"C:\FileOrganizerTest")
    
    # 1. Clean / setup test directory
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/8] Prepared fresh test directory: {test_dir}")

    # 2. Load config and initialize organizer
    config = load_config("config.json")
    config.watch_directory = test_dir
    config.stability.check_interval_seconds = 0.3
    config.stability.stable_checks = 2
    config.stability.max_retries = 8

    log_file = Path("logs") / "organizer.log"
    logger = setup_logger(log_file=log_file)
    organizer = FileOrganizer(config=config, logger=logger)
    watcher = FileWatcher(config=config, organizer=organizer, logger=logger, max_workers=4)

    print("[2/8] Starting live FileWatcher on C:\\FileOrganizerTest...")
    watcher.start()
    time.sleep(1.0)

    try:
        # 3. Create sample category files
        print("[3/8] Creating test files for all categories...")
        files_to_create = {
            "test.pdf": "Documents",
            "finances.xlsx": "Spreadsheets",
            "photo.jpg": "Images",
            "video.mp4": "Videos",
            "track.mp3": "Music",
            "archive.zip": "Archives",
            "setup.exe": "Applications",
            "main.py": "Code",
            "unknown.xyz": "Others",
        }

        for filename in files_to_create:
            p = test_dir / filename
            p.write_text(f"Dummy content for {filename}", encoding="utf-8")

        # Wait for watchdog and worker pool to detect and organize
        timeout = 10.0
        start = time.time()
        while time.time() - start < timeout:
            all_moved = all((test_dir / cat / fn).exists() for fn, cat in files_to_create.items())
            if all_moved:
                break
            time.sleep(0.5)

        for filename, category in files_to_create.items():
            dest = test_dir / category / filename
            assert dest.exists(), f"Expected {dest} to exist!"
            assert not (test_dir / filename).exists(), f"Source {filename} should be moved!"
            print(f"  [OK] {filename} -> {category}/{filename}")

        # 4. Test duplicate handling
        print("[4/8] Testing duplicate file handling...")
        dup1 = test_dir / "test.pdf"
        dup1.write_text("Second PDF content", encoding="utf-8")
        
        timeout = 5.0
        start = time.time()
        dup_dest1 = test_dir / "Documents" / "test_1.pdf"
        while time.time() - start < timeout:
            if dup_dest1.exists():
                break
            time.sleep(0.3)

        assert dup_dest1.exists(), f"Expected {dup_dest1} to exist!"
        assert dup_dest1.read_text(encoding="utf-8") == "Second PDF content"
        print("  [OK] Duplicate resolved: test.pdf -> Documents/test_1.pdf")

        dup2 = test_dir / "test.pdf"
        dup2.write_text("Third PDF content", encoding="utf-8")
        
        start = time.time()
        dup_dest2 = test_dir / "Documents" / "test_2.pdf"
        while time.time() - start < timeout:
            if dup_dest2.exists():
                break
            time.sleep(0.3)

        assert dup_dest2.exists(), f"Expected {dup_dest2} to exist!"
        assert dup_dest2.read_text(encoding="utf-8") == "Third PDF content"
        print("  [OK] Duplicate resolved: test.pdf -> Documents/test_2.pdf")

        # 5. Test temporary download files (must be ignored)
        print("[5/8] Testing temporary download files (.crdownload, .part, .tmp)...")
        temp_files = ["bigdownload.crdownload", "video_stream.part", "cache_session.tmp"]
        for tf in temp_files:
            (test_dir / tf).write_text("temporary data", encoding="utf-8")
        time.sleep(1.5)

        for tf in temp_files:
            p = test_dir / tf
            assert p.exists(), f"Temporary file {tf} should remain untouched in root!"
            print(f"  [OK] Temporary file ignored: {tf}")

        # 6. Test directory ignore
        print("[6/8] Testing directory ignore...")
        sub_folder = test_dir / "CustomUserFolder"
        sub_folder.mkdir()
        time.sleep(1.0)
        assert sub_folder.exists(), "Directory should not be moved or deleted!"
        print(f"  [OK] Subdirectory untouched: {sub_folder.name}")

        # 7. Test active download simulation (stability check)
        print("[7/8] Testing active file writing (download stability)...")
        active_file = test_dir / "large_document.docx"
        with open(active_file, "wb") as f:
            f.write(b"Initial chunk...")
            f.flush()

        # Simulate ongoing writes
        for i in range(3):
            time.sleep(0.2)
            with open(active_file, "ab") as f:
                f.write(f"\nChunk {i}".encode("utf-8"))
                f.flush()

        # Now wait for stability to kick in and organize
        timeout = 8.0
        start = time.time()
        active_dest = test_dir / "Documents" / "large_document.docx"
        while time.time() - start < timeout:
            if active_dest.exists():
                break
            time.sleep(0.3)

        assert active_dest.exists(), f"Expected {active_dest} to exist after stabilizing!"
        print("  [OK] Active writing finished and stabilized: large_document.docx -> Documents/large_document.docx")

        # 8. Check log file
        print("[8/8] Verifying logs in logs/organizer.log...")
        assert log_file.exists(), "Log file was not generated!"
        log_content = log_file.read_text(encoding="utf-8")
        assert "Organizer started" in log_content
        assert "Category resolved: Documents" in log_content
        assert "Duplicate detected. New filename: test_1.pdf" in log_content
        print("  [OK] Log file verification passed!")

        print("\n" + "=" * 60)
        print("ALL LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
        print("=" * 60)
        return True

    finally:
        watcher.stop()
        # Clean up test directory
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
            print("Cleaned up C:\\FileOrganizerTest.")


if __name__ == "__main__":
    success = run_live_verification()
    sys.exit(0 if success else 1)
