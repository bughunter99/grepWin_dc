from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.search_state import SearchDialogState
from ui.search_window import SearchWindow


def _normalize_argv(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    for arg in argv:
        if arg.startswith("/") and len(arg) > 1:
            normalized.append("--" + arg[1:])
        else:
            normalized.append(arg)
    return normalized


def parse_startup_args(argv: list[str]) -> tuple[SearchDialogState, str | None]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--searchpath")
    parser.add_argument("--searchfor")
    parser.add_argument("--replacewith")
    parser.add_argument("--filemask")
    parser.add_argument("--filemaskregex")
    parser.add_argument("--direxcluderegex")
    parser.add_argument("--regex")
    parser.add_argument("--includesystem")
    parser.add_argument("--includesymlinks")
    parser.add_argument("--includebinary")
    parser.add_argument("--binary")
    parser.add_argument("--utf8")
    parser.add_argument("--size")
    parser.add_argument("--sizecmp")
    parser.add_argument("--datelimit")
    parser.add_argument("--datelimitmode")
    parser.add_argument("--date1")
    parser.add_argument("--date2")
    parser.add_argument("--content", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--executesearch", action="store_true")
    parser.add_argument("--executereplace", action="store_true")

    args, _ = parser.parse_known_args(_normalize_argv(argv))

    state = SearchDialogState()
    if args.searchpath:
        state.search_path = args.searchpath
    if args.searchfor:
        state.search_string = args.searchfor
    if args.replacewith:
        state.replace_string = args.replacewith
    if args.filemask:
        state.file_match = args.filemask
    if args.filemaskregex:
        state.file_match = args.filemaskregex
        state.file_match_regex = True
    if args.direxcluderegex:
        state.exclude_dirs = args.direxcluderegex
    if args.regex:
        state.use_regex = args.regex.lower() in {"1", "true", "yes"}
    elif args.searchfor:
        # Keep close to grepWin startup behavior where search text implies regex mode by default.
        state.use_regex = True

    state.show_content = bool(args.content)

    if args.includesystem:
        state.include_system = args.includesystem.lower() in {"1", "true", "yes"}
    if args.includesymlinks:
        state.include_sym_links = args.includesymlinks.lower() in {"1", "true", "yes"}
    if args.includebinary:
        state.include_binary = args.includebinary.lower() in {"1", "true", "yes"}
    if args.binary:
        state.binary = args.binary.lower() in {"1", "true", "yes"}
    if args.utf8:
        state.utf8 = args.utf8.lower() in {"1", "true", "yes"}

    if args.size is not None:
        try:
            state.size_value = int(args.size)
            state.size_enabled = True
        except ValueError:
            state.size_enabled = False
    if args.sizecmp:
        mapping = {"0": "lt", "1": "eq", "2": "gt", "lt": "lt", "eq": "eq", "gt": "gt"}
        state.size_cmp = mapping.get(args.sizecmp.lower(), "lt")

    if args.datelimitmode:
        state.date_limit_mode = args.datelimitmode.lower()
    elif args.datelimit is not None:
        date_mode_map = {"0": "all", "1": "newer", "2": "older", "3": "between"}
        state.date_limit_mode = date_mode_map.get(str(args.datelimit).lower(), "all")
    if args.date1:
        state.date1 = args.date1
    if args.date2:
        state.date2 = args.date2

    action: str | None = None
    if args.executereplace:
        action = "replace"
    elif args.execute or args.executesearch:
        action = "search"

    return state, action


def main(argv: list[str] | None = None) -> int:
    cli_args = argv if argv is not None else sys.argv[1:]
    startup_state, startup_action = parse_startup_args(cli_args)

    app = QApplication(sys.argv)
    app_dir = Path(__file__).resolve().parent
    window = SearchWindow(app_dir=app_dir)
    window.apply_startup_state(startup_state)
    window.show()

    if startup_action:
        window.execute_action(startup_action)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
