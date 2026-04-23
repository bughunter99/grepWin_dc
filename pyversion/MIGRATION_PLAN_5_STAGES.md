# grepWin to Python (PySide6) Migration Plan - 5 Stages

## Goal
- Migrate the current C++/Win32 grepWin app to Python with PySide6.
- Keep class responsibilities and data flow as close as possible to the original architecture.
- Keep behavior parity for search, replace, filtering, sorting, settings, and bookmarks.

## Environment Baseline (workon v1)
- Assumption: virtualenvwrapper is available and the target environment name is `v1`.
- Activate before any implementation or tests:
  1. `workon v1`
  2. `python --version`
  3. `pip install -U pip`
  4. `pip install pyside6 regex`

Recommended pinned baseline (first pass):
- Python: 3.11+ (or current project standard)
- PySide6: latest stable
- regex: latest stable (for advanced regex compatibility if needed)

## Source Architecture Snapshot (from current C++ code)

### Entry and setup
- `src/grepWin.cpp`
  - Parses command line and preset files.
  - Handles single-instance behavior and startup handoff.
  - Creates and configures `CSearchDlg`.

### Main dialog and orchestration
- `src/SearchDlg.h`, `src/SearchDlg.cpp`
  - Central coordinator (`CSearchDlg`) for UI, state, search execution, result handling, and save/load settings.
  - Search pipeline methods:
    - `SearchThread()`
    - `SearchFile()`
    - `SearchOnTextFile()`
    - `SearchByFilePath()`
    - `SendResult()`
  - Result models stored in `m_origItems`, `m_items`, `m_listItems`.

### Core data model
- `src/SearchInfo.h`
  - `CSearchInfo` stores per-file metadata and match details.

### Bookmarks/presets
- `src/Bookmarks.h`, `src/BookmarksDlg.h`
  - Bookmark schema + INI persistence + selection dialog.

### Settings
- `src/Settings.h`, `src/Settings.cpp`
  - Persistent configuration UI and storage.

### Replace formatter
- `src/RegexReplaceFormatter.h`
  - Replacement token processing including `${filepath}`, `${filename}`, `${fileext}`, `${count...}`.

## Class Mapping (C++ -> Python)

- `CSearchDlg` -> `SearchWindow` (PySide6 `QDialog`)
- `CSearchInfo` -> `SearchInfo` (`@dataclass`)
- `CBookmarks` -> `BookmarksRepository` (INI-based persistence)
- `CBookmarksDlg` -> `BookmarksDialog` (`QDialog`)
- `CSettingsDlg` -> `SettingsDialog` (`QDialog`)
- `RegexReplaceFormatter` -> `RegexReplaceFormatter` (Python class with same token semantics)

Keep equivalent public APIs where practical:
- `set_search_path`, `set_search_string`, `set_file_mask`, `set_use_regex`, `set_preset`, `set_execute`, etc.

## Data Flow Parity Target

1. Input sources:
- CLI args / preset file / remembered settings -> UI state fields

2. Execution start:
- User action (Search/Replace/Capture) -> start worker pipeline

3. File traversal and filtering:
- Search paths -> path mask/exclude/date/size/attributes filters -> candidate files

4. File processing:
- Detect encoding -> search and optional replace -> match metadata accumulation

5. UI projection:
- Worker result event -> append/update in-memory results -> table/list refresh

6. Persistence:
- Save window/settings/history/bookmarks on exit or explicit action

## 5-Stage Migration Plan

## Stage 1 - Project skeleton and compatibility contracts
Deliverables:
- Create package skeleton under `pyversion/`:
  - `app.py`
  - `ui/search_window.py`
  - `core/search_info.py`
  - `core/search_engine.py`
  - `core/regex_replace_formatter.py`
  - `core/bookmarks.py`
  - `ui/bookmarks_dialog.py`
  - `ui/settings_dialog.py`
  - `infra/settings_store.py`
- Define compatibility contracts for options/state names matching C++ fields.
- Add basic app startup with PySide6 dialog shell.

Parity checks:
- Option fields map 1:1 with major C++ flags.
- CLI model object can carry values used by the C++ startup path.

Risks:
- Early divergence in naming/state can break parity later.

## Stage 2 - Data model and persistence parity
Deliverables:
- Implement `SearchInfo` dataclass mirroring `CSearchInfo` fields:
  - file path, size, matches, line/column/length arrays, encoding, read error, folder flag, exception.
- Implement `BookmarksRepository` with INI format compatible enough for migration.
- Implement settings storage abstraction:
  - portable INI mode first
  - optional platform-native mode later

Parity checks:
- Import/export of bookmarks preserves all relevant flags.
- Settings round trip reproduces UI state.

Risks:
- INI key naming mismatches with existing presets.

## Stage 3 - Search/replace engine parity
Deliverables:
- Implement `SearchEngine` that follows C++ pipeline structure:
  - `search_thread()` equivalent controller
  - per-file worker `search_file()`
  - text mode branch and binary/memory-mapped branch
- Implement replacement formatter token behavior:
  - `${filepath}`, `${filename}`, `${fileext}`
  - `${count}`, `${count(n)}`, `${count(n,m)}` variants
- Keep regex/text mode behavior and whole-word logic.

Parity checks:
- Golden tests against sample files for:
  - text search
  - regex search
  - replace with counters
  - include/exclude filters
- Match count and line/column semantics are within accepted tolerance.

Risks:
- Boost regex and Python regex behavior differences.
- Encoding edge cases on very large files.

## Stage 4 - UI behavior parity with PySide6
Deliverables:
- Implement `SearchWindow` controls and events close to current UX.
- Implement result views:
  - file mode and content mode
  - sortable columns
  - selection actions (copy/open)
- Wire bookmarks/settings dialogs and action shortcuts.

Parity checks:
- Main user flows behave same as C++:
  - search
  - replace with backup
  - search in found files
  - preset apply
- Result updates remain responsive during long scans.

Risks:
- Thread-to-UI signaling differences between Win32 messages and Qt signals.

## Stage 5 - Validation, hardening, and cutover
Deliverables:
- Build parity test matrix from real-world samples.
- Performance baseline and optimization pass.
- Regression checklist and release notes.
- Optional compatibility bridge for command-line switches.

Parity checks:
- Feature coverage target: >= 90% of C++ daily-use features.
- Stable behavior on large folders and mixed encodings.

Risks:
- Remaining shell/context-menu integration gaps on Windows.

## Suggested pyversion Layout (implementation target)

- `pyversion/app.py`
- `pyversion/ui/search_window.py`
- `pyversion/ui/bookmarks_dialog.py`
- `pyversion/ui/settings_dialog.py`
- `pyversion/core/search_info.py`
- `pyversion/core/search_engine.py`
- `pyversion/core/regex_replace_formatter.py`
- `pyversion/core/bookmarks.py`
- `pyversion/infra/settings_store.py`
- `pyversion/tests/test_search_engine.py`
- `pyversion/tests/test_replace_formatter.py`

## Immediate Next Actions
1. Freeze a field-by-field option map from `CSearchDlg` to Python state class.
2. Implement Stage 1 skeleton and Stage 2 models first.
3. Add test fixtures before Stage 3 engine parity work.
