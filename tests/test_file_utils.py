"""Unit tests for file utilities (normalization, unique naming, stability, safe move)."""

from pathlib import Path
import pytest
from src.file_utils import (
    ensure_directory_exists,
    get_unique_destination,
    is_file_stable,
    normalize_extension,
    safe_move_file,
)


def test_normalize_extension() -> None:
    assert normalize_extension("report.PDF") == ".pdf"
    assert normalize_extension("image.JPG") == ".jpg"
    assert normalize_extension("video.MP4") == ".mp4"
    assert normalize_extension(Path("folder/archive.tar.gz")) == ".gz"
    assert normalize_extension("no_extension") == ""
    assert normalize_extension(".hidden") == ""


def test_get_unique_destination(tmp_path: Path) -> None:
    dest_dir = tmp_path / "Documents"
    dest_dir.mkdir()

    # 1. Base case: no collision
    dest1 = get_unique_destination(dest_dir, "report.pdf")
    assert dest1 == dest_dir / "report.pdf"

    # Create report.pdf
    (dest_dir / "report.pdf").touch()

    # 2. First duplicate: report_1.pdf
    dest2 = get_unique_destination(dest_dir, "report.pdf")
    assert dest2 == dest_dir / "report_1.pdf"

    # Create report_1.pdf
    (dest_dir / "report_1.pdf").touch()

    # 3. Second duplicate: report_2.pdf
    dest3 = get_unique_destination(dest_dir, "report.pdf")
    assert dest3 == dest_dir / "report_2.pdf"

    # 4. File without extension
    (dest_dir / "data").touch()
    dest_noext = get_unique_destination(dest_dir, "data")
    assert dest_noext == dest_dir / "data_1"


def test_ensure_directory_exists(tmp_path: Path) -> None:
    nested = tmp_path / "level1" / "level2" / "level3"
    assert not nested.exists()
    result = ensure_directory_exists(nested)
    assert result.exists()
    assert result.is_dir()


def test_is_file_stable_static_file(tmp_path: Path) -> None:
    test_file = tmp_path / "static.txt"
    test_file.write_text("hello world", encoding="utf-8")

    # Should be stable immediately with mocked sleeper
    stable = is_file_stable(
        test_file,
        check_interval_seconds=0.01,
        stable_checks=2,
        max_retries=5,
        sleep_fn=lambda _: None,
    )
    assert stable is True


def test_is_file_stable_nonexistent_file(tmp_path: Path) -> None:
    nonexistent = tmp_path / "ghost.txt"
    stable = is_file_stable(
        nonexistent,
        check_interval_seconds=0.01,
        stable_checks=2,
        max_retries=3,
        sleep_fn=lambda _: None,
    )
    assert stable is False


def test_is_file_stable_growing_then_stable(tmp_path: Path) -> None:
    test_file = tmp_path / "growing.bin"
    test_file.write_bytes(b"chunk1")

    write_count = 0

    def mock_sleep(_duration: float) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            # Append more bytes during sleep
            with open(test_file, "ab") as f:
                f.write(b"chunk2")
        # After write_count >= 1, file stops growing

    stable = is_file_stable(
        test_file,
        check_interval_seconds=0.01,
        stable_checks=2,
        max_retries=10,
        sleep_fn=mock_sleep,
    )
    assert stable is True


def test_is_file_stable_never_stabilizes(tmp_path: Path) -> None:
    test_file = tmp_path / "infinite_grow.bin"
    test_file.write_bytes(b"initial")

    def mock_sleep(_duration: float) -> None:
        # Constantly append bytes on every sleep
        with open(test_file, "ab") as f:
            f.write(b"x")

    stable = is_file_stable(
        test_file,
        check_interval_seconds=0.01,
        stable_checks=2,
        max_retries=4,
        sleep_fn=mock_sleep,
    )
    assert stable is False


def test_safe_move_file_success(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_text("test content", encoding="utf-8")
    dest = tmp_path / "target_dir" / "destination.txt"

    result = safe_move_file(src, dest)
    assert not src.exists()
    assert dest.exists()
    assert result == dest.resolve()
    assert dest.read_text(encoding="utf-8") == "test content"


def test_safe_move_file_source_missing(tmp_path: Path) -> None:
    src = tmp_path / "nonexistent.txt"
    dest = tmp_path / "out.txt"
    with pytest.raises(FileNotFoundError):
        safe_move_file(src, dest)


def test_safe_move_file_source_is_directory(tmp_path: Path) -> None:
    src_dir = tmp_path / "some_dir"
    src_dir.mkdir()
    dest = tmp_path / "out_dir"
    with pytest.raises(IsADirectoryError):
        safe_move_file(src_dir, dest)


def test_safe_move_file_destination_exists_raises(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_text("src", encoding="utf-8")
    dest = tmp_path / "dest.txt"
    dest.write_text("already here", encoding="utf-8")

    with pytest.raises(FileExistsError):
        safe_move_file(src, dest)


def test_safe_move_file_same_source_and_destination(tmp_path: Path) -> None:
    src = tmp_path / "same.txt"
    src.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError):
        safe_move_file(src, src)
