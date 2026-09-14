"""Unit tests for MoveHistoryManager, revert_batch, and revert_directory."""

from pathlib import Path
from src.config import AppConfig, StabilityConfig
from src.history import MoveHistoryManager
from src.organizer import FileOrganizer


def test_move_history_manager_persistence(tmp_path: Path) -> None:
    hist_file = tmp_path / "test_history.json"
    mgr = MoveHistoryManager(history_file=hist_file)

    rec = mgr.add_record(
        source_path=tmp_path / "file.pdf",
        dest_path=tmp_path / "Documents" / "file.pdf",
        category="Documents",
        batch_id="b1",
    )

    assert rec.batch_id == "b1"
    assert not rec.reverted
    assert hist_file.exists()

    # Load in a new manager
    mgr2 = MoveHistoryManager(history_file=hist_file)
    assert len(mgr2.records) == 1
    assert mgr2.records[0].dest_path == str(tmp_path / "Documents" / "file.pdf")
    assert mgr2.get_batches() == ["b1"]


def test_revert_batch_restores_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch_revert"
    watch_dir.mkdir()

    cfg = AppConfig(
        watch_directory=watch_dir,
        stability=StabilityConfig(check_interval_seconds=0.01, stable_checks=1, max_retries=2),
        categories={"Docs": [".pdf"], "Images": [".png"]},
    )
    hist_file = tmp_path / "history.json"
    hist_mgr = MoveHistoryManager(history_file=hist_file)
    organizer = FileOrganizer(config=cfg, history_manager=hist_mgr)

    # 1. Create and organize files
    f1 = watch_dir / "doc.pdf"
    f1.write_text("doc content", encoding="utf-8")
    f2 = watch_dir / "pic.png"
    f2.write_text("pic content", encoding="utf-8")

    moved = organizer.organize_directory(watch_dir)
    assert len(moved) == 2
    assert (watch_dir / "Docs" / "doc.pdf").exists()
    assert (watch_dir / "Images" / "pic.png").exists()
    assert not f1.exists()
    assert not f2.exists()

    # 2. Revert the batch
    batches = hist_mgr.get_batches()
    assert len(batches) == 1
    batch_id = batches[0]

    restored = organizer.revert_batch(batch_id)
    assert len(restored) == 2
    assert f1.exists()
    assert f2.exists()
    assert f1.read_text(encoding="utf-8") == "doc content"
    assert f2.read_text(encoding="utf-8") == "pic content"
    assert not (watch_dir / "Docs" / "doc.pdf").exists()
    assert not (watch_dir / "Images" / "pic.png").exists()


def test_revert_directory_full_sweep(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch_full_revert"
    watch_dir.mkdir()

    cfg = AppConfig(
        watch_directory=watch_dir,
        categories={"Documents": [".pdf"], "Images": [".png"]},
    )
    organizer = FileOrganizer(config=cfg)

    # Populate category folders manually
    doc_dir = watch_dir / "Documents"
    doc_dir.mkdir()
    doc_file = doc_dir / "manual_doc.pdf"
    doc_file.write_text("sample doc", encoding="utf-8")

    img_dir = watch_dir / "Images"
    img_dir.mkdir()
    img_file = img_dir / "manual_img.png"
    img_file.write_text("sample img", encoding="utf-8")

    restored = organizer.revert_directory(watch_dir)
    assert len(restored) == 2
    assert (watch_dir / "manual_doc.pdf").exists()
    assert (watch_dir / "manual_img.png").exists()

    # Verify empty folders were cleaned up
    assert not doc_dir.exists()
    assert not img_dir.exists()


def test_revert_with_existing_name_collision(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch_collision"
    watch_dir.mkdir()

    cfg = AppConfig(
        watch_directory=watch_dir,
        categories={"Documents": [".pdf"]},
    )
    organizer = FileOrganizer(config=cfg)

    # In subfolder
    doc_dir = watch_dir / "Documents"
    doc_dir.mkdir()
    sub_file = doc_dir / "report.pdf"
    sub_file.write_text("subfolder version", encoding="utf-8")

    # In root directory, a new file named report.pdf already exists!
    root_file = watch_dir / "report.pdf"
    root_file.write_text("root existing version", encoding="utf-8")

    restored = organizer.revert_directory(watch_dir)
    assert len(restored) == 1
    # Should not overwrite root_file; should rename to report_1.pdf
    assert root_file.read_text(encoding="utf-8") == "root existing version"
    assert (watch_dir / "report_1.pdf").exists()
    assert (watch_dir / "report_1.pdf").read_text(encoding="utf-8") == "subfolder version"
