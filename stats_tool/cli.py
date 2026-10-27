from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .backup import (BackupError, create_backup, list_backups,
                     restore_backup, save_dump)
from .core import DataError, analyze, fmt, parse_numbers

EXIT_OK, EXIT_DATA, EXIT_IO = 0, 1, 3


def format_text(result: dict) -> str:
    modes = ", ".join(fmt(m) for m in result["mode"]) or "отсутствует / none"
    return (
        f"Количество / Count: {result['count']}\n"
        f"Среднее арифметическое / Mean: {fmt(result['mean'])}\n"
        f"Медиана / Median: {fmt(result['median'])}\n"
        f"Мода / Mode: {modes}\n"
    )


def _read_sample(args) -> str:
    if args.input:
        return Path(args.input).read_text(encoding="utf-8")
    if args.numbers:
        return " ".join(args.numbers)
    if sys.stdin.isatty():
        return input("Введите числа через пробел / Enter numbers: ")
    return sys.stdin.read()


def _cmd_calc(args) -> int:
    data = parse_numbers(_read_sample(args))
    result = analyze(data)
    if args.format == "json":
        out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    else:
        out = format_text(result)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    if args.save_dump:
        path = save_dump(result, data, Path(args.dump_dir))
        print(f"Дамп сохранён / Dump saved: {path}", file=sys.stderr)
    return EXIT_OK


def _cmd_backup(args) -> int:
    path = create_backup(Path(args.dump_dir), Path(args.backup_dir), keep=args.keep)
    print(f"Резервная копия создана / Backup created: {path}")
    return EXIT_OK


def _cmd_restore(args) -> int:
    if args.archive:
        archive = Path(args.archive)
    else:
        backups = list_backups(Path(args.backup_dir))
        if not backups:
            raise BackupError("Нет резервных копий / No backups found")
        archive = backups[-1]
    n = restore_backup(archive, Path(args.dump_dir))
    print(f"Восстановлено файлов / Files restored: {n} (из / from {archive})")
    return EXIT_OK


def _cmd_list(args) -> int:
    for p in list_backups(Path(args.backup_dir)):
        print(p)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stats-tool",
                                description="Median, mean and mode of a numeric sample.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--dump-dir", default="data/dumps")
        sp.add_argument("--backup-dir", default="data/backups")

    c = sub.add_parser("calc", help="calculate statistics")
    c.add_argument("numbers", nargs="*", help="numbers (or use --input / stdin)")
    c.add_argument("-i", "--input", help="input file")
    c.add_argument("-o", "--output", help="output file")
    c.add_argument("-f", "--format", choices=["text", "json"], default="text")
    c.add_argument("--save-dump", action="store_true", help="save result as dump")
    common(c)
    c.set_defaults(func=_cmd_calc)

    b = sub.add_parser("backup", help="back up dumps")
    b.add_argument("--keep", type=int, default=5, help="archives to keep")
    common(b)
    b.set_defaults(func=_cmd_backup)

    r = sub.add_parser("restore", help="restore dumps from a backup")
    r.add_argument("--archive", help="archive path (default: latest)")
    common(r)
    r.set_defaults(func=_cmd_restore)

    l = sub.add_parser("list", help="list backups")
    common(l)
    l.set_defaults(func=_cmd_list)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DataError as exc:
        print(f"Ошибка данных / Data error: {exc}", file=sys.stderr)
        return EXIT_DATA
    except (BackupError, OSError) as exc:
        print(f"Ошибка / Error: {exc}", file=sys.stderr)
        return EXIT_IO
