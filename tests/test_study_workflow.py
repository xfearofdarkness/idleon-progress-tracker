from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from idleon_reader.study_config import (
    StudyConfigError,
    ensure_example_files,
    load_study_config,
)
from idleon_reader.study_session import (
    StudySessionError,
    baseline_export,
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


def _write_study_files(root: Path, save_path: Path, save_account: str = ""):
    save_account_line = f'save_account = "{save_account}"\n' if save_account else ""
    (root / "study_profiles.toml").write_text(
        """[study]
default_export_root = "exports/study"
default_study_group = "main"
allowed_tags = ["baseline", "session_start", "session_end", "reached_level_10"]
allowed_milestone_tags = ["reached_level_10"]
allowed_run_types = ["baseline", "checkpoint", "session_end", "milestone"]

[accounts.A_speed]
account_label = "A_speed"
strategy_label = "speed"
export_subdir = "A_speed"

[accounts.B_skills]
account_label = "B_skills"
strategy_label = "skills"
export_subdir = "B_skills"
""",
        encoding="utf-8",
    )
    (root / "study_local.toml").write_text(
        f"""[local]
default_account = "A_speed"

[accounts.A_speed]
save_path = "{save_path.as_posix()}"
{save_account_line}""",
        encoding="utf-8",
    )


def test_load_study_config_and_examples(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save, save_account="save_a")

    config = load_study_config(tmp_path)
    assert config.default_account == "A_speed"
    assert config.accounts["A_speed"].save_path == fake_save.as_posix()
    assert config.accounts["A_speed"].save_account == "save_a"

    created = ensure_example_files(tmp_path)
    assert "study_profiles.toml.example" in created
    assert "study_local.toml.example" in created


def test_load_study_config_rejects_unknown_default(tmp_path):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    (tmp_path / "study_local.toml").write_text(
        """[local]
default_account = "missing"
""",
        encoding="utf-8",
    )

    with pytest.raises(StudyConfigError):
        load_study_config(tmp_path)


def test_next_session_id_reads_existing_snapshots(tmp_path):
    export_dir = tmp_path / "exports" / "study" / "A_speed"
    export_dir.mkdir(parents=True)
    (export_dir / "snapshots.csv").write_text(
        "snapshot_id,timestamp,source_path,account_label,study_group,session_id,run_type,strategy_label,notes,playtime_minutes_since_last_snapshot,schema_version,exporter_version,git_commit,platform\n"
        "1,2026-04-09T10:00:00Z,/tmp,A_speed,main,A_speed-20260409-s01,checkpoint,speed,,,2,1.0.0,,macOS\n"
        "2,2026-04-09T11:00:00Z,/tmp,A_speed,main,A_speed-20260409-s02,checkpoint,speed,,,2,1.0.0,,macOS\n",
        encoding="utf-8",
    )

    session_id = next_session_id("A_speed", export_dir, now=datetime(2026, 4, 9, 12, 0, 0))
    assert session_id == "A_speed-20260409-s03"


def test_baseline_export_writes_without_session_state(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    result = baseline_export(config, account_name="A_speed", tags=["baseline"], notes="baseline run")
    assert result.study_metadata["run_type"] == "baseline"
    assert load_session_state(tmp_path) is None
    assert (tmp_path / "exports" / "study" / "A_speed" / "snapshots.csv").exists()


def test_session_start_checkpoint_and_end_manage_state(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    start_result, start_state = session_start(
        config,
        account_name="A_speed",
        tags=[],
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    assert start_result.study_metadata["session_id"] == "A_speed-20260409-s01"
    assert load_session_state(tmp_path).session_id == start_state.session_id

    checkpoint_result, checkpoint_state = checkpoint_export(
        config,
        notes="mid session",
        playtime_minutes=20,
        tags=[],
    )
    assert checkpoint_result.append is True
    assert checkpoint_result.study_metadata["session_id"] == start_state.session_id
    assert checkpoint_state.last_snapshot_id == checkpoint_result.snapshot_id

    end_result, end_state = session_end(
        config,
        notes="finished",
        playtime_minutes=45,
        tags=[],
    )
    assert end_result.study_metadata["run_type"] == "session_end"
    assert end_state.session_id == start_state.session_id
    assert load_session_state(tmp_path) is None

    with open(tmp_path / "exports" / "study" / "A_speed" / "snapshots.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["session_id"] for row in rows if row["run_type"] != "baseline"] == [
        start_state.session_id,
        start_state.session_id,
        start_state.session_id,
    ]


def test_milestone_requires_allowed_tag(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())

    session_start(
        config,
        account_name="A_speed",
        tags=[],
        now=datetime(2026, 4, 9, 9, 0, 0),
    )

    with pytest.raises(StudySessionError):
        milestone_export(config, tags=["unknown_tag"])


def test_study_status_reports_active_and_inactive(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)
    clear_session_state(tmp_path)

    inactive = study_status(config)
    assert inactive.active is False

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_save_data())
    session_start(
        config,
        account_name="A_speed",
        tags=[],
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    active = study_status(config)
    assert active.active is True
    assert active.state.account_label == "A_speed"


def test_baseline_export_can_select_specific_save_account(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save, save_account="save_b")
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_multi_save_data())

    baseline_export(config, account_name="A_speed", tags=["baseline"])

    with open(tmp_path / "exports" / "study" / "A_speed" / "characters.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["char_name"] == "Beta"


def test_session_state_persists_selected_save_account(tmp_path, monkeypatch):
    fake_save = tmp_path / "fake-save"
    fake_save.mkdir()
    _write_study_files(tmp_path, fake_save)
    config = load_study_config(tmp_path)

    monkeypatch.setattr("idleon_reader.study_session.read_save_data", lambda _path: _sample_multi_save_data())

    start_result, start_state = session_start(
        config,
        account_name="A_speed",
        save_account_override="save_b",
        tags=[],
        now=datetime(2026, 4, 9, 9, 0, 0),
    )
    assert start_result.study_metadata["session_id"] == "A_speed-20260409-s01"
    assert start_state.save_account == "save_b"
    assert load_session_state(tmp_path).save_account == "save_b"

    checkpoint_result, checkpoint_state = checkpoint_export(
        config,
        notes="mid session",
        playtime_minutes=20,
        tags=[],
    )
    assert checkpoint_result.study_metadata["session_id"] == start_state.session_id
    assert checkpoint_state.save_account == "save_b"

    with open(tmp_path / "exports" / "study" / "A_speed" / "characters.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["char_name"] for row in rows} == {"Beta"}
