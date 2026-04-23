from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser


@dataclass
class Bookmark:
    name: str = ""
    search: str = ""
    replace: str = ""
    path: str = ""

    use_regex: bool = False
    case_sensitive: bool = False
    dot_matches_newline: bool = False
    backup: bool = False
    keep_file_date: bool = False
    whole_words: bool = False
    utf8: bool = False
    binary: bool = False
    include_system: bool = False
    include_folder: bool = False
    include_sym_links: bool = False
    include_hidden: bool = False
    include_binary: bool = False

    exclude_dirs: str = ""
    file_match: str = ""
    file_match_regex: bool = False


class BookmarksRepository:
    def __init__(self, ini_path: Path) -> None:
        self._ini_path = ini_path
        self._cfg = configparser.ConfigParser()

    def load(self) -> None:
        self._cfg.read(self._ini_path, encoding="utf-8")

    def save(self) -> None:
        self._ini_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ini_path.open("w", encoding="utf-8") as f:
            self._cfg.write(f)

    def add_bookmark(self, bm: Bookmark) -> None:
        section = bm.name
        if not section:
            raise ValueError("bookmark name is required")

        self._cfg[section] = {
            "search": bm.search,
            "replace": bm.replace,
            "path": bm.path,
            "useregex": str(int(bm.use_regex)),
            "casesensitive": str(int(bm.case_sensitive)),
            "dotmatchesnewline": str(int(bm.dot_matches_newline)),
            "backup": str(int(bm.backup)),
            "keepfiledate": str(int(bm.keep_file_date)),
            "wholewords": str(int(bm.whole_words)),
            "utf8": str(int(bm.utf8)),
            "binary": str(int(bm.binary)),
            "includesystem": str(int(bm.include_system)),
            "includefolder": str(int(bm.include_folder)),
            "includesymlinks": str(int(bm.include_sym_links)),
            "includehidden": str(int(bm.include_hidden)),
            "includebinary": str(int(bm.include_binary)),
            "excludedirs": bm.exclude_dirs,
            "filematch": bm.file_match,
            "filematchregex": str(int(bm.file_match_regex)),
        }

    def remove_bookmark(self, name: str) -> None:
        if self._cfg.has_section(name):
            self._cfg.remove_section(name)

    def get_bookmark(self, name: str) -> Bookmark | None:
        if not self._cfg.has_section(name):
            return None
        section = self._cfg[name]
        return Bookmark(
            name=name,
            search=section.get("search", ""),
            replace=section.get("replace", ""),
            path=section.get("path", ""),
            use_regex=section.getboolean("useregex", fallback=False),
            case_sensitive=section.getboolean("casesensitive", fallback=False),
            dot_matches_newline=section.getboolean("dotmatchesnewline", fallback=False),
            backup=section.getboolean("backup", fallback=False),
            keep_file_date=section.getboolean("keepfiledate", fallback=False),
            whole_words=section.getboolean("wholewords", fallback=False),
            utf8=section.getboolean("utf8", fallback=False),
            binary=section.getboolean("binary", fallback=False),
            include_system=section.getboolean("includesystem", fallback=False),
            include_folder=section.getboolean("includefolder", fallback=False),
            include_sym_links=section.getboolean("includesymlinks", fallback=False),
            include_hidden=section.getboolean("includehidden", fallback=False),
            include_binary=section.getboolean("includebinary", fallback=False),
            exclude_dirs=section.get("excludedirs", ""),
            file_match=section.get("filematch", ""),
            file_match_regex=section.getboolean("filematchregex", fallback=False),
        )

    def list_names(self) -> list[str]:
        return list(self._cfg.sections())
