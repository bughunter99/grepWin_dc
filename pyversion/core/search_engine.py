from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import fnmatch
import os
import re
import shutil
import tempfile
from typing import Callable

from core.regex_replace_formatter import RegexReplaceFormatter
from core.search_info import SearchInfo


@dataclass
class SearchOptions:
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

    file_match: str = ""
    file_match_regex: bool = False
    exclude_dirs: str = ""

    force_binary: bool = False
    prefer_utf8: bool = False

    create_backup: bool = False
    keep_file_date: bool = False

    size_enabled: bool = False
    size_value: int = 0
    size_cmp: str = "lt"

    date_limit_mode: str = "all"
    date1: str = ""
    date2: str = ""


@dataclass
class SearchProgress:
    scanned_files: int = 0
    matched_files: int = 0
    current_path: str = ""


class SearchEngine:
    STREAM_THRESHOLD_BYTES = 4 * 1024 * 1024

    def __init__(self) -> None:
        self.cancelled = False

    def search_thread(
        self,
        options: SearchOptions,
        on_result: Callable[[SearchInfo], None],
        on_progress: Callable[[SearchProgress], None] | None = None,
    ) -> list[SearchInfo]:
        results: list[SearchInfo] = []
        scanned_files = 0
        matched_files = 0

        roots = [p.strip() for p in options.search_path.split("|") if p.strip()]
        if not roots:
            return results

        exclude_dir_expr = self._compile_exclude_dirs(options.exclude_dirs)

        for root in roots:
            if self.cancelled:
                return results
            root_path = Path(root)
            if not root_path.exists():
                continue

            if root_path.is_file():
                root_stat = self._safe_stat(root_path)
                if root_stat is None or not self._passes_file_filters(root_path, root_stat, options):
                    if on_progress:
                        scanned_files += 1
                        on_progress(SearchProgress(scanned_files=scanned_files, matched_files=matched_files, current_path=str(root_path)))
                    continue
                info = self.search_file(root_path, options)
                if info.match_count > 0 or info.read_error or info.exception:
                    matched_files += 1
                    self.send_result(info, on_result, results)
                if on_progress:
                    scanned_files += 1
                    on_progress(SearchProgress(scanned_files=scanned_files, matched_files=matched_files, current_path=str(root_path)))
                continue

            walker = os.walk(root_path)
            for current, dirs, files in walker:
                if self.cancelled:
                    return results

                if not options.include_subfolders:
                    dirs[:] = []

                if not options.include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files = [f for f in files if not f.startswith(".")]

                if exclude_dir_expr is not None:
                    dirs[:] = [d for d in dirs if not exclude_dir_expr.search(d)]

                files = [f for f in files if self._match_path(f, options)]

                for name in files:
                    if self.cancelled:
                        return results
                    file_path = Path(current) / name
                    file_stat = self._safe_stat(file_path)
                    if file_stat is None or not self._passes_file_filters(file_path, file_stat, options):
                        if on_progress:
                            scanned_files += 1
                            on_progress(SearchProgress(scanned_files=scanned_files, matched_files=matched_files, current_path=str(file_path)))
                        continue
                    info = self.search_file(file_path, options)
                    if info.match_count > 0 or info.read_error or info.exception:
                        matched_files += 1
                        self.send_result(info, on_result, results)
                    if on_progress:
                        scanned_files += 1
                        on_progress(SearchProgress(scanned_files=scanned_files, matched_files=matched_files, current_path=str(file_path)))

        return results

    def search_file(self, file_path: Path, options: SearchOptions) -> SearchInfo:
        info = SearchInfo(file_path=str(file_path))
        try:
            stat = file_path.stat()
            info.file_size = stat.st_size
        except OSError as ex:
            info.read_error = True
            info.exception = str(ex)
            return info

        if self.cancelled:
            return info

        # Large files in non-regex/non-replace mode use a streaming path to reduce memory usage.
        if self._should_stream_text_search(info.file_size, options):
            return self.search_on_stream_lines(info, file_path, options)

        try:
            raw = file_path.read_bytes()
        except Exception as ex:
            info.read_error = True
            info.exception = str(ex)
            return info

        is_binary = self._is_binary_blob(raw)
        if (is_binary or options.force_binary) and not options.include_binary:
            return info

        if is_binary or options.force_binary:
            return self.search_by_file_path(info, raw, options)

        text = self._decode_text(raw, options)
        if text is None:
            if options.include_binary:
                return self.search_by_file_path(info, raw, options)
            return info
        return self.search_on_text_file(info, text, options)

    def search_on_text_file(self, info: SearchInfo, text: str, options: SearchOptions) -> SearchInfo:
        if not options.search_string:
            return info

        try:
            compiled = self._compile_search_regex(options)
        except re.error as ex:
            info.exception = f"regex error: {ex}"
            return info

        line_starts = [0]
        for idx, ch in enumerate(text):
            if ch == "\n":
                line_starts.append(idx + 1)

        for match in compiled.finditer(text):
            if self.cancelled:
                return info
            start = match.start()
            line_no = self._line_from_position(line_starts, start)
            col_no = start - line_starts[line_no - 1] + 1

            info.match_count += 1
            info.match_lines_numbers.append(line_no)
            info.match_columns_numbers.append(col_no)
            info.match_lengths.append(max(1, match.end() - match.start()))

            if line_no not in info.match_lines_map:
                line_text = self._line_text(text, line_starts, line_no)
                info.match_lines_map[line_no] = line_text

        if options.replace_string and info.match_count > 0:
            formatter = RegexReplaceFormatter(options.replace_string)
            formatter.set_replace_pair("${filepath}", info.file_path)
            file_name = Path(info.file_path).name
            formatter.set_replace_pair("${filename}", Path(file_name).stem)
            formatter.set_replace_pair("${fileext}", Path(file_name).suffix.lstrip("."))
            replaced = compiled.sub(lambda m: formatter.apply(m), text)
            if replaced != text:
                target = Path(info.file_path)
                if options.create_backup:
                    shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
                orig_times: tuple[float, float] | None = None
                if options.keep_file_date:
                    st = target.stat()
                    orig_times = (st.st_atime, st.st_mtime)
                target.write_text(replaced, encoding="utf-8")
                if orig_times is not None:
                    os.utime(target, orig_times)

        return info

    def search_on_stream_lines(self, info: SearchInfo, file_path: Path, options: SearchOptions) -> SearchInfo:
        if not options.search_string:
            return info

        try:
            compiled = self._compile_search_regex(options)
        except re.error as ex:
            info.exception = f"regex error: {ex}"
            return info

        for encoding, text_stream in self._iter_text_streams(file_path, options):
            temp_file = None
            temp_path = None
            formatter = None
            replaced_any = False
            try:
                if options.replace_string:
                    formatter = RegexReplaceFormatter(options.replace_string)
                    formatter.set_replace_pair("${filepath}", info.file_path)
                    file_name = Path(info.file_path).name
                    formatter.set_replace_pair("${filename}", Path(file_name).stem)
                    formatter.set_replace_pair("${fileext}", Path(file_name).suffix.lstrip("."))
                    fd, temp_name = tempfile.mkstemp(
                        dir=file_path.parent,
                        prefix=file_path.name + ".",
                        suffix=".grepwinreplaced",
                    )
                    os.close(fd)
                    temp_path = Path(temp_name)
                    temp_file = temp_path.open("w", encoding=encoding, newline="")

                line_no = 0
                for raw_line in text_stream:
                    if self.cancelled:
                        if temp_file is not None:
                            temp_file.close()
                            temp_file = None
                        if temp_path is not None and temp_path.exists():
                            temp_path.unlink(missing_ok=True)
                        return info

                    line_no += 1
                    line = raw_line.rstrip("\r\n")
                    line_ending = raw_line[len(line) :]
                    matches = list(compiled.finditer(line))
                    if not matches:
                        if temp_file is not None:
                            temp_file.write(raw_line)
                        continue

                    info.match_lines_map.setdefault(line_no, line)
                    for match in matches:
                        info.match_count += 1
                        info.match_lines_numbers.append(line_no)
                        info.match_columns_numbers.append(match.start() + 1)
                        info.match_lengths.append(max(1, match.end() - match.start()))

                    if temp_file is not None and formatter is not None:
                        replaced_line = compiled.sub(lambda m: formatter.apply(m), line)
                        temp_file.write(replaced_line + line_ending)
                        replaced_any = replaced_any or (replaced_line != line)

                if temp_file is not None:
                    temp_file.close()
                    temp_file = None
                    text_stream.close()
                    if self.cancelled:
                        if temp_path is not None and temp_path.exists():
                            temp_path.unlink(missing_ok=True)
                        return info
                    if replaced_any and temp_path is not None:
                        if options.create_backup:
                            shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))
                        orig_times: tuple[float, float] | None = None
                        if options.keep_file_date:
                            st = file_path.stat()
                            orig_times = (st.st_atime, st.st_mtime)
                        os.replace(temp_path, file_path)
                        if orig_times is not None:
                            os.utime(file_path, orig_times)
                    elif temp_path is not None and temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                else:
                    text_stream.close()
                return info
            except UnicodeDecodeError:
                if temp_file is not None:
                    temp_file.close()
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                continue
            except Exception as ex:
                if temp_file is not None:
                    temp_file.close()
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                info.read_error = True
                info.exception = str(ex)
                return info

        info.read_error = True
        info.exception = "unable to decode file for streaming search"
        return info

    def search_by_file_path(self, info: SearchInfo, raw: bytes, options: SearchOptions) -> SearchInfo:
        # Keep a fast raw-data path for binary-like content where text decoding is unreliable.
        text = raw.decode("latin-1", errors="ignore")
        return self.search_on_text_file(info, text, options)

    def send_result(
        self,
        info: SearchInfo,
        on_result: Callable[[SearchInfo], None],
        sink: list[SearchInfo],
    ) -> None:
        sink.append(info)
        on_result(info)

    @staticmethod
    def _line_from_position(line_starts: list[int], pos: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if line_starts[mid] <= pos:
                lo = mid + 1
            else:
                hi = mid - 1
        return hi + 1

    @staticmethod
    def _line_text(text: str, line_starts: list[int], line_no: int) -> str:
        start = line_starts[line_no - 1]
        if line_no < len(line_starts):
            end = line_starts[line_no] - 1
        else:
            end = len(text)
        return text[start:end].rstrip("\r\n")

    @staticmethod
    def _is_binary_blob(raw: bytes) -> bool:
        if not raw:
            return False
        sample = raw[:8192]
        return b"\x00" in sample

    @staticmethod
    def _decode_text(raw: bytes, options: SearchOptions) -> str | None:
        encodings: list[str]
        if options.prefer_utf8:
            encodings = ["utf-8", "utf-16-le", "utf-16-be", "cp1252"]
        else:
            encodings = ["utf-8", "cp1252", "utf-16-le", "utf-16-be"]

        for encoding in encodings:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None

    @staticmethod
    def _compile_exclude_dirs(expr: str) -> re.Pattern[str] | None:
        value = expr.strip()
        if not value:
            return None
        try:
            return re.compile(value, re.IGNORECASE)
        except re.error:
            escaped = re.escape(value).replace(r"\|", "|")
            return re.compile(escaped, re.IGNORECASE)

    @staticmethod
    def _match_path(file_name: str, options: SearchOptions) -> bool:
        rule = options.file_match.strip()
        if not rule:
            return True

        if options.file_match_regex:
            try:
                return re.search(rule, file_name, flags=re.IGNORECASE) is not None
            except re.error:
                return False

        patterns = [part.strip() for part in rule.split(";") if part.strip()]
        if not patterns:
            return True

        include = [p for p in patterns if not p.startswith("-")]
        exclude = [p[1:] for p in patterns if p.startswith("-") and len(p) > 1]

        included = True if not include else any(fnmatch.fnmatch(file_name.lower(), p.lower()) for p in include)
        excluded = any(fnmatch.fnmatch(file_name.lower(), p.lower()) for p in exclude)
        return included and not excluded

    @staticmethod
    def _safe_stat(file_path: Path) -> os.stat_result | None:
        try:
            return file_path.stat()
        except OSError:
            return None

    def _passes_file_filters(self, file_path: Path, stat_result: os.stat_result, options: SearchOptions) -> bool:
        if not options.include_sym_links and file_path.is_symlink():
            return False

        if not options.include_hidden and self._is_hidden_entry(file_path, stat_result):
            return False

        if not options.include_system and self._is_system_entry(stat_result):
            return False

        if options.size_enabled:
            if not self._passes_size_filter(stat_result.st_size, options.size_cmp, options.size_value):
                return False

        if not self._passes_date_filter(stat_result.st_mtime, options.date_limit_mode, options.date1, options.date2):
            return False

        return True

    @staticmethod
    def _is_hidden_entry(file_path: Path, stat_result: os.stat_result) -> bool:
        if file_path.name.startswith("."):
            return True
        attrs = getattr(stat_result, "st_file_attributes", 0)
        # FILE_ATTRIBUTE_HIDDEN = 0x2
        return bool(attrs & 0x2)

    @staticmethod
    def _is_system_entry(stat_result: os.stat_result) -> bool:
        attrs = getattr(stat_result, "st_file_attributes", 0)
        # FILE_ATTRIBUTE_SYSTEM = 0x4
        return bool(attrs & 0x4)

    @staticmethod
    def _passes_size_filter(file_size: int, size_cmp: str, size_value: int) -> bool:
        if size_cmp == "eq":
            return file_size == size_value
        if size_cmp == "gt":
            return file_size > size_value
        return file_size < size_value

    def _passes_date_filter(self, mtime_epoch: float, mode: str, date1: str, date2: str) -> bool:
        if mode == "all":
            return True

        file_time = datetime.fromtimestamp(mtime_epoch)
        dt1 = self._parse_datetime(date1)
        dt2 = self._parse_datetime(date2)

        if mode == "newer":
            return dt1 is None or file_time >= dt1
        if mode == "older":
            return dt1 is None or file_time <= dt1
        if mode == "between":
            if dt1 is None or dt2 is None:
                return True
            return dt1 <= file_time <= dt2
        return True

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        raw = value.strip()
        if not raw:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _should_stream_text_search(self, file_size: int, options: SearchOptions) -> bool:
        if file_size < self.STREAM_THRESHOLD_BYTES:
            return False
        if options.use_regex:
            return False
        if options.dot_matches_newline:
            return False
        if options.force_binary:
            return False
        return True

    @staticmethod
    def _iter_text_streams(file_path: Path, options: SearchOptions):
        if options.prefer_utf8:
            encodings = ["utf-8", "cp1252", "utf-16-le", "utf-16-be"]
        else:
            encodings = ["cp1252", "utf-8", "utf-16-le", "utf-16-be"]

        for encoding in encodings:
            with file_path.open("r", encoding=encoding, errors="strict") as f:
                yield encoding, f

    @staticmethod
    def _compile_search_regex(options: SearchOptions) -> re.Pattern[str]:
        flags = 0
        if not options.case_sensitive:
            flags |= re.IGNORECASE
        if options.dot_matches_newline:
            flags |= re.DOTALL

        if options.use_regex:
            expr = options.search_string
        else:
            expr = re.escape(options.search_string)

        if options.whole_words:
            expr = rf"\b{expr}\b"

        return re.compile(expr, flags)

    @staticmethod
    def _find_literal_columns(line: str, needle: str, case_sensitive: bool, whole_words: bool) -> list[tuple[int, int]]:
        if not needle:
            return []

        if case_sensitive:
            haystack = line
            target = needle
        else:
            haystack = line.lower()
            target = needle.lower()

        result: list[tuple[int, int]] = []
        start = 0
        nlen = len(target)
        while True:
            pos = haystack.find(target, start)
            if pos < 0:
                break

            if whole_words and not SearchEngine._is_whole_word_match(line, pos, nlen):
                start = pos + 1
                continue

            # 1-based column to stay compatible with existing result model.
            result.append((pos + 1, nlen))
            start = pos + 1

        return result

    @staticmethod
    def _is_whole_word_match(line: str, pos: int, length: int) -> bool:
        left_ok = pos == 0 or not (line[pos - 1].isalnum() or line[pos - 1] == "_")
        right = pos + length
        right_ok = right >= len(line) or not (line[right].isalnum() or line[right] == "_")
        return left_ok and right_ok
