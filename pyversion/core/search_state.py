from __future__ import annotations

from dataclasses import dataclass

from core.search_engine import SearchOptions
from infra.settings_store import SettingsStore


@dataclass
class SearchDialogState:
    search_path: str = ""
    search_string: str = ""
    replace_string: str = ""

    use_regex: bool = False
    case_sensitive: bool = False
    dot_matches_newline: bool = False
    whole_words: bool = False

    include_subfolders: bool = True
    include_hidden: bool = False
    include_system: bool = False
    include_sym_links: bool = False
    include_binary: bool = False

    create_backup: bool = False
    keep_file_date: bool = False
    utf8: bool = False
    binary: bool = False

    file_match: str = ""
    file_match_regex: bool = False
    exclude_dirs: str = ""
    show_content: bool = False

    size_enabled: bool = False
    size_value: int = 0
    size_cmp: str = "lt"

    date_limit_mode: str = "all"
    date1: str = ""
    date2: str = ""

    @classmethod
    def from_settings(cls, store: SettingsStore) -> "SearchDialogState":
        return cls(
            search_path=store.get("global", "searchpath", ""),
            search_string=store.get("global", "searchfor", ""),
            replace_string=store.get("global", "replacewith", ""),
            use_regex=store.get_bool("global", "useregex", False),
            case_sensitive=store.get_bool("global", "casesensitive", False),
            dot_matches_newline=store.get_bool("global", "dotmatchesnewline", False),
            whole_words=store.get_bool("global", "wholewords", False),
            include_subfolders=store.get_bool("global", "includesubfolders", True),
            include_hidden=store.get_bool("global", "includehidden", False),
            include_system=store.get_bool("global", "includesystem", False),
            include_sym_links=store.get_bool("global", "includesymlinks", False),
            include_binary=store.get_bool("global", "includebinary", False),
            create_backup=store.get_bool("settings", "backupinfolder", False),
            keep_file_date=store.get_bool("settings", "keepfiledate", False),
            utf8=store.get_bool("global", "utf8", False),
            binary=store.get_bool("global", "binary", False),
            file_match=store.get("global", "filematch", ""),
            file_match_regex=store.get_bool("global", "filematchregex", False),
            exclude_dirs=store.get("global", "excludedirs", ""),
            show_content=store.get_bool("global", "showcontent", False),
            size_enabled=store.get_bool("global", "sizeenabled", False),
            size_value=int(store.get("global", "sizevalue", "0") or 0),
            size_cmp=store.get("global", "sizecmp", "lt"),
            date_limit_mode=store.get("global", "datelimitmode", "all"),
            date1=store.get("global", "date1", ""),
            date2=store.get("global", "date2", ""),
        )

    def to_settings(self, store: SettingsStore) -> None:
        store.set("global", "searchpath", self.search_path)
        store.set("global", "searchfor", self.search_string)
        store.set("global", "replacewith", self.replace_string)
        store.set_bool("global", "useregex", self.use_regex)
        store.set_bool("global", "casesensitive", self.case_sensitive)
        store.set_bool("global", "dotmatchesnewline", self.dot_matches_newline)
        store.set_bool("global", "wholewords", self.whole_words)
        store.set_bool("global", "includesubfolders", self.include_subfolders)
        store.set_bool("global", "includehidden", self.include_hidden)
        store.set_bool("global", "includesystem", self.include_system)
        store.set_bool("global", "includesymlinks", self.include_sym_links)
        store.set_bool("global", "includebinary", self.include_binary)
        store.set_bool("settings", "backupinfolder", self.create_backup)
        store.set_bool("settings", "keepfiledate", self.keep_file_date)
        store.set_bool("global", "utf8", self.utf8)
        store.set_bool("global", "binary", self.binary)
        store.set("global", "filematch", self.file_match)
        store.set_bool("global", "filematchregex", self.file_match_regex)
        store.set("global", "excludedirs", self.exclude_dirs)
        store.set_bool("global", "showcontent", self.show_content)
        store.set_bool("global", "sizeenabled", self.size_enabled)
        store.set("global", "sizevalue", str(self.size_value))
        store.set("global", "sizecmp", self.size_cmp)
        store.set("global", "datelimitmode", self.date_limit_mode)
        store.set("global", "date1", self.date1)
        store.set("global", "date2", self.date2)

    def to_search_options(self, replace_enabled: bool) -> SearchOptions:
        return SearchOptions(
            search_path=self.search_path,
            search_string=self.search_string,
            replace_string=self.replace_string if replace_enabled else "",
            use_regex=self.use_regex,
            case_sensitive=self.case_sensitive,
            dot_matches_newline=self.dot_matches_newline,
            whole_words=self.whole_words,
            include_subfolders=self.include_subfolders,
            include_hidden=self.include_hidden,
            include_system=self.include_system,
            include_sym_links=self.include_sym_links,
            include_binary=self.include_binary,
            create_backup=self.create_backup,
            keep_file_date=self.keep_file_date,
            file_match=self.file_match,
            file_match_regex=self.file_match_regex,
            exclude_dirs=self.exclude_dirs,
            force_binary=self.binary,
            prefer_utf8=self.utf8,
            size_enabled=self.size_enabled,
            size_value=self.size_value,
            size_cmp=self.size_cmp,
            date_limit_mode=self.date_limit_mode,
            date1=self.date1,
            date2=self.date2,
        )
