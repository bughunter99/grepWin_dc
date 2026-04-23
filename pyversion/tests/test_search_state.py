from __future__ import annotations

from pathlib import Path

from core.search_state import SearchDialogState
from infra.settings_store import SettingsStore


def test_state_round_trip(tmp_path: Path) -> None:
    ini = tmp_path / "settings.ini"
    store = SettingsStore(ini)

    state = SearchDialogState(
        search_path="d:/repo|d:/work",
        search_string="abc",
        replace_string="def",
        use_regex=True,
        case_sensitive=True,
        dot_matches_newline=True,
        whole_words=True,
        include_subfolders=True,
        include_hidden=True,
        include_system=True,
        include_sym_links=True,
        include_binary=True,
        create_backup=True,
        keep_file_date=True,
        utf8=True,
        binary=False,
        file_match="*.py",
        file_match_regex=False,
        exclude_dirs="build|dist",
        show_content=True,
        size_enabled=True,
        size_value=2048,
        size_cmp="gt",
        date_limit_mode="between",
        date1="2025-01-01",
        date2="2025-12-31",
    )

    state.to_settings(store)
    store.save()

    loaded = SettingsStore(ini)
    loaded.load()
    restored = SearchDialogState.from_settings(loaded)

    assert restored.search_path == state.search_path
    assert restored.search_string == state.search_string
    assert restored.replace_string == state.replace_string
    assert restored.use_regex is True
    assert restored.case_sensitive is True
    assert restored.dot_matches_newline is True
    assert restored.whole_words is True
    assert restored.include_subfolders is True
    assert restored.include_hidden is True
    assert restored.include_system is True
    assert restored.include_sym_links is True
    assert restored.include_binary is True
    assert restored.create_backup is True
    assert restored.keep_file_date is True
    assert restored.utf8 is True
    assert restored.binary is False
    assert restored.file_match == "*.py"
    assert restored.file_match_regex is False
    assert restored.exclude_dirs == "build|dist"
    assert restored.show_content is True
    assert restored.size_enabled is True
    assert restored.size_value == 2048
    assert restored.size_cmp == "gt"
    assert restored.date_limit_mode == "between"
    assert restored.date1 == "2025-01-01"
    assert restored.date2 == "2025-12-31"
