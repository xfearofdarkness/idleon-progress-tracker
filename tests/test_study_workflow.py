from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from idleon_reader.study_config import (
    StudyConfigError,
    ensure_example_files,
    load_study_config,
)
from idleon_reader.study_cli import cmd_init_config
from idleon_reader.study_session import (
    StudySessionError,
    baseline_export,
    backup_now,
    checkpoint_export,
    clear_session_state,
    load_session_state,
    milestone_export,
    next_session_id,
    session_end,
    session_start,
    study_status,
)


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


def _sample_multi_save_data():
    return {
        "save_a": {
            "Money": 111,
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
                    "InventoryOrder": ["EquipmentHats73"],
                    "ItemQuantity": [1],
                    "ItemMap": [{"rarity": "common"}],
                    "EquipmentOrder": [["EquipmentHats73"], ["Blank"], ["Blank"]],
                    "EquipmentQuantity": [[1], [0], [0]],
                    "EquipmentMap": [[{"defence": 1}], [{}], [{}]],
                    "QuestStatus": {"Scripticus2": [3]},
                    "QuestComplete": {"Scripticus2": 0},
                }
            },
        },
        "save_b": {
            "Money": 222,
            "PlayerDATABASE": {
                "Beta": {
                    "CharacterClass": 2,
                    "Lv0": [7, 1, 0],
                    "Exp0": [14.5, 10, 20],
                    "ExpReq0": [44.0, 15, 25],
                    "CurrentMap": 2,
                    "AFKtarget": "frogG",
                    "PlayerHP": 40.5,
                    "PlayerMP": 21,
                    "Money": 20,
                    "InventorySlotsOwned": 16,
                    "SkillLevels": [4, 6, 0, 0, 1],
                    "InventoryOrder": ["EquipmentShirts7"],
                    "ItemQuantity": [2],
                    "ItemMap": [{"rarity": "rare"}],
                    "EquipmentOrder": [["EquipmentShirts7"], ["Blank"], ["Blank"]],
                    "EquipmentQuantity": [[1], [0], [0]],
                    "EquipmentMap": [[{"defence": 2}], [{}], [{}]],
                    "QuestStatus": {"Scripticus2": [2]},
                    "QuestComplete": {"Scripticus2": 0},
                }
            },
        },
    }


def _write_study_files(
    root: Path,
    save_path: Path,
    save_account: str = "",
    include_local_config: bool = True,
    expected_character_names: tuple[str, ...] = (),
    expected_character_count: int = 0,
):
    (save_path / "000001.log").write_bytes(b"stub")
    save_account_line = f'save_selector = "{save_account}"\n' if save_account else ""
    backup_root = root.parent / f"{root.name}-backups"
    expected_names_line = ""
    if expected_character_names:
        expected_names_line = "expected_character_names = [" + ", ".join(f'"{name}"' for name in expected_character_names) + "]\n"
    expected_count_line = ""
    if expected_character_count:
        expected_count_line = f"expected_character_count = {expected_character_count}\n"
    (root / "study_profiles.toml").write_text(
        f"""[study]
default_export_root = "exports/study"
default_study_group = "main"
allowed_tags = ["baseline", "session_start", "session_end", "reached_level_10"]
allowed_milestone_tags = ["reached_level_10"]
allowed_run_types = ["baseline", "checkpoint", "session_end", "milestone"]

[accounts.speed_run]
account_label = "speed_run"
strategy_label = "speed"
export_subdir = "speed_run"
{expected_names_line}{expected_count_line}

[accounts.skill_focus]
account_label = "skill_focus"
strategy_label = "skills"
export_subdir = "skill_focus"
""",
        encoding="utf-8",
    )
    (root / "study_local.toml").write_text(
        f"""[local]
profile = "speed_run"
save_path = "{save_path.as_posix()}"
{save_account_line}
[backup]
root = "{backup_root.as_posix()}"
include_local_config = {"true" if include_local_config else "false"}
""",
        encoding="utf-8",
    )


def _write_advanced_local_file(root: Path, save_path: Path, save_account: str = ""):
    (save_path / "000001.log").write_bytes(b"stub")
    save_account_line = f'save_selector = "{save_account}"\n' if save_account else ""
    backup_root = root.parent / f"{root.name}-backups"
    (root / "study_local.toml").write_text(
        f"""[local]
profile = "speed_run"

[backup]
root = "{backup_root.as_posix()}"

[accounts.speed_run]
save_path = "{save_path.as_posix()}"
{save_account_line}""",
        encoding="utf-8",
    )


def test_load_study_config_and_examples(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save, save_account="save_a")

    config = load_study_config(tmp_path)
    assert config.default_profile == "speed_run"
    assert config.default_save_path == fake_save.as_posix()
    assert config.default_save_account == "save_a"
    assert config.include_local_config_in_backup is True
    assert config.accounts["speed_run"].save_path == ""
    assert config.accounts["speed_run"].save_account == ""
    assert config.accounts["speed_run"].expected_character_names == ()
    assert config.accounts["speed_run"].expected_character_count == 0

    created = ensure_example_files(tmp_path)
    assert "study_profiles.toml.example" in created
    assert "study_local.toml.example" in created


def test_init_config_bootstraps_active_files_from_examples(tmp_path, monkeypatch):
    monkeypatch.setattr("idleon_reader.study_cli.repo_root_from_path", lambda: tmp_path)

    exit_code = cmd_init_config(None)

    assert exit_code == 0
    assert (tmp_path / "study_profiles.toml").exists()
    assert (tmp_path / "study_local.toml").exists()
    config = load_study_config(tmp_path)
    assert "account_1" in config.accounts


def test_load_study_config_rejects_unknown_default(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    (tmp_path / "study_local.toml").write_text(
        """[local]
profile = "missing"
""",
        encoding="utf-8",
    )

    with pytest.raises(StudyConfigError):
        load_study_config(tmp_path)


def test_next_session_id_reads_existing_snapshots(tmp_path):
    export_dir = tmp_path / "exports" / "study" / "speed_run"
    export_dir.mkdir(parents=True)
    (export_dir / "snapshots.csv").write_text(
        "snapshot_id,timestamp,source_path,account_label,study_group,session_id,run_type,strategy_label,notes,playtime_minutes_since_last_snapshot,schema_version,exporter_version,git_commit,platform\n"
        "1,2026-04-09T10:00:00Z,/tmp,speed_run,main,speed_run-20260409-s01,checkpoint,speed,,,2,1.0.0,,macOS\n"
        "2,2026-04-09T11:00:00Z,/tmp,speed_run,main,speed_run-20260409-s02,checkpoint,speed,,,2,1.0.0,,macOS\n",
        encoding="utf-8",
    )

    session_id = next_session_id("speed_run", export_dir, now=datetime(2026, 4, 9, 12, 0, 0))
    assert session_id == "speed_run-20260409-s03"


def test_baseline_export_writes_without_session_state(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"], notes="baseline run")
    assert result.study_metadata["run_type"] == "baseline"
    assert result.backup["success"] is True
    assert load_session_state(tmp_path) is None
    assert (tmp_path / "exports" / "study" / "speed_run" / "snapshots.csv").exists()


def test_baseline_export_validates_expected_character_names(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(
        tmp_path,
        fake_save,
        expected_character_names=("Alpha",),
        expected_character_count=1,
    )
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"])

    assert result.study_metadata["account_label"] == "speed_run"


def test_baseline_export_rejects_missing_expected_character_names(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(
        tmp_path,
        fake_save,
        expected_character_names=("MissingAlpha",),
        expected_character_count=1,
    )
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    with pytest.raises(StudySessionError, match="Fehlend: MissingAlpha"):
        baseline_export(config, account_name="speed_run", tags=["baseline"])


def test_baseline_export_rejects_expected_character_count_shortfall(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(
        tmp_path,
        fake_save,
        expected_character_count=2,
    )
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    with pytest.raises(StudySessionError, match="Erwartet: mindestens 2, gefunden: 1"):
        baseline_export(config, account_name="speed_run", tags=["baseline"])


def test_load_study_config_rejects_expected_count_smaller_than_names(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(
        tmp_path,
        fake_save,
        expected_character_names=("Alpha", "Beta"),
        expected_character_count=1,
    )

    with pytest.raises(StudyConfigError, match="expected_character_count ist kleiner"):
        load_study_config(tmp_path)


def test_baseline_export_can_write_debug_json(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="speed_run", tags=["baseline"], debug_json=True)
    assert result.debug_json_path is not None
    assert result.debug_json_path.exists()


def test_baseline_export_defaults_to_append_on_existing_history(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    baseline_export(config, account_name="speed_run", tags=["baseline"], notes="first")
    result = baseline_export(config, account_name="speed_run", tags=["baseline"], notes="second")

    assert result.mode == "append"

    with open(tmp_path / "exports" / "study" / "speed_run" / "snapshots.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2


def test_session_start_checkpoint_and_end_manage_state(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    start_state = session_start(
        config,
        account_name="speed_run",
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    assert start_state.session_id == "speed_run-20260409-s01"
    assert load_session_state(tmp_path).session_id == start_state.session_id

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    end_result, end_state = session_end(
        config,
        notes="finished",
        tags=[],
    )
    assert end_result.study_metadata["run_type"] == "session_end"
    assert end_result.backup["success"] is True
    assert end_state.session_id == start_state.session_id
    assert load_session_state(tmp_path) is None

    with open(tmp_path / "exports" / "study" / "speed_run" / "snapshots.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["session_id"] for row in rows if row["run_type"] != "baseline"] == [start_state.session_id]


def test_milestone_requires_allowed_tag(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    session_start(
        config,
        account_name="speed_run",
        now=datetime(2026, 4, 9, 9, 0, 0),
    )

    with pytest.raises(StudySessionError, match="nicht mehr Teil des empfohlenen Workflows"):
        milestone_export(config, tags=["unknown_tag"])


def test_checkpoint_is_no_longer_supported(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    session_start(
        config,
        account_name="speed_run",
        now=datetime(2026, 4, 9, 9, 0, 0),
    )

    with pytest.raises(StudySessionError, match="checkpoint ist nicht mehr Teil des empfohlenen Workflows"):
        checkpoint_export(config)


def test_study_status_reports_active_and_inactive(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)
    clear_session_state(tmp_path)

    inactive = study_status(config)
    assert inactive.active is False

    session_start(
        config,
        account_name="speed_run",
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    active = study_status(config)
    assert active.active is True
    assert active.state.account_label == "speed_run"
    assert "session-end" in active.next_step


def test_baseline_export_can_select_specific_save_account(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save, save_account="save_b")
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_multi_save_data())

    baseline_export(config, account_name="speed_run", tags=["baseline"])

    with open(tmp_path / "exports" / "study" / "speed_run" / "characters.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["char_name"] == "Beta"


def test_session_state_persists_selected_save_account(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    start_state = session_start(
        config,
        account_name="speed_run",
        save_account_override="save_b",
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    assert start_state.session_id == "speed_run-20260409-s01"
    assert start_state.save_account == "save_b"
    assert load_session_state(tmp_path).save_account == "save_b"

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_multi_save_data())

    end_result, end_state = session_end(
        config,
        notes="end session",
        tags=[],
    )
    assert end_result.study_metadata["session_id"] == start_state.session_id
    assert end_state.save_account == "save_b"

    with open(tmp_path / "exports" / "study" / "speed_run" / "characters.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["char_name"] for row in rows} == {"Beta"}


def test_load_study_config_still_supports_profile_specific_overrides(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    _write_advanced_local_file(tmp_path, fake_save, save_account="save_b")

    config = load_study_config(tmp_path)

    assert config.default_profile == "speed_run"
    assert config.default_save_path == ""
    assert config.default_save_account == ""
    assert config.accounts["speed_run"].save_path == fake_save.as_posix()
    assert config.accounts["speed_run"].save_account == "save_b"


def test_backup_now_can_skip_local_config(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    baseline_export(config, account_name="speed_run", tags=["baseline"])
    record = backup_now(config, account_name="speed_run", include_local_config=False)

    with zipfile.ZipFile(record.archive_path, "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))

    assert "config/study_local.toml" not in names
    assert manifest["include_local_config"] is False
