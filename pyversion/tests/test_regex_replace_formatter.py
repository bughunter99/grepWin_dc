from __future__ import annotations

import re

from core.regex_replace_formatter import RegexReplaceFormatter


def test_count_replacer_default_sequence() -> None:
    formatter = RegexReplaceFormatter("item-${count}")
    pattern = re.compile(r"x")
    text = "xxx"

    replaced = pattern.sub(lambda m: formatter.apply(m), text)

    assert replaced == "item-1item-2item-3"


def test_count_replacer_with_start_and_step_and_padding() -> None:
    formatter = RegexReplaceFormatter("${count03(5,2)}")
    pattern = re.compile(r"x")

    replaced = pattern.sub(lambda m: formatter.apply(m), "xx")

    assert replaced == "005007"


def test_builtin_path_variables() -> None:
    formatter = RegexReplaceFormatter("${filepath}|${filename}|${fileext}")
    formatter.set_replace_pair("${filepath}", "C:/tmp/file.txt")
    formatter.set_replace_pair("${filename}", "file")
    formatter.set_replace_pair("${fileext}", "txt")
    pattern = re.compile(r"x")

    replaced = pattern.sub(lambda m: formatter.apply(m), "x")

    assert replaced == "C:/tmp/file.txt|file|txt"
