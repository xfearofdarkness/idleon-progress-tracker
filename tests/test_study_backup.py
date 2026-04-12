from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from idleon_reader.study_backup import (
    StudyBackupError,
    create_study_backup,
    list_study_backups,
    restore_study_backup,
)
from idleon_reader.study_config import StudyConfigError, load_study_config
from idleon_reader.study_session import baseline_export, load_session_state, session_end, session_start


def _sample_save_data():
    return {
        "mySave": {
            "Money": 12345,
            "GemsOwned": 67,
            "Cards": [{"mushG": 1, "frogG": 0}, {"Copper": 2}],
            "StarSignsUnlocked": {"The_Book_Worm": "1", "Flexo_Bendo": "0"},
            "PlayerDATABASE": {
                "Alpha": {
                    "CharacterClass": 1,
                    "Lv0": [2, 1, 0],
                    "Exp0": [4.5, 10, 20],
                    "ExpReq0": [44.0, 15, 25],
                    "CurrentMap": 1,
                    "AFKtarget": "mushG",
                    "PlayerHP": 20.5,
                    "PlayerMP": 11,
                    "Money": 10,
                    "InventorySlotsOwned": 16,
                    "SkillLevels": [3, 5, 0, 0, 1],
                    "InventoryOrder": ["EquipmentHats73", "Blank", "LockedInvSpace"],
                    "ItemQuantity": [1, 0, 0],
                    "ItemMap": [{"rarity": "common"}, {}, {}],
                    "EquipmentOrder": [["EquipmentHats73", "Blank"], ["Blank"], ["Blank"]],
                    "EquipmentQuantity": [[1, 0], [0], [0]],
                    "EquipmentMap": [[{"defence": 1}, {}], [{}], [{}]],
                    "QuestStatus": {"Scripticus2": [3], "Secretkeeper1": [0]},
                    "QuestComplete": {"Scripticus2": 0, "Secretkeeper1": 1},
                }
            },
        }
    }


def _write_study_files(root: Path, save_path: Path, *, backup_root: Path, include_local_config: bool = True) -> None:
    (save_path / "000001.log").write_bytes(b"stub")
    (root / "study_profiles.toml").write_text(
        """[study]
default_export_root = "exports/study"
default_study_group = "main"
allowed_tags = ["baseline", "session_start", "session_end", "reached_level_10"]
allowed_milestone_tags = ["reached_level_10"]
allowed_run_types = ["baseline", "checkpoint", "session_end", "milestone"]

[accounts.speed_run]
account_label = "speed_run"
strategy_label = "speed"
export_subdir = "speed_run"
""",
        encoding="utf-8",
    )
    (root / "study_local.toml").write_text(
        f"""[local]
profile = "speed_run"
save_path = "{save_path.as_posix()}"

[backup]
root = "{backup_root.as_posix()}"
include_local_config = {"true" if include_local_config else "false"}
""",
        encoding="utf-8",
    )


def test_backup_root_inside_repo_is_rejected(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save, backup_root=tmp_path / "backups")

    with pytest.raises(StudyConfigError):
        load_study_config(tmp_path)


def test_automatic_backup_archive_contains_expected_files(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"])

    archive_path = Path(result.backup["archive_path"])
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        backup_manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))

    assert "exports/speed_run/snapshots.csv" in names
    assert f"exports/speed_run/run_manifests/{result.snapshot_id}.json" in names
    assert "config/study_profiles.toml" in names
    assert "config/study_local.toml" in names
    assert backup_manifest["account_label"] == "speed_run"
    assert backup_manifest["snapshot_id"] == result.snapshot_id


def test_backup_failure_marks_result_but_keeps_export(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    def fail_backup(**_kwargs):
        raise StudyBackupError("disk full")

    monkeypatch.setattr("idleon_reader.study_session.create_study_backup", fail_backup)

    result = baseline_export(config, account_name="speed_run", tags=["baseline"])
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.backup["success"] is False
    assert manifest["backup"]["success"] is False
    assert (tmp_path / "exports" / "study" / "speed_run" / "snapshots.csv").exists()


def test_list_backups_returns_created_archives(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    baseline_export(config, account_name="speed_run", tags=["baseline"])
    records, warnings = list_study_backups(config, account_label="speed_run")

    assert warnings == []
    assert len(records) == 1
    assert records[0].account_label == "speed_run"


def test_restore_backup_to_new_directory(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"])
    restore = restore_study_backup(
        repo_root=tmp_path,
        archive_path=Path(result.backup["archive_path"]),
        output_dir=tmp_path / "restores" / "baseline-restore",
    )

    assert (restore.output_dir / "backup_manifest.json").exists()
    assert (restore.output_dir / "exports" / "speed_run" / "snapshots.csv").exists()
    assert (restore.output_dir / "config" / "study_profiles.toml").exists()


def test_session_end_backup_excludes_current_session_file(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    session_start(
        config,
        account_name="speed_run",
        tags=[],
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    assert load_session_state(tmp_path) is not None

    end_result, _state = session_end(
        config,
        notes="done",
        playtime_minutes=10,
        tags=[],
    )

    with zipfile.ZipFile(Path(end_result.backup["archive_path"]), "r") as archive:
        names = set(archive.namelist())

    assert "state/current_session.json" not in names


def test_dry_run_does_not_create_backup(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"], dry_run=True)

    assert result.backup["attempted"] is False
    assert not backup_root.exists()


def test_create_study_backup_closes_mkstemp_fd(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    backup_root = tmp_path.parent / f"{tmp_path.name}-backups"
    _write_study_files(tmp_path, fake_save, backup_root=backup_root)
    config = load_study_config(tmp_path)
    export_dir = tmp_path / "exports" / "study" / "speed_run"
    export_dir.mkdir(parents=True)
    (export_dir / "snapshots.csv").write_text("snapshot_id,timestamp\nsnap-1,2026-04-12T00:00:00Z\n", encoding="utf-8")

    captured: dict[str, int] = {}
    real_mkstemp = tempfile.mkstemp

    def tracked_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        captured["fd"] = fd
        return fd, name

    monkeypatch.setattr("idleon_reader.study_backup.tempfile.mkstemp", tracked_mkstemp)

    record = create_study_backup(
        config=config,
        account=config.accounts["speed_run"],
        export_dir=export_dir,
        snapshot_id="snap-1",
        run_type="baseline",
        study_group="main",
    )

    with pytest.raises(OSError):
        os.fstat(captured["fd"])
    assert record.archive_path.exists()
