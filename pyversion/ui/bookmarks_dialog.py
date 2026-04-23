from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QVBoxLayout

from core.bookmarks import Bookmark, BookmarksRepository


class BookmarksDialog(QDialog):
    def __init__(self, bookmarks_ini: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bookmarks")
        self._repo = BookmarksRepository(bookmarks_ini)
        self._repo.load()

        self.list_widget = QListWidget(self)
        for name in self._repo.list_names():
            self.list_widget.addItem(name)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addWidget(buttons)

    def selected_name(self) -> str:
        item = self.list_widget.currentItem()
        return item.text() if item else ""

    def selected_bookmark(self) -> Bookmark | None:
        name = self.selected_name()
        if not name:
            return None
        return self._repo.get_bookmark(name)
