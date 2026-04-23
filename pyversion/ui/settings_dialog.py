from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit

from infra.settings_store import SettingsStore


class SettingsDialog(QDialog):
    _PRESETS = {
        "Custom": "",
        "VS Code": "code --goto {file}:{line}",
        "Notepad++": 'notepad++ -n{line} "{file}"',
        "Sublime Text": 'subl "{file}":{line}',
        "Windows Notepad": 'notepad "{file}"',
    }

    def __init__(self, settings_store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._store = settings_store

        self.close_on_esc = QCheckBox("Close on Esc")
        self.backup_in_folder = QCheckBox("Create backup (.bak) before replacing")
        self.keep_file_date = QCheckBox("Keep original file date after replacing")
        self.prefer_vscode = QCheckBox("Prefer VS Code for opening results")
        self.editor_cmd = QLineEdit(self._store.get("settings", "editorcmd", ""))
        self.editor_preset = QComboBox()
        self.editor_preset.addItems(list(self._PRESETS.keys()))
        self.editor_cmd.setPlaceholderText("Example: code --goto {file}:{line}")

        self.close_on_esc.setChecked(self._store.get_bool("settings", "escclose", False))
        self.backup_in_folder.setChecked(self._store.get_bool("settings", "backupinfolder", False))
        self.keep_file_date.setChecked(self._store.get_bool("settings", "keepfiledate", False))
        self.prefer_vscode.setChecked(self._store.get_bool("settings", "prefervscode", True))
        self._sync_preset_from_command(self.editor_cmd.text().strip())
        self.editor_preset.currentTextChanged.connect(self._apply_preset)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_and_save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow(self.close_on_esc)
        form.addRow(self.backup_in_folder)
        form.addRow(self.keep_file_date)
        form.addRow(self.prefer_vscode)
        form.addRow("Editor preset", self.editor_preset)
        form.addRow("Editor command", self.editor_cmd)
        form.addRow(buttons)

    def _accept_and_save(self) -> None:
        self._store.set_bool("settings", "escclose", self.close_on_esc.isChecked())
        self._store.set_bool("settings", "backupinfolder", self.backup_in_folder.isChecked())
        self._store.set_bool("settings", "keepfiledate", self.keep_file_date.isChecked())
        self._store.set_bool("settings", "prefervscode", self.prefer_vscode.isChecked())
        self._store.set("settings", "editorcmd", self.editor_cmd.text().strip())
        self._store.save()
        self.accept()

    def _sync_preset_from_command(self, command: str) -> None:
        for name, value in self._PRESETS.items():
            if value and value == command:
                self.editor_preset.setCurrentText(name)
                return
        self.editor_preset.setCurrentText("Custom")

    def _apply_preset(self, preset_name: str) -> None:
        value = self._PRESETS.get(preset_name, "")
        if value:
            self.editor_cmd.setText(value)
