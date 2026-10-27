from __future__ import annotations

import math
import re
from collections import Counter
from typing import List

_SPLIT = re.compile(r"[\s,;]+")


class DataError(ValueError):


def parse_numbers(text: str) -> List[float]:
    tokens = [t for t in _SPLIT.split(text.strip()) if t]
    if not tokens:
        raise DataError("Выборка пуста / The sample is empty")
    numbers: List[float] = []
    for token in tokens:
        try:
            value = float(token)
        except ValueError:
            raise DataError(f"Не число / Not a number: {token!r}") from None
        if not math.isfinite(value):
            raise DataError(f"Недопустимое значение / Invalid value: {token!r}")
        numbers.append(value)
    return numbers


def mean(data: List[float]) -> float:
    if not data:
        raise DataError("Выборка пуста / The sample is empty")
    return math.fsum(data) / len(data)


def median(data: List[float]) -> float:
    if not data:
        raise DataError("Выборка пуста / The sample is empty")
    s = sorted(data)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def mode(data: List[float]) -> List[float]:
    if not data:
        raise DataError("Выборка пуста / The sample is empty")
    counts = Counter(data)
    top = max(counts.values())
    if top == 1 and len(data) > 1:
        return []
    return sorted(v for v, c in counts.items() if c == top)


def analyze(data: List[float]) -> dict:
    return {
        "count": len(data),
        "mean": mean(data),
        "median": median(data),
        "mode": mode(data),
    }


def fmt(value: float) -> str:
    return f"{value:.10g}"
