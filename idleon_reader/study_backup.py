"""Backup and restore helpers for study exports."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .study_config import StudyAccountProfile, StudyConfig


BACKUP_VERSION = 1


class StudyBackupError(RuntimeError):
    """Raised when backup or restore cannot be completed."""


@dataclass(frozen=True)
class BackupRecord:
    archive_path: Path
    created_at: str
    backup_reason: str
    account_label: str
    study_group: str
    session_id: str
    run_type: str
    snapshot_id: str
    size_bytes: int
    include_local_config: bool


@dataclass(frozen=True)
class RestoreResult:
    archive_path: Path
    output_dir: Path
    backup_record: BackupRecord


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _archive_timestamp(value: str) -> str:
    return value.replace(":", "-").replace("+00:00", "Z")


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise StudyBackupError(f"Ungueltiger relativer Pfad im Backup: {relative_path}")
    return path


def _backup_root_path(config: StudyConfig, *, create: bool = False) -> Path:
    path = Path(config.backup_root).expanduser().resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _iter_export_files(export_dir: Path) -> list[Path]:
    if not export_dir.exists():
        raise StudyBackupError(f"Exportordner existiert nicht: {export_dir}")
    if not export_dir.is_dir():
        raise StudyBackupError(f"Exportpfad ist kein Verzeichnis: {export_dir}")
    files = sorted(path for path in export_dir.rglob("*") if path.is_file())
    if not files:
        raise StudyBackupError(f"Exportordner ist leer: {export_dir}")
    return files


def _latest_snapshot_row(export_dir: Path) -> dict[str, str]:
    snapshots_csv = export_dir / "snapshots.csv"
    if not snapshots_csv.exists():
        raise StudyBackupError(f"Kein snapshots.csv im Exportordner gefunden: {export_dir}")
    with open(snapshots_csv, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise StudyBackupError(f"snapshots.csv ist leer: {snapshots_csv}")
    return rows[-1]


def _backup_manifest_from_record(
    *,
    created_at: str,
    backup_reason: str,
    account: StudyAccountProfile,
    study_group: str,
    session_id: str,
    run_type: str,
    snapshot_id: str,
    export_dir: Path,
    repo_root: Path,
    include_local_config: bool,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "backup_version": BACKUP_VERSION,
        "created_at": created_at,
        "backup_reason": backup_reason,
        "account_label": account.account_label,
        "study_group": study_group,
        "session_id": session_id,
        "run_type": run_type,
        "snapshot_id": snapshot_id,
        "export_subdir": account.export_subdir,
        "source_repo_root": str(repo_root),
        "git_commit": _git_commit(repo_root),
        "platform": platform.platform(),
        "include_local_config": include_local_config,
        "files": files,
    }


def _build_archive_entries(
    *,
    config: StudyConfig,
    account: StudyAccountProfile,
    export_dir: Path,
    include_local_config: bool,
    session_state_path: Optional[Path],
) -> list[tuple[Path, Path]]:
    entries: list[tuple[Path, Path]] = []
    for file_path in _iter_export_files(export_dir):
        relative = Path("exports") / account.export_subdir / file_path.relative_to(export_dir)
        entries.append((file_path, relative))

    entries.append((config.profiles_path, Path("config") / "study_profiles.toml"))

    if include_local_config and config.local_path.exists():
        entries.append((config.local_path, Path("config") / "study_local.toml"))

    if session_state_path is not None and session_state_path.exists():
        entries.append((session_state_path, Path("state") / "current_session.json"))

    return entries


def create_study_backup(
    *,
    config: StudyConfig,
    account: StudyAccountProfile,
    export_dir: Path,
    snapshot_id: str,
    run_type: str,
    study_group: str,
    session_id: str = "",
    backup_reason: str = "auto_post_export",
    include_local_config: Optional[bool] = None,
    session_state_path: Optional[Path] = None,
) -> BackupRecord:
    include_local = config.include_local_config_in_backup if include_local_config is None else include_local_config
    backup_root = _backup_root_path(config, create=True)
    created_at = _utc_now()
    year = created_at[:4]
    date_token = created_at[:10]
    archive_dir = backup_root / account.account_label / year / date_token
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_name = (
        f"{_archive_timestamp(created_at)}__{account.account_label}__{run_type or 'unknown'}__{snapshot_id or 'unknown'}.zip"
    )
    archive_path = archive_dir / archive_name
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".backup-", suffix=".zip", dir=archive_dir)
    Path(tmp_name).unlink(missing_ok=True)

    entries = _build_archive_entries(
        config=config,
        account=account,
        export_dir=export_dir,
        include_local_config=include_local,
        session_state_path=session_state_path,
    )
    file_entries: list[dict[str, Any]] = []
    temp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path, archive_relative_path in entries:
                data = file_path.read_bytes()
                archive.writestr(str(archive_relative_path), data)
                file_entries.append(
                    {
                        "relative_path": str(archive_relative_path),
                        "size_bytes": len(data),
                        "sha256": _sha256_bytes(data),
                    }
                )

            manifest = _backup_manifest_from_record(
                created_at=created_at,
                backup_reason=backup_reason,
                account=account,
                study_group=study_group,
                session_id=session_id,
                run_type=run_type,
                snapshot_id=snapshot_id,
                export_dir=export_dir,
                repo_root=config.repo_root,
                include_local_config=include_local,
                files=file_entries,
            )
            archive.writestr("backup_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        temp_path.replace(archive_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise StudyBackupError(f"Backup konnte nicht erstellt werden: {exc}") from exc

    return BackupRecord(
        archive_path=archive_path,
        created_at=created_at,
        backup_reason=backup_reason,
        account_label=account.account_label,
        study_group=study_group,
        session_id=session_id,
        run_type=run_type,
        snapshot_id=snapshot_id,
        size_bytes=archive_path.stat().st_size,
        include_local_config=include_local,
    )


def create_backup_from_latest_export(
    *,
    config: StudyConfig,
    account: StudyAccountProfile,
    export_dir: Path,
    include_local_config: Optional[bool] = None,
    session_state_path: Optional[Path] = None,
) -> BackupRecord:
    latest = _latest_snapshot_row(export_dir)
    return create_study_backup(
        config=config,
        account=account,
        export_dir=export_dir,
        snapshot_id=latest.get("snapshot_id", ""),
        run_type=latest.get("run_type", ""),
        study_group=latest.get("study_group", ""),
        session_id=latest.get("session_id", ""),
        backup_reason="manual_backup_now",
        include_local_config=include_local_config,
        session_state_path=session_state_path,
    )


def update_export_manifest_backup_status(manifest_path: Optional[Path], backup_status: dict[str, Any]) -> None:
    if manifest_path is None or not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["backup"] = backup_status
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _backup_record_from_manifest(archive_path: Path, manifest: dict[str, Any]) -> BackupRecord:
    return BackupRecord(
        archive_path=archive_path,
        created_at=str(manifest.get("created_at", "")),
        backup_reason=str(manifest.get("backup_reason", "")),
        account_label=str(manifest.get("account_label", "")),
        study_group=str(manifest.get("study_group", "")),
        session_id=str(manifest.get("session_id", "")),
        run_type=str(manifest.get("run_type", "")),
        snapshot_id=str(manifest.get("snapshot_id", "")),
        size_bytes=archive_path.stat().st_size,
        include_local_config=bool(manifest.get("include_local_config", False)),
    )


def _read_backup_manifest(archive_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest_bytes = archive.read("backup_manifest.json")
    except KeyError as exc:
        raise StudyBackupError(f"backup_manifest.json fehlt im Archiv: {archive_path}") from exc
    except zipfile.BadZipFile as exc:
        raise StudyBackupError(f"Ungueltiges ZIP-Archiv: {archive_path}") from exc
    return json.loads(manifest_bytes.decode("utf-8"))


def list_study_backups(config: StudyConfig, account_label: str = "") -> tuple[list[BackupRecord], list[str]]:
    backup_root = _backup_root_path(config, create=False)
    if not backup_root.exists():
        return [], []

    records: list[BackupRecord] = []
    warnings: list[str] = []
    for archive_path in sorted(backup_root.rglob("*.zip"), reverse=True):
        try:
            manifest = _read_backup_manifest(archive_path)
            record = _backup_record_from_manifest(archive_path, manifest)
            if account_label and record.account_label != account_label:
                continue
            records.append(record)
        except StudyBackupError as exc:
            warnings.append(str(exc))
    records.sort(key=lambda item: item.created_at, reverse=True)
    return records, warnings


def restore_study_backup(
    *,
    repo_root: Path,
    archive_path: Path,
    output_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> RestoreResult:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.exists():
        raise StudyBackupError(f"Backup-Archiv existiert nicht: {archive_path}")

    manifest = _read_backup_manifest(archive_path)
    record = _backup_record_from_manifest(archive_path, manifest)
    files = manifest.get("files")
    if not isinstance(files, list):
        raise StudyBackupError("backup_manifest.json enthaelt keine gueltige Dateiliste.")

    repo_root = repo_root.resolve()
    target_dir = output_dir if output_dir is not None else (repo_root / "restores" / archive_path.stem)
    if not target_dir.is_absolute():
        target_dir = (repo_root / target_dir).resolve()
    else:
        target_dir = target_dir.resolve()

    if target_dir.exists():
        if not overwrite:
            if any(target_dir.iterdir()):
                raise StudyBackupError(f"Restore-Ziel ist nicht leer: {target_dir}")
            target_dir.rmdir()
        else:
            if target_dir.is_dir():
                pass
            else:
                raise StudyBackupError(f"Restore-Ziel ist kein Verzeichnis: {target_dir}")

    target_parent = target_dir.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".restore-{archive_path.stem}-", dir=target_parent))

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest_bytes = archive.read("backup_manifest.json")
            (temp_dir / "backup_manifest.json").write_bytes(manifest_bytes)

            for file_entry in files:
                if not isinstance(file_entry, dict):
                    raise StudyBackupError("backup_manifest.json enthaelt einen ungueltigen Dateieintrag.")
                relative_path = _safe_relative_path(str(file_entry.get("relative_path", "")))
                expected_sha = str(file_entry.get("sha256", ""))
                expected_size = int(file_entry.get("size_bytes", -1))
                try:
                    data = archive.read(str(relative_path))
                except KeyError as exc:
                    raise StudyBackupError(f"Datei fehlt im Archiv: {relative_path}") from exc
                if len(data) != expected_size:
                    raise StudyBackupError(f"Groesse stimmt nicht fuer {relative_path}.")
                if _sha256_bytes(data) != expected_sha:
                    raise StudyBackupError(f"Pruefsumme stimmt nicht fuer {relative_path}.")
                destination = temp_dir / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)

        if target_dir.exists():
            shutil.rmtree(target_dir)
        temp_dir.replace(target_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    return RestoreResult(
        archive_path=archive_path,
        output_dir=target_dir,
        backup_record=record,
    )
