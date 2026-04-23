from __future__ import annotations

import re
from dataclasses import dataclass


_COUNT_EXPR = re.compile(
    r"\$\{count(?P<leadzero>0)?(?P<length>\d+)?(?:\((?P<start>-?\d+)(?:,(?P<step>-?\d+))?\))?\}"
)


@dataclass
class NumberReplacer:
    expression: str
    lead_zero: bool = False
    padding: int = 0
    start: int = 1
    increment: int = 1


class RegexReplaceFormatter:
    def __init__(self, replace_string: str) -> None:
        self._replace_string = replace_string
        self._replace_map: dict[str, str] = {}
        self._numbers: list[NumberReplacer] = []

        for match in _COUNT_EXPR.finditer(replace_string):
            lead_zero = bool(match.group("leadzero"))
            padding = int(match.group("length")) if match.group("length") else 0
            start = int(match.group("start")) if match.group("start") else 1
            step = int(match.group("step")) if match.group("step") else 1
            if step == 0:
                step = 1
            self._numbers.append(
                NumberReplacer(
                    expression=match.group(0),
                    lead_zero=lead_zero,
                    padding=padding,
                    start=start,
                    increment=step,
                )
            )

    def set_replace_pair(self, source: str, target: str) -> None:
        self._replace_map[source] = target

    def apply(self, match: re.Match[str]) -> str:
        replaced = match.expand(self._replace_string)

        for src, dst in self._replace_map.items():
            replaced = replaced.replace(src, dst)

        for number_replacer in self._numbers:
            if number_replacer.expression not in replaced:
                continue

            if number_replacer.padding > 0:
                fill = "0" if number_replacer.lead_zero else " "
                value = f"{number_replacer.start:{fill}>{number_replacer.padding}d}"
            else:
                value = str(number_replacer.start)

            replaced = replaced.replace(number_replacer.expression, value, 1)
            number_replacer.start += number_replacer.increment

        return replaced
