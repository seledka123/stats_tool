from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional

MANIFEST = "manifest.json"


class BackupError(Exception):

def _now(now: Optional[dt.datetime]) -> dt.datetime:
    return now or dt.datetime.now(dt.timezone.utc)


def _stamp(now: dt.datetime) -> str:
    return now.strftime("%Y%m%d_%H%M%S_%f")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_dump(result: dict, data: List[float], dump_dir: Path,
              now: Optional[dt.datetime] = None) -> Path:
    now = _now(now)
    dump_dir = Path(dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": now.isoformat(), "data": data, **result}
    path = dump_dir / f"dump_{_stamp(now)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_backups(backup_dir: Path) -> List[Path]:
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("backup_*.zip"))


def create_backup(dump_dir: Path, backup_dir: Path, keep: int = 5,
                  now: Optional[dt.datetime] = None) -> Path:
    now = _now(now)
    dump_dir, backup_dir = Path(dump_dir), Path(backup_dir)
    files = sorted(dump_dir.glob("dump_*.json")) if dump_dir.is_dir() else []
    if not files:
        raise BackupError(f"Нет дампов для копирования / No dumps in {dump_dir}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    blobs = {f.name: f.read_bytes() for f in files}
    manifest = {
        "created_at": now.isoformat(),
        "files": {name: _sha256(b) for name, b in blobs.items()},
    }
    target = backup_dir / f"backup_{_stamp(now)}.zip"
    fd, tmp_name = tempfile.mkstemp(dir=backup_dir, suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, indent=2))
            for name, blob in blobs.items():
                zf.writestr(name, blob)
        os.replace(tmp_name, target)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    for old in list_backups(backup_dir)[:-keep] if keep > 0 else []:
        old.unlink()
    return target


def verify_archive(archive: Path) -> dict:
    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BackupError(f"Архив повреждён / Bad archive: {exc}") from None
    with zf:
        if MANIFEST not in zf.namelist():
            raise BackupError("Нет manifest.json / manifest.json missing")
        try:
            files = json.loads(zf.read(MANIFEST))["files"]
        except (KeyError, ValueError):
            raise BackupError("Некорректный manifest / Invalid manifest") from None
        extra = set(zf.namelist()) - set(files) - {MANIFEST}
        if extra:
            raise BackupError(f"Лишние файлы / Unexpected files: {sorted(extra)}")
        blobs = {}
        for name, digest in files.items():
            if name != Path(name).name or not name.startswith("dump_"):
                raise BackupError(f"Небезопасное имя / Unsafe name: {name!r}")
            try:
                blob = zf.read(name)
            except KeyError:
                raise BackupError(f"Файл отсутствует / Missing file: {name}") from None
            if _sha256(blob) != digest:
                raise BackupError(f"Контрольная сумма не совпала / Checksum mismatch: {name}")
            blobs[name] = blob
    return blobs


def restore_backup(archive: Path, dump_dir: Path) -> int:
    dump_dir = Path(dump_dir)
    blobs = verify_archive(Path(archive))
    dump_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=dump_dir.parent, prefix=".restore_"))
    safety = dump_dir.with_name(dump_dir.name + ".pre_restore")
    moved = False
    try:
        for name, blob in blobs.items():
            (tmp / name).write_bytes(blob)
        if dump_dir.exists():
            if safety.exists():
                shutil.rmtree(safety)
            os.replace(dump_dir, safety)
            moved = True
        os.replace(tmp, dump_dir)
    except Exception:
        if moved and not dump_dir.exists():
            os.replace(safety, dump_dir)
        shutil.rmtree(tmp, ignore_errors=True)
        raise BackupError("Не удалось восстановить / Restore failed") from None
    return len(blobs)
