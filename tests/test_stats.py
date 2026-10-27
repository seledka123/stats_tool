import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from stats_tool import cli
from stats_tool.backup import (BackupError, create_backup, list_backups,
                               restore_backup, save_dump)
from stats_tool.core import DataError, analyze, mean, median, mode, parse_numbers


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CoreTests(unittest.TestCase):
    def test_tc01_mean(self):
        self.assertAlmostEqual(mean([1, 2, 3, 4]), 2.5)

    def test_tc02_median_odd(self):
        self.assertEqual(median([5, 1, 3]), 3)

    def test_tc03_median_even(self):
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_tc04_mode_single(self):
        self.assertEqual(mode([1, 2, 2, 3]), [2])

    def test_tc05_mode_multi(self):
        self.assertEqual(mode([1, 1, 2, 2, 3]), [1, 2])

    def test_tc06_mode_none(self):
        self.assertEqual(mode([1, 2, 3]), [])

    def test_tc07_single_element(self):
        r = analyze([7])
        self.assertEqual((r["mean"], r["median"], r["mode"]), (7, 7, [7]))

    def test_tc08_negative_and_float(self):
        self.assertEqual(parse_numbers("-1.5; 2,3 4"), [-1.5, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(mean([-1.5, 1.5]), 0.0)

    def test_tc09_empty(self):
        for text in ("", "  \n "):
            with self.assertRaises(DataError):
                parse_numbers(text)

    def test_tc10_invalid_tokens(self):
        for text in ("1 a 3", "1 nan", "inf 2"):
            with self.assertRaises(DataError):
                parse_numbers(text)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tc11_console_args(self):
        code, out, _ = run_cli("calc", "1", "2", "2", "3")
        self.assertEqual(code, 0)
        self.assertIn("Медиана / Median: 2", out)
        self.assertIn("Мода / Mode: 2", out)

    def test_tc12_file_in_file_out(self):
        src, dst = self.dir / "in.txt", self.dir / "out.json"
        src.write_text("1 2 3\n4 5", encoding="utf-8")
        code, _, _ = run_cli("calc", "-i", str(src), "-o", str(dst), "-f", "json")
        self.assertEqual(code, 0)
        data = json.loads(dst.read_text(encoding="utf-8"))
        self.assertEqual((data["mean"], data["median"], data["count"]), (3, 3, 5))

    def test_tc13_bad_data_exit_code(self):
        code, _, err = run_cli("calc", "1", "x")
        self.assertEqual(code, 1)
        self.assertIn("x", err)

    def test_tc14_missing_input_file(self):
        code, _, _ = run_cli("calc", "-i", str(self.dir / "nope.txt"))
        self.assertEqual(code, 3)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dumps, self.backups = self.root / "dumps", self.root / "backups"
        t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        self.t0 = t0
        for i in range(3):
            d = [float(i), 2.0, 2.0]
            save_dump(analyze(d), d, self.dumps, now=t0 + dt.timedelta(seconds=i))

    def tearDown(self):
        self.tmp.cleanup()

    def test_tc15_backup_restore_roundtrip(self):
        archive = create_backup(self.dumps, self.backups)
        before = {p.name: p.read_bytes() for p in self.dumps.glob("*.json")}
        for p in self.dumps.glob("*.json"):
            p.unlink()
        self.assertEqual(restore_backup(archive, self.dumps), 3)
        after = {p.name: p.read_bytes() for p in self.dumps.glob("*.json")}
        self.assertEqual(before, after)

    def test_tc16_corrupted_archive_rejected(self):
        archive = create_backup(self.dumps, self.backups)
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(bad, "w") as dst:
            for n in src.namelist():
                blob = src.read(n)
                if n.startswith("dump_"):
                    blob += b" tampered"
                dst.writestr(n, blob)
        with self.assertRaises(BackupError):
            restore_backup(bad, self.dumps)
        self.assertEqual(len(list(self.dumps.glob("*.json"))), 3)

    def test_tc17_not_a_zip(self):
        junk = self.root / "junk.zip"
        junk.write_text("not a zip")
        with self.assertRaises(BackupError):
            restore_backup(junk, self.dumps)

    def test_tc18_rotation(self):
        for i in range(4):
            create_backup(self.dumps, self.backups, keep=2,
                          now=self.t0 + dt.timedelta(minutes=i))
        self.assertEqual(len(list_backups(self.backups)), 2)

    def test_tc19_no_dumps(self):
        with self.assertRaises(BackupError):
            create_backup(self.root / "empty", self.backups)

    def test_tc20_restore_keeps_safety_copy(self):
        archive = create_backup(self.dumps, self.backups)
        restore_backup(archive, self.dumps)
        self.assertTrue((self.root / "dumps.pre_restore").is_dir())

    def test_tc21_cli_flow(self):
        base = ["--dump-dir", str(self.root / "d2"), "--backup-dir", str(self.backups)]
        self.assertEqual(run_cli("calc", "1", "2", "--save-dump", *base)[0], 0)
        self.assertEqual(run_cli("backup", *base)[0], 0)
        self.assertEqual(run_cli("restore", *base)[0], 0)
        self.assertEqual(run_cli("restore", "--dump-dir", str(self.root / "d3"),
                                 "--backup-dir", str(self.root / "none"))[0], 3)


if __name__ == "__main__":
    unittest.main()
