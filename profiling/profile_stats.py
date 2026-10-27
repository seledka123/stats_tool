"""Измерение скорости и памяти stats-tool.

Запуск из корня проекта:
    python -m profiling.profile_stats timeit      [N]   # timeit: скорость функций
    python -m profiling.profile_stats cprofile    [N]   # cProfile: кто и сколько вызывался
    python -m profiling.profile_stats tracemalloc [N]   # tracemalloc: память и снимки
    python -m profiling.profile_stats all         [N]   # три предыдущих подряд
    python -m profiling.profile_stats loop        [сек] # нагрузка для py-spy

N — размер выборки (по умолчанию 200000).

Сторонние инструменты (pip install -r profiling/requirements-profiling.txt):
    kernprof -l -v profiling/profile_stats.py line      # line_profiler
    python -m memory_profiler profiling/profile_stats.py line   # memory_profiler
    py-spy record -o flame.svg -- python -m profiling.profile_stats loop 30
"""
from __future__ import annotations

import cProfile
import io
import math
import pstats
import random
import sys
import time
import timeit
import tracemalloc

try:  # kernprof (line_profiler) и memory_profiler подставляют profile сами
    profile  # type: ignore[name-defined]
except NameError:
    def profile(func):  # без профилировщика декоратор ничего не делает
        return func

try:
    from stats_tool.core import mean, median, mode, parse_numbers
except ImportError:  # запуск как скрипта: добавить корень проекта в путь
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from stats_tool.core import mean, median, mode, parse_numbers

DEFAULT_N = 200_000


def make_text(n: int, seed: int = 1) -> str:
    """Случайная выборка из n целых чисел в виде строки (как ввод пользователя)."""
    rnd = random.Random(seed)
    return " ".join(str(rnd.randint(0, 10_000)) for _ in range(n))


@profile
def workload(text: str):
    """Полный цикл программы; построчные профилировщики покажут каждую строку."""
    data = parse_numbers(text)
    avg = mean(data)
    med = median(data)
    mod = mode(data)
    return avg, med, mod


# ---------------------------------------------------------------- timeit
def run_timeit(n: int) -> None:
    text = make_text(n)
    data = parse_numbers(text)
    print(f"== timeit, выборка {n} значений (лучшее из 5 серий по 5 запусков) ==")
    cases = [
        ("parse_numbers", lambda: parse_numbers(text)),
        ("mean (fsum)", lambda: mean(data)),
        ("median", lambda: median(data)),
        ("mode", lambda: mode(data)),
    ]
    for name, fn in cases:
        best = min(timeit.repeat(fn, number=5, repeat=5)) / 5
        print(f"{name:<16}{best * 1000:10.2f} мс")
    t_fsum = min(timeit.repeat(lambda: math.fsum(data), number=20, repeat=5)) / 20
    t_sum = min(timeit.repeat(lambda: sum(data), number=20, repeat=5)) / 20
    print(f"\nСравнение: math.fsum {t_fsum * 1000:.2f} мс и sum {t_sum * 1000:.2f} мс "
          f"(fsum медленнее в {t_fsum / t_sum:.1f} раза, но точнее суммирует дроби)")


# -------------------------------------------------------------- cProfile
def run_cprofile(n: int) -> None:
    text = make_text(n)
    print(f"== cProfile, выборка {n} значений ==")
    pr = cProfile.Profile()
    pr.enable()
    workload(text)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).strip_dirs().sort_stats("cumulative").print_stats(8)
    print(buf.getvalue())


# ------------------------------------------------------------ tracemalloc
def run_tracemalloc(n: int) -> None:
    text = make_text(n)
    print(f"== tracemalloc, выборка {n} значений ==")
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    data = parse_numbers(text)          # данные живы -> видны в снимке
    after_parse = tracemalloc.take_snapshot()
    mean(data), median(data), mode(data)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Исходный текст: {len(text) / 1e6:.1f} МБ (создан до замера)")
    print(f"После разбора и расчёта: {current / 1e6:.1f} МБ, пик за всё время: {peak / 1e6:.1f} МБ")
    print("Топ-3 прироста по строкам кода (снимок после parse_numbers минус снимок до):")
    for stat in after_parse.compare_to(before, "lineno")[:3]:
        print(" ", stat)
    del data


# ------------------------------------------------------------------ py-spy
def run_loop(seconds: float) -> None:
    """Нагрузка для py-spy: многократно считает выборку, чтобы было что снимать."""
    text = make_text(DEFAULT_N)
    print(f"PID {__import__('os').getpid()}: нагрузка {seconds:.0f} с (подключите py-spy)")
    end = time.time() + seconds
    while time.time() < end:
        workload(text)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    what = args[0] if args else "all"
    arg = float(args[1]) if len(args) > 1 else None
    n = int(arg) if arg else DEFAULT_N
    if what in ("timeit", "all"):
        run_timeit(n)
    if what in ("cprofile", "all"):
        run_cprofile(n)
    if what in ("tracemalloc", "all"):
        run_tracemalloc(n)
    if what == "loop":
        run_loop(arg or 30)
    if what == "line":  # точка входа для kernprof / memory_profiler
        workload(make_text(n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
