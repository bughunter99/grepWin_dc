from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
import pytest

from core.search_engine import SearchEngine, SearchOptions
from core.search_info import SearchInfo


def _collect_results(engine: SearchEngine, options: SearchOptions) -> list[SearchInfo]:
    found: list[SearchInfo] = []
    engine.search_thread(options=options, on_result=lambda info: found.append(info))
    return found


def test_file_mask_filters_results(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("needle\n", encoding="utf-8")
    (root / "b.txt").write_text("needle\n", encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        file_match="*.py",
        file_match_regex=False,
        include_subfolders=True,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert results[0].file_path.endswith("a.py")


def test_exclude_dirs_regex_skips_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    keep = root / "keep"
    build = root / "build"
    keep.mkdir(parents=True)
    build.mkdir(parents=True)
    (keep / "k.txt").write_text("needle\n", encoding="utf-8")
    (build / "b.txt").write_text("needle\n", encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        exclude_dirs="build",
        include_subfolders=True,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert "keep" in results[0].file_path


def test_binary_inclusion_controls_results(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    payload = b"A\x00B\x00needle\x00C"
    target = root / "bin.dat"
    target.write_bytes(payload)

    engine = SearchEngine()

    without_binary = SearchOptions(
        search_path=str(root),
        search_string="needle",
        include_binary=False,
    )
    with_binary = SearchOptions(
        search_path=str(root),
        search_string="needle",
        include_binary=True,
    )

    results_without = _collect_results(engine, without_binary)
    results_with = _collect_results(engine, with_binary)

    assert results_without == []
    assert len(results_with) == 1
    assert Path(results_with[0].file_path).name == "bin.dat"


def test_size_filter_less_than(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "small.txt").write_text("needle\n", encoding="utf-8")
    (root / "large.txt").write_text("needle\n" + ("x" * 5000), encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        size_enabled=True,
        size_cmp="lt",
        size_value=200,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert results[0].file_path.endswith("small.txt")


def test_date_filter_newer(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    old_file = root / "old.txt"
    new_file = root / "new.txt"
    old_file.write_text("needle\n", encoding="utf-8")
    new_file.write_text("needle\n", encoding="utf-8")

    old_time = datetime.now() - timedelta(days=10)
    os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

    threshold = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        date_limit_mode="newer",
        date1=threshold,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert results[0].file_path.endswith("new.txt")


def test_symlink_filter_excludes_links(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "target.txt"
    link = root / "link.txt"
    target.write_text("needle\n", encoding="utf-8")

    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not available in this environment")

    engine = SearchEngine()
    options_exclude = SearchOptions(
        search_path=str(root),
        search_string="needle",
        include_sym_links=False,
    )
    options_include = SearchOptions(
        search_path=str(root),
        search_string="needle",
        include_sym_links=True,
    )

    results_exclude = _collect_results(engine, options_exclude)
    results_include = _collect_results(engine, options_include)

    assert len(results_exclude) == 1
    assert len(results_include) >= 2


def test_large_file_uses_streaming_search_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "big.txt"

    # Ensure the file is above STREAM_THRESHOLD_BYTES (4MB).
    block = "abcdefghij" * 1000
    content = (block + "\n") * 500
    content += "needle target line\n"
    content += (block + "\n") * 500
    # Repeat to go over threshold.
    target.write_text(content * 2, encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        use_regex=False,
        whole_words=False,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert results[0].match_count >= 1
    assert any("needle" in line for line in results[0].match_lines_map.values())


def test_streaming_whole_words_respected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "big_words.txt"

    # Above threshold with controlled content around word boundaries.
    filler = ("x" * 10000) + "\n"
    text = filler * 450
    text += "token tokenized token\n"
    text += filler * 450
    target.write_text(text, encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="token",
        use_regex=False,
        whole_words=True,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    # whole_words=True should match only the two standalone 'token' occurrences.
    assert results[0].match_count == 2


def test_large_file_streaming_replace_updates_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "big_replace.txt"

    filler = ("abcdefghij" * 1000) + "\n"
    text = filler * 500
    text += "needle here\n"
    text += filler * 500
    target.write_text(text * 2, encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        replace_string="updated",
        use_regex=False,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    assert results[0].match_count >= 1
    updated_text = target.read_text(encoding="utf-8")
    assert "updated here" in updated_text
    assert "needle here" not in updated_text


def test_create_backup_creates_bak_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "sample.txt"
    target.write_text("hello needle world\n", encoding="utf-8")

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        replace_string="pin",
        use_regex=False,
        create_backup=True,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    backup = root / "sample.txt.bak"
    assert backup.exists(), "backup file should be created"
    assert "needle" in backup.read_text(encoding="utf-8")
    assert "pin" in target.read_text(encoding="utf-8")


def test_keep_file_date_preserves_mtime(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "dated.txt"
    target.write_text("old needle old\n", encoding="utf-8")
    # Set mtime to a clearly recognisable past timestamp
    old_mtime = target.stat().st_mtime - 3600
    os.utime(target, (old_mtime, old_mtime))

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        replace_string="pin",
        use_regex=False,
        keep_file_date=True,
    )

    _collect_results(engine, options)

    new_mtime = target.stat().st_mtime
    assert abs(new_mtime - old_mtime) < 2, "mtime should be preserved after replace"


def test_streaming_create_backup_creates_bak_file(tmp_path: Path) -> None:
    """Same as test_create_backup but with a file large enough to hit the streaming path."""
    root = tmp_path / "root"
    root.mkdir()
    target = root / "big_backup.txt"

    filler = ("abcdefghij" * 1000) + "\n"
    text = filler * 500 + "needle big\n" + filler * 500
    target.write_bytes((text * 2).encode("utf-8"))

    engine = SearchEngine()
    options = SearchOptions(
        search_path=str(root),
        search_string="needle",
        replace_string="pin",
        use_regex=False,
        create_backup=True,
    )

    results = _collect_results(engine, options)

    assert len(results) == 1
    backup = root / "big_backup.txt.bak"
    assert backup.exists(), "streaming backup file should be created"
    assert "needle" in backup.read_text(encoding="utf-8")
    assert "pin big" in target.read_text(encoding="utf-8")
