from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class UnicodeType(str, Enum):
    AUTO = "auto"
    ANSI = "ansi"
    UTF8 = "utf8"
    UTF16_LE = "utf16_le"
    UTF16_BE = "utf16_be"
    BINARY = "binary"


@dataclass
class SearchInfo:
    file_path: str = ""
    file_size: int = 0
    search_pattern: str = ""

    match_lines_numbers: list[int] = field(default_factory=list)
    match_columns_numbers: list[int] = field(default_factory=list)
    match_lengths: list[int] = field(default_factory=list)
    match_lines_map: dict[int, str] = field(default_factory=dict)

    match_count: int = 0
    modified_time: datetime | None = None
    encoding: UnicodeType = UnicodeType.AUTO
    has_backed_up: bool = False
    read_error: bool = False
    folder: bool = False
    exception: str = ""
