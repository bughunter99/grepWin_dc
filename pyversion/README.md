# pyversion

Python/PySide6 migration workspace for grepWin.

## Environment

This project assumes virtualenvwrapper environment `v1`.

```powershell
workon v1
cd d:\data3\grepWin_dc\pyversion
pip install -r requirements.txt
python app.py
pytest -q
```

## Current scope

- Stage 1-4 baseline implemented:
  - app entry and grepWin-like CLI startup parsing
  - Search window with file/content result modes
  - Search engine with text/binary branches
  - path mask and exclude-dir filtering
  - size/date/system/symlink pre-filters
  - SearchInfo model
  - bookmarks/settings storage and dialogs
  - result row double-click open behavior
  - result context menu (open/copy path/copy row)
  - result context menu extras (open containing folder/copy selected rows)
  - configurable editor command (`{file}`, `{line}` placeholders)
  - editor command presets (VS Code, Notepad++, Sublime Text, Windows Notepad)
  - open behavior policy toggle (`Prefer VS Code`)
  - result list keyboard shortcuts:
    - `Enter`: open selected result
    - `Ctrl+C`: copy selected paths
    - `Ctrl+Shift+C`: copy selected rows
    - `Ctrl+A`: select all result rows
    - `Delete`: remove selected rows from current result view
    - `Ctrl+Z`: undo last row-removal batch
  - numeric-aware sorting for line/column/match/length columns
  - search run controls:
    - `Cancel` button (cooperative cancel)
    - progress indicator with scanned/matched counters
    - `QThread`-based background search execution for responsive UI
    - incremental live result rendering while search is running
  - large-file optimization:
    - streaming line-by-line search path for large non-regex searches
    - temp-file based streaming replace for large literal search/replace
    - finer cancel checkpoints in traversal/matching loops

## Notes

- The structure mirrors C++ responsibilities (`CSearchDlg`, `CSearchInfo`, bookmarks/settings modules).
- Behavior parity is incremental and will be improved in Stage 2-5.
- Date inputs use `yyyy-MM-dd` format in the UI.
