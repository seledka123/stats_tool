# stats-tool

[🇷🇺 Русский](README.md) | 🇬🇧 English

A Python console program that computes the **arithmetic mean, median and mode** of a numeric sample, with console or file input/output, plus backup and restore of statistics dumps.

Dependencies: standard library only, **Python 3.9+**.

## Installation

```bash
git clone https://github.com/<your-account>/stats-tool.git
cd stats-tool
```

## Usage

### Calculation

```bash
# from arguments
python -m stats_tool calc 3 1 4 1 5 9 2 6 5 3 5

# interactive prompt or stdin
python -m stats_tool calc
echo "1 2 2 3" | python -m stats_tool calc

# file to file, JSON format
python -m stats_tool calc -i sample.txt -o result.json -f json

# save the result as a dump
python -m stats_tool calc -i sample.txt --save-dump
```

Sample format: numbers separated by spaces, newlines, `,` or `;`. The decimal mark is a dot (`2.5`).

Rules: for an even count the median is the mean of the two middle values; several modes are all printed; if all values are unique (and there is more than one), the mode is reported as none.

### Backup and restore

```bash
python -m stats_tool backup [--keep 5]            # back up dumps
python -m stats_tool list                         # list backups
python -m stats_tool restore [--archive FILE]     # restore (latest by default)
```

Dumps live in `data/dumps`, backups in `data/backups` (override with `--dump-dir`, `--backup-dir`). The archive is verified by SHA-256 before restoring; current dumps are kept in `data/dumps.pre_restore`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | data error (empty sample, not a number) |
| 2 | invalid command-line arguments |
| 3 | file / backup error |

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

## Documentation (Russian)

- [Technical specification](docs/TZ.md)
- [Test cases](docs/TEST_CASES.md)
- [Maintenance regulations](docs/MAINTENANCE.md)
