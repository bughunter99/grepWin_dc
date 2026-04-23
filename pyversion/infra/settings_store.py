from __future__ import annotations

from pathlib import Path
import configparser


class SettingsStore:
    def __init__(self, ini_path: Path) -> None:
        self._ini_path = ini_path
        self._cfg = configparser.ConfigParser()

    def load(self) -> None:
        self._cfg.read(self._ini_path, encoding="utf-8")

    def save(self) -> None:
        self._ini_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ini_path.open("w", encoding="utf-8") as f:
            self._cfg.write(f)

    def get(self, section: str, key: str, default: str = "") -> str:
        return self._cfg.get(section, key, fallback=default)

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        return self._cfg.getboolean(section, key, fallback=default)

    def set(self, section: str, key: str, value: str) -> None:
        if not self._cfg.has_section(section):
            self._cfg.add_section(section)
        self._cfg.set(section, key, value)

    def set_bool(self, section: str, key: str, value: bool) -> None:
        self.set(section, key, "1" if value else "0")
