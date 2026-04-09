"""
R-friendly export of IdleOn save data.

The goal of this module is not to mirror the raw save format one-to-one, but to
produce stable, analysable datasets with explicit join keys and predictable
column names.
"""

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .progress import CLASS_NAMES, SKILL_NAMES, _extract_level_value, _to_int


R_SAFE_SKILL_NAMES = {k: v.replace("'", "").replace(" ", "_") for k, v in SKILL_NAMES.items()}

CLASS_LINES = {
    0: "Beginner", 1: "Beginner", 2: "Beginner", 3: "Beginner",
    4: "Warrior", 5: "Warrior", 6: "Warrior", 7: "Warrior",
    8: "Warrior", 9: "Warrior", 10: "Warrior",
    11: "Archer", 12: "Archer", 13: "Archer", 14: "Archer",
    15: "Archer", 16: "Archer", 17: "Archer",
    18: "Mage", 19: "Mage", 20: "Mage", 21: "Mage",
    22: "Mage", 23: "Mage", 24: "Mage",
}

CLASS_TIER = {
    0: 0, 1: 1, 2: 2, 3: 3,
    4: 1, 5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 3,
    11: 1, 12: 2, 13: 2, 14: 3, 15: 3, 16: 3, 17: 3,
    18: 1, 19: 2, 20: 2, 21: 3, 22: 3, 23: 3, 24: 3,
}

ALL_SKILL_IDS = sorted(SKILL_NAMES.keys())

TABLE_SCHEMAS = {
    "snapshots": [
        ("snapshot_id", "string", "Deterministic snapshot key for joins."),
        ("timestamp", "datetime", "UTC export timestamp."),
        ("source_path", "string", "Original save directory used for the export."),
    ],
    "account_metrics": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("metric_name", "string", "Metric identifier such as money or character_count."),
        ("metric_value", "number", "Metric value."),
    ],
    "characters": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("char_index", "integer", "Zero-based character index within the save."),
        ("char_name", "string", "Character name."),
        ("class_id", "integer", "Raw IdleOn class id."),
        ("class_name", "string", "Human-readable class name."),
        ("class_line", "string", "Class archetype for faceting."),
        ("class_tier", "integer", "Promotion tier."),
        ("level", "integer", "Displayed character level."),
        ("exp_current", "number", "Current level experience."),
        ("exp_required", "number", "Required experience for next level."),
        ("current_map", "integer", "Current map id."),
        ("afk_target", "string", "Current AFK target identifier."),
        ("hp", "number", "Current HP."),
        ("mp", "number", "Current MP."),
        ("money_carried", "number", "Per-character carried money."),
        ("inventory_slots_owned", "integer", "Unlocked inventory slots."),
    ],
    "skills": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("char_index", "integer", "Join key to characters.csv."),
        ("char_name", "string", "Denormalized character name."),
        ("skill_id", "integer", "Raw skill id."),
        ("skill_name", "string", "R-safe skill name."),
        ("skill_level", "integer", "Observed skill level."),
        ("skill_exp_current", "number", "Current skill experience."),
        ("skill_exp_required", "number", "Required skill experience."),
    ],
    "inventory_slots": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("char_index", "integer", "Join key to characters.csv."),
        ("char_name", "string", "Denormalized character name."),
        ("slot_index", "integer", "Inventory slot index."),
        ("slot_state", "string", "occupied, empty or locked."),
        ("item_code", "string", "Raw item id."),
        ("item_quantity", "number", "Stack size."),
        ("item_meta_json", "json", "Serialized per-slot metadata."),
    ],
    "equipment_slots": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("char_index", "integer", "Join key to characters.csv."),
        ("char_name", "string", "Denormalized character name."),
        ("equipment_tab_index", "integer", "Equipment tab group."),
        ("slot_index", "integer", "Slot index within the tab."),
        ("slot_state", "string", "occupied or empty."),
        ("item_code", "string", "Raw equipped item id."),
        ("item_quantity", "number", "Quantity in the slot."),
        ("item_stats_json", "json", "Serialized stat payload."),
    ],
    "quests": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("char_index", "integer", "Join key to characters.csv."),
        ("char_name", "string", "Denormalized character name."),
        ("quest_id", "string", "Quest identifier."),
        ("quest_complete_code", "integer", "Raw completion code from the save."),
        ("quest_is_complete", "integer", "1 only when the raw code is > 0."),
        ("status_value_count", "integer", "Length of the quest status vector."),
        ("status_json", "json", "Serialized raw quest status payload."),
    ],
    "cards": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("card_group_index", "integer", "Original card page/group index."),
        ("card_id", "string", "Card identifier."),
        ("card_value", "number", "Observed raw card value."),
    ],
    "starsigns": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("starsign_id", "string", "Star sign identifier."),
        ("unlock_value", "string", "Raw unlock value from the save."),
        ("is_unlocked", "integer", "1 if the value is truthy."),
    ],
}


def make_snapshot_id(timestamp: str, source_path: str = "") -> str:
    raw = f"{timestamp}|{source_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _json_cell(value: Any) -> str:
    if value in ("", None):
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _list_value(values: Any, index: int, default: Any = "") -> Any:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return default


def _skill_array_to_map(values: Any) -> dict[int, int]:
    if isinstance(values, list):
        result = {}
        for idx, value in enumerate(values):
            converted = _to_int(value)
            result[idx] = 0 if converted is None else converted
        return result
    if isinstance(values, dict):
        result = {}
        for key, value in values.items():
            idx = _to_int(key)
            if idx is None:
                continue
            converted = _to_int(value)
            result[idx] = 0 if converted is None else converted
        return result
    return {}


def _iter_character_contexts(save: dict) -> Iterable[dict]:
    player_db = save.get("PlayerDATABASE")
    if isinstance(player_db, dict) and player_db:
        for char_index, (char_name, char_data) in enumerate(player_db.items()):
            if isinstance(char_data, dict):
                yield {
                    "char_index": char_index,
                    "char_name": char_name,
                    "char_data": char_data,
                    "is_player_db": True,
                }
        return

    names = save.get("PlayerNames", [])
    classes = [k for k in save if k.startswith("CharacterClass_")]
    skill_keys = [k for k in save if k.startswith("SkillLevels_") and "MAX" not in k]
    max_index = -1
    for key in classes + skill_keys:
        idx = _to_int(key.split("_")[-1])
        if idx is not None:
            max_index = max(max_index, idx)
    if isinstance(names, list):
        max_index = max(max_index, len(names) - 1)

    for char_index in range(max_index + 1):
        char_name = _list_value(names, char_index, f"char_{char_index}")
        yield {
            "char_index": char_index,
            "char_name": char_name,
            "char_data": save,
            "is_player_db": False,
        }


def _class_for_context(context: dict) -> Optional[int]:
    char_data = context["char_data"]
    if context["is_player_db"]:
        return _to_int(char_data.get("CharacterClass"))
    return _to_int(char_data.get(f"CharacterClass_{context['char_index']}"))


def _level_for_context(context: dict) -> Optional[int]:
    char_data = context["char_data"]
    if context["is_player_db"]:
        return _extract_level_value(char_data)
    levels = char_data.get("Level")
    if isinstance(levels, list):
        return _to_int(_list_value(levels, context["char_index"]))
    return None


def _skill_payload_for_context(context: dict) -> tuple[dict[int, int], list[Any], list[Any]]:
    char_data = context["char_data"]
    if context["is_player_db"]:
        return (
            _skill_array_to_map(char_data.get("SkillLevels")),
            char_data.get("Exp0", []) if isinstance(char_data.get("Exp0"), list) else [],
            char_data.get("ExpReq0", []) if isinstance(char_data.get("ExpReq0"), list) else [],
        )

    skill_key = f"SkillLevels_{context['char_index']}"
    req_key = f"SkillLevelsMAX_{context['char_index']}"
    return (
        _skill_array_to_map(char_data.get(skill_key)),
        [],
        char_data.get(req_key, []) if isinstance(char_data.get(req_key), list) else [],
    )


def extract_tidy_characters(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []
    for context in _iter_character_contexts(save):
        char_data = context["char_data"]
        class_id = _class_for_context(context)
        rows.append({
            "snapshot_id": snapshot_id,
            "char_index": context["char_index"],
            "char_name": context["char_name"],
            "class_id": class_id if class_id is not None else "",
            "class_name": CLASS_NAMES.get(class_id, "") if class_id is not None else "",
            "class_line": CLASS_LINES.get(class_id, "") if class_id is not None else "",
            "class_tier": CLASS_TIER.get(class_id, "") if class_id is not None else "",
            "level": _level_for_context(context) or "",
            "exp_current": _list_value(char_data.get("Exp0", []), 0),
            "exp_required": _list_value(char_data.get("ExpReq0", []), 0),
            "current_map": char_data.get("CurrentMap", ""),
            "afk_target": char_data.get("AFKtarget", ""),
            "hp": char_data.get("PlayerHP", ""),
            "mp": char_data.get("PlayerMP", ""),
            "money_carried": char_data.get("Money", ""),
            "inventory_slots_owned": char_data.get("InventorySlotsOwned", ""),
        })

    return rows


def extract_tidy_skills(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []
    for context in _iter_character_contexts(save):
        skill_map, exp_current, exp_required = _skill_payload_for_context(context)
        for skill_id in ALL_SKILL_IDS:
            rows.append({
                "snapshot_id": snapshot_id,
                "char_index": context["char_index"],
                "char_name": context["char_name"],
                "skill_id": skill_id,
                "skill_name": R_SAFE_SKILL_NAMES.get(skill_id, f"Skill_{skill_id}"),
                "skill_level": skill_map.get(skill_id, 0),
                "skill_exp_current": _list_value(exp_current, skill_id),
                "skill_exp_required": _list_value(exp_required, skill_id),
            })
    return rows


def extract_tidy_account_metrics(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []

    def add_metric(metric_name: str, metric_value: Any):
        if metric_value in (None, ""):
            return
        rows.append({
            "snapshot_id": snapshot_id,
            "metric_name": metric_name,
            "metric_value": metric_value,
        })

    add_metric("money", save.get("Money"))
    add_metric("gems", save.get("GemsOwned"))

    card_total = 0
    card_collected = 0
    cards = save.get("Cards")
    if isinstance(cards, list):
        for group in cards:
            if isinstance(group, dict):
                card_total += len(group)
                card_collected += sum(1 for value in group.values() if _to_int(value) not in (None, 0))
    elif isinstance(cards, dict):
        card_total = len(cards)
        card_collected = sum(1 for value in cards.values() if _to_int(value) not in (None, 0))
    add_metric("cards_total", card_total)
    add_metric("cards_collected", card_collected)

    add_metric("character_count", len(list(_iter_character_contexts(save))))

    starsigns = save.get("StarSignsUnlocked")
    if isinstance(starsigns, dict):
        add_metric("starsigns_unlocked", sum(1 for value in starsigns.values() if str(value) not in ("", "0", "False", "false")))

    return rows


def extract_tidy_inventory(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []
    for context in _iter_character_contexts(save):
        if not context["is_player_db"]:
            continue
        char_data = context["char_data"]
        items = char_data.get("InventoryOrder")
        quantities = char_data.get("ItemQuantity")
        metadata = char_data.get("ItemMap")
        if not isinstance(items, list):
            continue

        for slot_index, item_code in enumerate(items):
            slot_state = "occupied"
            if item_code == "Blank":
                slot_state = "empty"
            elif item_code == "LockedInvSpace":
                slot_state = "locked"
            rows.append({
                "snapshot_id": snapshot_id,
                "char_index": context["char_index"],
                "char_name": context["char_name"],
                "slot_index": slot_index,
                "slot_state": slot_state,
                "item_code": item_code,
                "item_quantity": _list_value(quantities, slot_index, ""),
                "item_meta_json": _json_cell(_list_value(metadata, slot_index, "")),
            })

    return rows


def extract_tidy_equipment(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []
    for context in _iter_character_contexts(save):
        if not context["is_player_db"]:
            continue
        char_data = context["char_data"]
        equipment = char_data.get("EquipmentOrder")
        quantities = char_data.get("EquipmentQuantity")
        stats = char_data.get("EquipmentMap")
        if not isinstance(equipment, list):
            continue

        for tab_index, tab_items in enumerate(equipment):
            if not isinstance(tab_items, list):
                continue
            tab_quantities = _list_value(quantities, tab_index, [])
            tab_stats = _list_value(stats, tab_index, [])
            for slot_index, item_code in enumerate(tab_items):
                rows.append({
                    "snapshot_id": snapshot_id,
                    "char_index": context["char_index"],
                    "char_name": context["char_name"],
                    "equipment_tab_index": tab_index,
                    "slot_index": slot_index,
                    "slot_state": "empty" if item_code == "Blank" else "occupied",
                    "item_code": item_code,
                    "item_quantity": _list_value(tab_quantities, slot_index, ""),
                    "item_stats_json": _json_cell(_list_value(tab_stats, slot_index, "")),
                })

    return rows


def extract_tidy_quests(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return []

    rows = []
    for context in _iter_character_contexts(save):
        char_data = context["char_data"]
        quest_status = char_data.get("QuestStatus")
        quest_complete = char_data.get("QuestComplete")
        if not isinstance(quest_status, dict) and not isinstance(quest_complete, dict):
            continue

        quest_ids = set()
        if isinstance(quest_status, dict):
            quest_ids.update(quest_status.keys())
        if isinstance(quest_complete, dict):
            quest_ids.update(quest_complete.keys())

        for quest_id in sorted(quest_ids):
            complete_code = _to_int(quest_complete.get(quest_id)) if isinstance(quest_complete, dict) else None
            status_value = quest_status.get(quest_id) if isinstance(quest_status, dict) else None
            rows.append({
                "snapshot_id": snapshot_id,
                "char_index": context["char_index"],
                "char_name": context["char_name"],
                "quest_id": quest_id,
                "quest_complete_code": complete_code if complete_code is not None else "",
                "quest_is_complete": 1 if complete_code is not None and complete_code > 0 else 0,
                "status_value_count": len(status_value) if isinstance(status_value, list) else (1 if status_value not in (None, "") else 0),
                "status_json": _json_cell(status_value),
            })

    return rows


def extract_tidy_cards(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    cards = save.get("Cards") if isinstance(save, dict) else None
    rows = []
    if isinstance(cards, list):
        for group_index, group in enumerate(cards):
            if not isinstance(group, dict):
                continue
            for card_id, card_value in sorted(group.items()):
                rows.append({
                    "snapshot_id": snapshot_id,
                    "card_group_index": group_index,
                    "card_id": card_id,
                    "card_value": card_value,
                })
    elif isinstance(cards, dict):
        for card_id, card_value in sorted(cards.items()):
            rows.append({
                "snapshot_id": snapshot_id,
                "card_group_index": 0,
                "card_id": card_id,
                "card_value": card_value,
            })
    return rows


def extract_tidy_starsigns(data: dict, snapshot_id: str) -> list[dict]:
    save = data.get("mySave", data)
    starsigns = save.get("StarSignsUnlocked") if isinstance(save, dict) else None
    if not isinstance(starsigns, dict):
        return []

    rows = []
    for starsign_id, unlock_value in sorted(starsigns.items()):
        rows.append({
            "snapshot_id": snapshot_id,
            "starsign_id": starsign_id,
            "unlock_value": unlock_value,
            "is_unlocked": 0 if str(unlock_value) in ("", "0", "False", "false") else 1,
        })
    return rows


def _write_csv(rows: list[dict], filepath: Path, append: bool = False, fieldnames: Optional[list[str]] = None):
    mode = "a" if append and filepath.exists() else "w"
    write_header = not (append and filepath.exists())
    if fieldnames is None:
        if rows:
            fieldnames = list(rows[0].keys())
        else:
            raise ValueError("fieldnames are required when writing an empty CSV")

    with open(filepath, mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _write_dataset_dictionary(output_dir: Path):
    rows = []
    for table_name, columns in TABLE_SCHEMAS.items():
        for column_name, data_type, description in columns:
            rows.append({
                "table_name": table_name,
                "column_name": column_name,
                "data_type": data_type,
                "description": description,
            })
    _write_csv(rows, output_dir / "data_dictionary.csv", append=False, fieldnames=list(rows[0].keys()))


def export_tidy_csvs(
    data: dict,
    output_dir: Path,
    source_path: str = "",
    append: bool = False,
    timestamp: Optional[str] = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    snapshot_id = make_snapshot_id(timestamp, source_path)
    snapshot_rows = [{
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "source_path": source_path,
    }]

    tables = {
        "snapshots": snapshot_rows,
        "account_metrics": extract_tidy_account_metrics(data, snapshot_id),
        "characters": extract_tidy_characters(data, snapshot_id),
        "skills": extract_tidy_skills(data, snapshot_id),
        "inventory_slots": extract_tidy_inventory(data, snapshot_id),
        "equipment_slots": extract_tidy_equipment(data, snapshot_id),
        "quests": extract_tidy_quests(data, snapshot_id),
        "cards": extract_tidy_cards(data, snapshot_id),
        "starsigns": extract_tidy_starsigns(data, snapshot_id),
    }

    paths = {}
    for table_name, rows in tables.items():
        filepath = output_dir / f"{table_name}.csv"
        fieldnames = [column_name for column_name, _, _ in TABLE_SCHEMAS[table_name]]
        _write_csv(rows, filepath, append=append, fieldnames=fieldnames)
        paths[table_name] = filepath

    _write_dataset_dictionary(output_dir)
    return paths


def rows_to_csv_string(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
