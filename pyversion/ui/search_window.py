from __future__ import annotations

from pathlib import Path
import os
import subprocess
import shlex

from PySide6.QtCore import QDate, QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QMenu,
    QVBoxLayout,
)

from core.search_engine import SearchEngine, SearchOptions, SearchProgress
from core.search_info import SearchInfo
from core.search_state import SearchDialogState
from infra.settings_store import SettingsStore
from ui.bookmarks_dialog import BookmarksDialog
from ui.settings_dialog import SettingsDialog


class SearchWorker(QObject):
    result_found = Signal(object)
    progress_updated = Signal(object)
    finished = Signal(bool, str)

    def __init__(self, options: SearchOptions) -> None:
        super().__init__()
        self._options = options
        self._engine: SearchEngine | None = None
        self._cancel_requested = False
        self._last_path = ""

    @Slot()
    def run(self) -> None:
        self._engine = SearchEngine()
        if self._cancel_requested:
            self._engine.cancelled = True

        def on_result(info: SearchInfo) -> None:
            self.result_found.emit(info)

        def on_progress(progress: SearchProgress) -> None:
            self._last_path = progress.current_path
            self.progress_updated.emit(progress)

        self._engine.search_thread(self._options, on_result=on_result, on_progress=on_progress)
        self.finished.emit(self._engine.cancelled, self._last_path)

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True
        if self._engine is not None:
            self._engine.cancelled = True


class SearchWindow(QDialog):
    def __init__(self, app_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("grepWin PyVersion")
        self.resize(980, 640)

        self._app_dir = app_dir
        self._settings = SettingsStore(app_dir / "grepwin_py.ini")
        self._settings.load()
        self._state = SearchDialogState.from_settings(self._settings)
        self._searching = False
        self._undo_deleted_rows_stack: list[list[dict[str, object]]] = []
        self._search_thread: QThread | None = None
        self._search_worker: SearchWorker | None = None
        self._found_results: list[SearchInfo] = []
        self._matched_count = 0
        self._last_progress_path = ""
        self._active_show_content_mode = False

        self.search_path_edit = QLineEdit(self._state.search_path)
        self.browse_path_button = QPushButton("...")
        self.browse_path_button.setToolTip("Select search folder")
        self.browse_path_button.setFixedWidth(32)
        self.browse_path_button.clicked.connect(self._browse_search_path)
        self.search_text_edit = QLineEdit(self._state.search_string)
        self.replace_text_edit = QLineEdit(self._state.replace_string)
        self.file_match_edit = QLineEdit(self._state.file_match)
        self.exclude_dirs_edit = QLineEdit(self._state.exclude_dirs)
        self.size_value_edit = QLineEdit(str(self._state.size_value))
        self.date1_edit = QDateEdit()
        self.date2_edit = QDateEdit()
        self.date1_edit.setCalendarPopup(True)
        self.date2_edit.setCalendarPopup(True)
        self.date1_edit.setDisplayFormat("yyyy-MM-dd")
        self.date2_edit.setDisplayFormat("yyyy-MM-dd")

        self.use_regex = QCheckBox("Use regex")
        self.case_sensitive = QCheckBox("Case sensitive")
        self.dot_matches_newline = QCheckBox("Dot matches newline")
        self.whole_words = QCheckBox("Whole words")
        self.include_subfolders = QCheckBox("Include subfolders")
        self.include_hidden = QCheckBox("Include hidden")
        self.include_binary = QCheckBox("Include binary")
        self.include_system = QCheckBox("Include system")
        self.include_symlinks = QCheckBox("Include symlinks")
        self.size_enabled = QCheckBox("Enable size filter")
        self.force_binary = QCheckBox("Treat as binary")
        self.file_match_regex = QCheckBox("File mask is regex")
        self.result_files_radio = QRadioButton("Result files")
        self.result_content_radio = QRadioButton("Result content")

        self.size_cmp_combo = QComboBox()
        self.size_cmp_combo.addItems(["lt", "eq", "gt"])
        self.date_mode_combo = QComboBox()
        self.date_mode_combo.addItems(["all", "newer", "older", "between"])

        self.use_regex.setChecked(self._state.use_regex)
        self.case_sensitive.setChecked(self._state.case_sensitive)
        self.dot_matches_newline.setChecked(self._state.dot_matches_newline)
        self.whole_words.setChecked(self._state.whole_words)
        self.include_subfolders.setChecked(self._state.include_subfolders)
        self.include_hidden.setChecked(self._state.include_hidden)
        self.include_binary.setChecked(self._state.include_binary)
        self.include_system.setChecked(self._state.include_system)
        self.include_symlinks.setChecked(self._state.include_sym_links)
        self.size_enabled.setChecked(self._state.size_enabled)
        self.force_binary.setChecked(self._state.binary)
        self.file_match_regex.setChecked(self._state.file_match_regex)
        self.result_content_radio.setChecked(self._state.show_content)
        self.result_files_radio.setChecked(not self._state.show_content)
        self.size_cmp_combo.setCurrentText(self._state.size_cmp)
        self.date_mode_combo.setCurrentText(self._state.date_limit_mode)
        self._set_qdate_if_valid(self.date1_edit, self._state.date1)
        self._set_qdate_if_valid(self.date2_edit, self._state.date2)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)

        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self._on_replace)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._on_cancel)

        self.bookmarks_button = QPushButton("Bookmarks")
        self.bookmarks_button.clicked.connect(self._open_bookmarks)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings)

        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(["File", "Matches", "Line", "Column", "Preview"])
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setSortingEnabled(True)
        self.results.cellDoubleClicked.connect(self._open_result_row)
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._show_result_context_menu)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.progress = QProgressBar(self)
        self.progress.setVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        self._build_layout()
        self.date_mode_combo.currentTextChanged.connect(self._update_date_edit_state)
        self._update_date_edit_state()

    def apply_startup_state(self, state: SearchDialogState) -> None:
        self.search_path_edit.setText(state.search_path)
        self.search_text_edit.setText(state.search_string)
        self.replace_text_edit.setText(state.replace_string)
        self.file_match_edit.setText(state.file_match)
        self.exclude_dirs_edit.setText(state.exclude_dirs)
        self.size_value_edit.setText(str(state.size_value))
        self._set_qdate_if_valid(self.date1_edit, state.date1)
        self._set_qdate_if_valid(self.date2_edit, state.date2)

        self.use_regex.setChecked(state.use_regex)
        self.case_sensitive.setChecked(state.case_sensitive)
        self.dot_matches_newline.setChecked(state.dot_matches_newline)
        self.whole_words.setChecked(state.whole_words)
        self.include_subfolders.setChecked(state.include_subfolders)
        self.include_hidden.setChecked(state.include_hidden)
        self.include_binary.setChecked(state.include_binary)
        self.include_system.setChecked(state.include_system)
        self.include_symlinks.setChecked(state.include_sym_links)
        self.size_enabled.setChecked(state.size_enabled)
        self.force_binary.setChecked(state.binary)
        self.file_match_regex.setChecked(state.file_match_regex)
        self.result_content_radio.setChecked(state.show_content)
        self.result_files_radio.setChecked(not state.show_content)
        self.size_cmp_combo.setCurrentText(state.size_cmp)
        self.date_mode_combo.setCurrentText(state.date_limit_mode)
        self._update_date_edit_state()

    def execute_action(self, action: str) -> None:
        if action == "replace":
            self._run_search(replace=True)
        elif action == "search":
            self._run_search(replace=False)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        grid = QGridLayout()
        grid.addWidget(QLabel("Search path"), 0, 0)
        _path_row = QHBoxLayout()
        _path_row.setContentsMargins(0, 0, 0, 0)
        _path_row.addWidget(self.search_path_edit)
        _path_row.addWidget(self.browse_path_button)
        grid.addLayout(_path_row, 0, 1, 1, 3)
        grid.addWidget(QLabel("Search"), 1, 0)
        grid.addWidget(self.search_text_edit, 1, 1, 1, 3)
        grid.addWidget(QLabel("Replace"), 2, 0)
        grid.addWidget(self.replace_text_edit, 2, 1, 1, 3)
        grid.addWidget(QLabel("File mask"), 3, 0)
        grid.addWidget(self.file_match_edit, 3, 1, 1, 3)
        grid.addWidget(QLabel("Exclude dirs regex"), 4, 0)
        grid.addWidget(self.exclude_dirs_edit, 4, 1, 1, 3)
        grid.addWidget(QLabel("Size"), 5, 0)
        grid.addWidget(self.size_enabled, 5, 1)
        grid.addWidget(self.size_cmp_combo, 5, 2)
        grid.addWidget(self.size_value_edit, 5, 3)
        grid.addWidget(QLabel("Date"), 6, 0)
        grid.addWidget(self.date_mode_combo, 6, 1)
        grid.addWidget(self.date1_edit, 6, 2)
        grid.addWidget(self.date2_edit, 6, 3)

        grid.addWidget(self.use_regex, 7, 0)
        grid.addWidget(self.case_sensitive, 7, 1)
        grid.addWidget(self.dot_matches_newline, 7, 2)
        grid.addWidget(self.whole_words, 7, 3)
        grid.addWidget(self.include_subfolders, 8, 0)
        grid.addWidget(self.include_hidden, 8, 1)
        grid.addWidget(self.include_binary, 8, 2)
        grid.addWidget(self.force_binary, 8, 3)
        grid.addWidget(self.include_system, 9, 0)
        grid.addWidget(self.include_symlinks, 9, 1)
        grid.addWidget(self.file_match_regex, 9, 2)
        grid.addWidget(self.result_files_radio, 10, 0)
        grid.addWidget(self.result_content_radio, 10, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.search_button)
        buttons.addWidget(self.replace_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.bookmarks_button)
        buttons.addWidget(self.settings_button)
        buttons.addStretch(1)

        root.addLayout(grid)
        root.addLayout(buttons)
        root.addWidget(self.progress)
        root.addWidget(self.results)
        root.addWidget(self.status_label)

    def _collect_state(self) -> SearchDialogState:
        size_text = self.size_value_edit.text().strip()
        try:
            size_value = int(size_text) if size_text else 0
        except ValueError:
            size_value = 0

        return SearchDialogState(
            search_path=self.search_path_edit.text().strip(),
            search_string=self.search_text_edit.text(),
            replace_string=self.replace_text_edit.text(),
            use_regex=self.use_regex.isChecked(),
            case_sensitive=self.case_sensitive.isChecked(),
            dot_matches_newline=self.dot_matches_newline.isChecked(),
            whole_words=self.whole_words.isChecked(),
            include_subfolders=self.include_subfolders.isChecked(),
            include_hidden=self.include_hidden.isChecked(),
            include_binary=self.include_binary.isChecked(),
            include_system=self.include_system.isChecked(),
            include_sym_links=self.include_symlinks.isChecked(),
            create_backup=self._state.create_backup,
            keep_file_date=self._state.keep_file_date,
            utf8=self._state.utf8,
            binary=self.force_binary.isChecked(),
            file_match=self.file_match_edit.text().strip(),
            file_match_regex=self.file_match_regex.isChecked(),
            exclude_dirs=self.exclude_dirs_edit.text().strip(),
            show_content=self.result_content_radio.isChecked(),
            size_enabled=self.size_enabled.isChecked(),
            size_value=size_value,
            size_cmp=self.size_cmp_combo.currentText(),
            date_limit_mode=self.date_mode_combo.currentText(),
            date1=self.date1_edit.date().toString("yyyy-MM-dd"),
            date2=self.date2_edit.date().toString("yyyy-MM-dd"),
        )

    def _browse_search_path(self) -> None:
        current = self.search_path_edit.text().strip()
        start_dir = current if current and Path(current).is_dir() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Search Folder", start_dir)
        if folder:
            self.search_path_edit.setText(folder)

    def _on_search(self) -> None:
        self._run_search(replace=False)

    def _on_replace(self) -> None:
        self._run_search(replace=True)

    def _on_cancel(self) -> None:
        if self._searching and self._search_worker is not None:
            self._search_worker.cancel()
            self.status_label.setText("Cancelling...")

    def _set_search_running_ui(self, running: bool) -> None:
        self._searching = running
        self.search_button.setEnabled(not running)
        self.replace_button.setEnabled(not running)
        self.bookmarks_button.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.result_files_radio.setEnabled(not running)
        self.result_content_radio.setEnabled(not running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

    def _run_search(self, replace: bool) -> None:
        if self._searching:
            return
        state = self._collect_state()
        options: SearchOptions = state.to_search_options(replace_enabled=replace)
        self._found_results = []
        self._matched_count = 0
        self._last_progress_path = ""
        self._active_show_content_mode = state.show_content
        self._state = state
        self._prepare_results_view()
        self._set_search_running_ui(True)
        self._search_thread = QThread(self)
        self._search_worker = SearchWorker(options)
        self._search_worker.moveToThread(self._search_thread)

        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.result_found.connect(self._handle_search_result)
        self._search_worker.progress_updated.connect(self._handle_search_progress)
        self._search_worker.finished.connect(self._handle_search_finished)
        self._search_worker.finished.connect(self._search_thread.quit)
        self._search_worker.finished.connect(self._search_worker.deleteLater)
        self._search_thread.finished.connect(self._search_thread.deleteLater)
        self._search_thread.finished.connect(self._clear_search_thread_refs)
        self._search_thread.start()

    @Slot(object)
    def _handle_search_result(self, info: SearchInfo) -> None:
        if info.match_count == 0:
            return
        self._matched_count += 1
        self._found_results.append(info)
        if self._active_show_content_mode:
            self._append_content_results(info)
        else:
            self._append_file_result(info)

    @Slot(object)
    def _handle_search_progress(self, progress: SearchProgress) -> None:
        self._last_progress_path = progress.current_path
        p = Path(progress.current_path) if progress.current_path else None
        current_name = p.name if p else ""
        current_dir = str(p.parent) if p and p.parent != p else ""
        dir_part = f"  [{current_dir}]" if current_dir else ""
        self.status_label.setText(
            f"Scanning... scanned: {progress.scanned_files}, matched: {progress.matched_files}, file: {current_name}{dir_part}"
        )
        self.progress.setFormat(
            f"Scanned: {progress.scanned_files} / Matched: {progress.matched_files} / {current_name}"
        )

    @Slot(bool, str)
    def _handle_search_finished(self, cancelled: bool, last_path: str) -> None:
        self._set_search_running_ui(False)
        self._last_progress_path = last_path or self._last_progress_path
        self._render_results(self._found_results)
        current_name = Path(self._last_progress_path).name if self._last_progress_path else ""
        if cancelled:
            self.status_label.setText(f"Cancelled. matched files: {self._matched_count}, last file: {current_name}")
        else:
            self.status_label.setText(f"Done. matched files: {self._matched_count}, last file: {current_name}")
        self._save_ui_state(self._state)

    @Slot()
    def _clear_search_thread_refs(self) -> None:
        self._search_worker = None
        self._search_thread = None

    def _append_file_result(self, info: SearchInfo) -> None:
        line = info.match_lines_numbers[0] if info.match_lines_numbers else 0
        col = info.match_columns_numbers[0] if info.match_columns_numbers else 0
        preview = info.match_lines_map.get(line, "")

        row = self.results.rowCount()
        self.results.insertRow(row)
        self.results.setItem(row, 0, QTableWidgetItem(info.file_path))
        self.results.setItem(row, 1, self._numeric_item(info.match_count))
        self.results.setItem(row, 2, self._numeric_item(line))
        self.results.setItem(row, 3, self._numeric_item(col))
        self.results.setItem(row, 4, QTableWidgetItem(preview))
        self._attach_row_metadata(row, info.file_path, line)

    def _append_content_results(self, info: SearchInfo) -> None:
        for idx, line in enumerate(info.match_lines_numbers):
            col = info.match_columns_numbers[idx] if idx < len(info.match_columns_numbers) else 0
            length = info.match_lengths[idx] if idx < len(info.match_lengths) else 0
            preview = info.match_lines_map.get(line, "")

            row = self.results.rowCount()
            self.results.insertRow(row)
            self.results.setItem(row, 0, QTableWidgetItem(info.file_path))
            self.results.setItem(row, 1, self._numeric_item(line))
            self.results.setItem(row, 2, self._numeric_item(col))
            self.results.setItem(row, 3, self._numeric_item(length))
            self.results.setItem(row, 4, QTableWidgetItem(preview))
            self._attach_row_metadata(row, info.file_path, line)

    def _render_results(self, found: list[SearchInfo]) -> None:
        self._prepare_results_view()

        for info in found:
            if self._active_show_content_mode:
                self._append_content_results(info)
            else:
                self._append_file_result(info)

        self.results.setSortingEnabled(True)

    def _prepare_results_view(self) -> None:
        self.results.setSortingEnabled(False)
        self.results.setRowCount(0)

        if self._active_show_content_mode:
            self.results.setHorizontalHeaderLabels(["File", "Line", "Column", "Length", "Preview"])
        else:
            self.results.setHorizontalHeaderLabels(["File", "Matches", "Line", "Column", "Preview"])

    def _open_bookmarks(self) -> None:
        dlg = BookmarksDialog(self._app_dir / "bookmarks.ini", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        bookmark = dlg.selected_bookmark()
        if not bookmark:
            return
        self.search_text_edit.setText(bookmark.search)
        self.replace_text_edit.setText(bookmark.replace)
        if bookmark.path:
            self.search_path_edit.setText(bookmark.path)
        self.use_regex.setChecked(bookmark.use_regex)
        self.case_sensitive.setChecked(bookmark.case_sensitive)
        self.dot_matches_newline.setChecked(bookmark.dot_matches_newline)
        self.whole_words.setChecked(bookmark.whole_words)
        self.include_subfolders.setChecked(bookmark.include_folder)
        self.include_hidden.setChecked(bookmark.include_hidden)
        self.include_binary.setChecked(bookmark.include_binary)
        self.file_match_edit.setText(bookmark.file_match)
        self.file_match_regex.setChecked(bookmark.file_match_regex)
        self.exclude_dirs_edit.setText(bookmark.exclude_dirs)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        dlg.exec()

    def _save_ui_state(self, state: SearchDialogState) -> None:
        state.to_settings(self._settings)
        self._settings.save()

    def _update_date_edit_state(self) -> None:
        mode = self.date_mode_combo.currentText()
        self.date1_edit.setEnabled(mode in {"newer", "older", "between"})
        self.date2_edit.setEnabled(mode == "between")

    @staticmethod
    def _set_qdate_if_valid(edit: QDateEdit, value: str) -> None:
        date = QDate.fromString(value.strip(), "yyyy-MM-dd") if value else QDate()
        if date.isValid():
            edit.setDate(date)

    def _attach_row_metadata(self, row: int, file_path: str, line: int) -> None:
        item = self.results.item(row, 0)
        if item is None:
            return
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setData(Qt.ItemDataRole.UserRole + 1, line)

    def _open_result_row(self, row: int, _column: int) -> None:
        item = self.results.item(row, 0)
        if item is None:
            return
        file_path = item.data(Qt.ItemDataRole.UserRole)
        line = item.data(Qt.ItemDataRole.UserRole + 1)
        if not file_path:
            return
        self._open_file(file_path, int(line or 0))

    def _show_result_context_menu(self, pos) -> None:
        item = self.results.itemAt(pos)
        if item is None:
            return

        row = item.row()
        file_item = self.results.item(row, 0)
        if file_item is None:
            return

        file_path = file_item.data(Qt.ItemDataRole.UserRole) or file_item.text()
        line = int(file_item.data(Qt.ItemDataRole.UserRole + 1) or 0)

        menu = QMenu(self)
        open_action = QAction("Open", self)
        open_folder_action = QAction("Open containing folder", self)
        copy_path_action = QAction("Copy path", self)
        copy_row_action = QAction("Copy row", self)
        copy_selected_paths_action = QAction("Copy selected paths", self)
        copy_selected_rows_action = QAction("Copy selected rows", self)

        open_action.triggered.connect(lambda: self._open_file(file_path, line))
        open_folder_action.triggered.connect(lambda: self._open_containing_folder(str(file_path)))
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(file_path)))
        copy_row_action.triggered.connect(lambda: QApplication.clipboard().setText(self._row_text(row)))
        copy_selected_paths_action.triggered.connect(self._copy_selected_paths)
        copy_selected_rows_action.triggered.connect(self._copy_selected_rows)

        menu.addAction(open_action)
        menu.addAction(open_folder_action)
        menu.addAction(copy_path_action)
        menu.addAction(copy_row_action)
        menu.addAction(copy_selected_paths_action)
        menu.addAction(copy_selected_rows_action)
        menu.exec(self.results.viewport().mapToGlobal(pos))

    def _row_text(self, row: int) -> str:
        values: list[str] = []
        for col in range(self.results.columnCount()):
            item = self.results.item(row, col)
            values.append(item.text() if item else "")
        return "\t".join(values)

    def _open_file(self, file_path: str, line: int) -> None:
        editor_cmd = self._settings.get("settings", "editorcmd", "").strip()
        prefer_vscode = self._settings.get_bool("settings", "prefervscode", True)
        if editor_cmd:
            if self._run_editor_command(editor_cmd, file_path, line):
                return

        if prefer_vscode:
            try:
                if line > 0:
                    subprocess.Popen(["code", "--goto", f"{file_path}:{line}"], shell=False)
                    return
                subprocess.Popen(["code", file_path], shell=False)
                return
            except Exception:
                pass

        try:
            os.startfile(file_path)
        except Exception:
            pass

    @staticmethod
    def _run_editor_command(template: str, file_path: str, line: int) -> bool:
        cmd = template.replace("{file}", file_path).replace("{line}", str(line)).strip()
        if not cmd:
            return False
        try:
            args = shlex.split(cmd, posix=False)
            subprocess.Popen(args, shell=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _open_containing_folder(file_path: str) -> None:
        try:
            parent = str(Path(file_path).resolve().parent)
            os.startfile(parent)
        except Exception:
            pass

    def _copy_selected_rows(self) -> None:
        indexes = self.results.selectionModel().selectedRows()
        if not indexes:
            return
        rows = sorted({idx.row() for idx in indexes})
        text = "\n".join(self._row_text(row) for row in rows)
        QApplication.clipboard().setText(text)

    def _copy_selected_paths(self) -> None:
        indexes = self.results.selectionModel().selectedRows()
        if not indexes:
            return
        rows = sorted({idx.row() for idx in indexes})
        paths: list[str] = []
        for row in rows:
            item = self.results.item(row, 0)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole) or item.text()
            if path:
                paths.append(str(path))
        if paths:
            QApplication.clipboard().setText("\n".join(paths))

    def _remove_selected_rows(self) -> None:
        indexes = self.results.selectionModel().selectedRows()
        if not indexes:
            return
        rows_asc = sorted({idx.row() for idx in indexes})
        removed_batch = [self._capture_row(row) for row in rows_asc]
        self._undo_deleted_rows_stack.append(removed_batch)

        rows = sorted(rows_asc, reverse=True)
        self.results.setSortingEnabled(False)
        for row in rows:
            self.results.removeRow(row)
        self.results.setSortingEnabled(True)

    def _undo_remove_selected_rows(self) -> None:
        if not self._undo_deleted_rows_stack:
            return
        batch = self._undo_deleted_rows_stack.pop()
        self.results.setSortingEnabled(False)
        for row_data in batch:
            row = int(row_data["row"])
            insert_at = max(0, min(row, self.results.rowCount()))
            self.results.insertRow(insert_at)
            values = row_data["values"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                numeric_cols = row_data.get("numeric_cols", set())
                if col in numeric_cols:
                    try:
                        item.setData(Qt.ItemDataRole.EditRole, int(value))
                    except ValueError:
                        pass
                self.results.setItem(insert_at, col, item)

            file_path = row_data.get("file_path", "")
            line = int(row_data.get("line", 0))
            self._attach_row_metadata(insert_at, str(file_path), line)
        self.results.setSortingEnabled(True)

    @staticmethod
    def _numeric_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value))
        item.setData(Qt.ItemDataRole.EditRole, int(value))
        return item

    def _capture_row(self, row: int) -> dict[str, object]:
        values: list[str] = []
        numeric_cols: set[int] = set()
        for col in range(self.results.columnCount()):
            item = self.results.item(row, col)
            if item is None:
                values.append("")
                continue
            text = item.text()
            values.append(text)
            if isinstance(item.data(Qt.ItemDataRole.EditRole), int):
                numeric_cols.add(col)

        first_item = self.results.item(row, 0)
        file_path = ""
        line = 0
        if first_item is not None:
            file_path = str(first_item.data(Qt.ItemDataRole.UserRole) or first_item.text())
            line = int(first_item.data(Qt.ItemDataRole.UserRole + 1) or 0)

        return {
            "row": row,
            "values": values,
            "numeric_cols": numeric_cols,
            "file_path": file_path,
            "line": line,
        }

    def keyPressEvent(self, event) -> None:
        if self.results.hasFocus():
            if event.matches(QKeySequence.StandardKey.SelectAll):
                self.results.selectAll()
                event.accept()
                return

            if event.matches(QKeySequence.StandardKey.Copy):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._copy_selected_rows()
                else:
                    self._copy_selected_paths()
                event.accept()
                return

            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = self.results.currentRow()
                if row >= 0:
                    self._open_result_row(row, 0)
                    event.accept()
                    return

            if event.key() == Qt.Key.Key_Delete:
                self._remove_selected_rows()
                event.accept()
                return

            if event.matches(QKeySequence.StandardKey.Undo):
                self._undo_remove_selected_rows()
                event.accept()
                return

        super().keyPressEvent(event)
