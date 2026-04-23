from __future__ import annotations

from app import parse_startup_args


def test_parse_grepwin_style_switches() -> None:
    state, action = parse_startup_args(
        [
            "/searchpath", "d:/repo",
            "/searchfor", "needle",
            "/replacewith", "new",
            "/filemask", "*.py;*.txt",
            "/direxcluderegex", "build|dist",
            "/execute",
            "/content",
        ]
    )

    assert state.search_path == "d:/repo"
    assert state.search_string == "needle"
    assert state.replace_string == "new"
    assert state.file_match == "*.py;*.txt"
    assert state.exclude_dirs == "build|dist"
    assert state.show_content is True
    assert action == "search"


def test_parse_execute_replace_priority() -> None:
    state, action = parse_startup_args(["/executereplace", "/searchfor", "x"])

    assert state.search_string == "x"
    assert state.use_regex is True
    assert action == "replace"


def test_parse_filemaskregex_sets_regex_flag() -> None:
    state, action = parse_startup_args(["/filemaskregex", ".*\\.log$"])

    assert state.file_match == r".*\.log$"
    assert state.file_match_regex is True
    assert action is None


def test_parse_extended_filter_switches() -> None:
    state, action = parse_startup_args(
        [
            "/includesystem", "yes",
            "/includesymlinks", "1",
            "/includebinary", "true",
            "/binary", "1",
            "/utf8", "1",
            "/size", "4096",
            "/sizecmp", "2",
            "/datelimitmode", "between",
            "/date1", "2025-01-01",
            "/date2", "2025-12-31",
        ]
    )

    assert state.include_system is True
    assert state.include_sym_links is True
    assert state.include_binary is True
    assert state.binary is True
    assert state.utf8 is True
    assert state.size_enabled is True
    assert state.size_value == 4096
    assert state.size_cmp == "gt"
    assert state.date_limit_mode == "between"
    assert state.date1 == "2025-01-01"
    assert state.date2 == "2025-12-31"
    assert action is None


def test_parse_numeric_datelimit_mapping() -> None:
    state, _ = parse_startup_args(["/datelimit", "3"])
    assert state.date_limit_mode == "between"


def test_parse_datelimitmode_overrides_numeric_datelimit() -> None:
    state, _ = parse_startup_args(["/datelimit", "1", "/datelimitmode", "older"])
    assert state.date_limit_mode == "older"
