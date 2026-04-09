import csv

import pytest

from idleon_reader.export_tidy import (
    ALL_SKILL_IDS,
    R_SAFE_SKILL_NAMES,
    export_tidy_csvs,
    extract_tidy_account_metrics,
    extract_tidy_cards,
    extract_tidy_characters,
    extract_tidy_equipment,
    extract_tidy_inventory,
    extract_tidy_quests,
    extract_tidy_skills,
    extract_tidy_starsigns,
    make_snapshot_id,
)


@pytest.fixture
def sample_save_data():
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
                },
                "Bravo": {
                    "CharacterClass": 7,
                    "Lv0": [9, 2, 1],
                    "Exp0": [99.0, 50, 5],
                    "ExpReq0": [100.0, 75, 15],
                    "CurrentMap": 5,
                    "AFKtarget": "frogG",
                    "PlayerHP": 40,
                    "PlayerMP": 20,
                    "Money": 100,
                    "InventorySlotsOwned": 20,
                    "SkillLevels": [10, 2, 1, 0, 0],
                    "InventoryOrder": ["Blank", "Blank"],
                    "ItemQuantity": [0, 0],
                    "ItemMap": [{}, {}],
                    "EquipmentOrder": [["Blank"], ["Blank"], ["Blank"]],
                    "EquipmentQuantity": [[0], [0], [0]],
                    "EquipmentMap": [[{}], [{}], [{}]],
                    "QuestStatus": {"Scripticus2": [1]},
                    "QuestComplete": {"Scripticus2": -1},
                },
            },
        }
    }


def test_make_snapshot_id_is_deterministic():
    assert make_snapshot_id("2026-01-01T00:00:00Z", "a") == make_snapshot_id("2026-01-01T00:00:00Z", "a")


def test_r_safe_skill_names():
    assert R_SAFE_SKILL_NAMES[3] == "Choppin"
    assert all("'" not in name for name in R_SAFE_SKILL_NAMES.values())
    assert all(" " not in name for name in R_SAFE_SKILL_NAMES.values())


def test_extract_tidy_characters(sample_save_data):
    rows = extract_tidy_characters(sample_save_data, "snap")
    assert len(rows) == 2
    assert rows[0]["char_name"] == "Alpha"
    assert rows[0]["class_name"] == "Journeyman"
    assert rows[0]["level"] == 3
    assert rows[1]["class_name"] == "Blood Berserker"
    assert rows[1]["level"] == 10


def test_extract_tidy_skills(sample_save_data):
    rows = extract_tidy_skills(sample_save_data, "snap")
    assert len(rows) == 2 * len(ALL_SKILL_IDS)
    alpha_character = next(row for row in rows if row["char_name"] == "Alpha" and row["skill_id"] == 0)
    assert alpha_character["skill_level"] == 3
    assert alpha_character["skill_exp_current"] == 4.5


def test_extract_account_metrics(sample_save_data):
    rows = extract_tidy_account_metrics(sample_save_data, "snap")
    metrics = {row["metric_name"]: row["metric_value"] for row in rows}
    assert metrics["money"] == 12345
    assert metrics["gems"] == 67
    assert metrics["cards_total"] == 3
    assert metrics["cards_collected"] == 2
    assert metrics["character_count"] == 2
    assert metrics["starsigns_unlocked"] == 1


def test_extract_inventory(sample_save_data):
    rows = extract_tidy_inventory(sample_save_data, "snap")
    assert len(rows) == 5
    assert rows[0]["slot_state"] == "occupied"
    assert rows[1]["slot_state"] == "empty"
    assert rows[2]["slot_state"] == "locked"


def test_extract_equipment(sample_save_data):
    rows = extract_tidy_equipment(sample_save_data, "snap")
    occupied = next(row for row in rows if row["item_code"] == "EquipmentHats73")
    assert occupied["equipment_tab_index"] == 0
    assert occupied["slot_state"] == "occupied"


def test_extract_quests(sample_save_data):
    rows = extract_tidy_quests(sample_save_data, "snap")
    secret = next(row for row in rows if row["char_name"] == "Alpha" and row["quest_id"] == "Secretkeeper1")
    assert secret["quest_complete_code"] == 1
    assert secret["quest_is_complete"] == 1


def test_extract_cards(sample_save_data):
    rows = extract_tidy_cards(sample_save_data, "snap")
    assert len(rows) == 3
    assert {row["card_id"] for row in rows} == {"mushG", "frogG", "Copper"}


def test_extract_starsigns(sample_save_data):
    rows = extract_tidy_starsigns(sample_save_data, "snap")
    unlocked = next(row for row in rows if row["starsign_id"] == "The_Book_Worm")
    locked = next(row for row in rows if row["starsign_id"] == "Flexo_Bendo")
    assert unlocked["is_unlocked"] == 1
    assert locked["is_unlocked"] == 0


def test_export_tidy_csvs(sample_save_data, tmp_path):
    paths = export_tidy_csvs(
        sample_save_data,
        tmp_path,
        source_path="test-save",
        timestamp="2026-01-01T00:00:00Z",
    )

    expected_tables = {
        "snapshots",
        "account_metrics",
        "characters",
        "skills",
        "inventory_slots",
        "equipment_slots",
        "quests",
        "cards",
        "starsigns",
    }
    assert expected_tables == set(paths.keys())
    assert (tmp_path / "data_dictionary.csv").exists()

    with open(tmp_path / "characters.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["snapshot_id"] == rows[1]["snapshot_id"]


def test_append_mode(sample_save_data, tmp_path):
    export_tidy_csvs(sample_save_data, tmp_path, source_path="a", timestamp="2026-01-01T00:00:00Z")
    export_tidy_csvs(sample_save_data, tmp_path, source_path="a", timestamp="2026-01-02T00:00:00Z", append=True)

    with open(tmp_path / "skills.csv", encoding="utf-8") as handle:
        content = handle.read()
    assert content.count("snapshot_id,char_index,char_name") == 1
