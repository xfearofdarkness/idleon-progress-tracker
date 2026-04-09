"""
R-friendly export of IdleOn save data.

The goal of this module is not to mirror the raw save format one-to-one, but to
produce stable, analysable datasets with explicit join keys and predictable
column names.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from . import __version__
from .progress import CLASS_NAMES, SKILL_NAMES, _extract_level_value, _to_int


SCHEMA_VERSION = 2
RUN_TYPE_CHOICES = ("manual", "baseline", "checkpoint", "session_end", "milestone")

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
        ("account_label", "string", "Study-facing account label for comparisons."),
        ("study_group", "string", "Optional study group or cohort."),
        ("session_id", "string", "Session identifier supplied at export time."),
        ("run_type", "string", "Optional run classification such as baseline or milestone."),
        ("strategy_label", "string", "Optional study strategy label."),
        ("notes", "string", "Free-form notes captured with the snapshot."),
        ("playtime_minutes_since_last_snapshot", "integer", "Estimated playtime since the prior snapshot."),
        ("schema_version", "integer", "Exporter schema version for compatibility tracking."),
        ("exporter_version", "string", "IdleOn tracker package version."),
        ("git_commit", "string", "Git commit used for the export, if available."),
        ("platform", "string", "Host platform string for the export run."),
    ],
    "snapshot_tags": [
        ("snapshot_id", "string", "Join key to snapshots.csv."),
        ("tag", "string", "User-supplied event or milestone tag."),
        ("tag_index", "integer", "Zero-based input order for repeated tags."),
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

TABLE_ORDER = [
    "snapshots",
    "snapshot_tags",
    "account_metrics",
    "characters",
    "skills",
    "inventory_slots",
    "equipment_slots",
    "quests",
    "cards",
    "starsigns",
]

REQUIRED_CORE_TABLES = [
    "snapshots",
    "snapshot_tags",
    "account_metrics",
    "characters",
    "skills",
    "inventory_slots",
    "equipment_slots",
    "quests",
    "cards",
    "starsigns",
]

DUPLICATE_KEY_FIELDS = {
    "snapshots": ("snapshot_id",),
    "snapshot_tags": ("snapshot_id", "tag_index"),
    "account_metrics": ("snapshot_id", "metric_name"),
    "characters": ("snapshot_id", "char_index"),
    "skills": ("snapshot_id", "char_index", "skill_name"),
    "inventory_slots": ("snapshot_id", "char_index", "slot_index"),
    "equipment_slots": ("snapshot_id", "char_index", "equipment_tab_index", "slot_index"),
    "quests": ("snapshot_id", "char_index", "quest_id"),
    "cards": ("snapshot_id", "card_group_index", "card_id"),
    "starsigns": ("snapshot_id", "starsign_id"),
}


class ExportValidationError(RuntimeError):
    """Raised when export validation fails before or after writing files."""

    def __init__(self, message: str, validation_results: Optional[list[dict[str, Any]]] = None):
        super().__init__(message)
        self.validation_results = validation_results or []


@dataclass
class ExportResult:
    snapshot_id: str
    timestamp: str
    output_dir: Path
    source_path: str
    append: bool
    dry_run: bool
    paths: dict[str, Path]
    table_row_counts: dict[str, int]
    validation: list[dict[str, Any]]
    warnings: list[str]
    manifest_path: Optional[Path]
    study_metadata: dict[str, Any]


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


def extract_snapshot_tags(snapshot_id: str, tags: list[str]) -> list[dict]:
    return [
        {
            "snapshot_id": snapshot_id,
            "tag": tag,
            "tag_index": idx,
        }
        for idx, tag in enumerate(tags)
    ]


def _expected_fieldnames(table_name: str) -> list[str]:
    return [column_name for column_name, _, _ in TABLE_SCHEMAS[table_name]]


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


def _normalize_study_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = metadata or {}
    tags = data.get("tags") or []
    return {
        "account_label": data.get("account_label", "") or "",
        "study_group": data.get("study_group", "") or "",
        "session_id": data.get("session_id", "") or "",
        "run_type": data.get("run_type", "") or "",
        "strategy_label": data.get("strategy_label", "") or "",
        "notes": data.get("notes", "") or "",
        "playtime_minutes_since_last_snapshot": data.get("playtime_minutes_since_last_snapshot", ""),
        "tags": [str(tag) for tag in tags],
    }


def _platform_string() -> str:
    return platform.platform()


def _git_commit() -> str:
    repo_root = Path(__file__).resolve().parent.parent
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


def _build_snapshot_row(snapshot_id: str, timestamp: str, source_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "source_path": source_path,
        "account_label": metadata["account_label"],
        "study_group": metadata["study_group"],
        "session_id": metadata["session_id"],
        "run_type": metadata["run_type"],
        "strategy_label": metadata["strategy_label"],
        "notes": metadata["notes"],
        "playtime_minutes_since_last_snapshot": metadata["playtime_minutes_since_last_snapshot"],
        "schema_version": SCHEMA_VERSION,
        "exporter_version": __version__,
        "git_commit": _git_commit(),
        "platform": _platform_string(),
    }


def _build_tables(data: dict, snapshot_row: dict[str, Any], metadata: dict[str, Any]) -> dict[str, list[dict]]:
    snapshot_id = snapshot_row["snapshot_id"]
    return {
        "snapshots": [snapshot_row],
        "snapshot_tags": extract_snapshot_tags(snapshot_id, metadata["tags"]),
        "account_metrics": extract_tidy_account_metrics(data, snapshot_id),
        "characters": extract_tidy_characters(data, snapshot_id),
        "skills": extract_tidy_skills(data, snapshot_id),
        "inventory_slots": extract_tidy_inventory(data, snapshot_id),
        "equipment_slots": extract_tidy_equipment(data, snapshot_id),
        "quests": extract_tidy_quests(data, snapshot_id),
        "cards": extract_tidy_cards(data, snapshot_id),
        "starsigns": extract_tidy_starsigns(data, snapshot_id),
    }


def _record_validation(results: list[dict[str, Any]], name: str, passed: bool, message: str, **details: Any) -> None:
    entry = {
        "name": name,
        "passed": passed,
        "message": message,
    }
    if details:
        entry["details"] = details
    results.append(entry)


def _header_line(fieldnames: list[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fieldnames)
    return output.getvalue().strip()


def _count_csv_rows(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    with open(filepath, encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _validate_tables(
    tables: dict[str, list[dict]],
    snapshot_id: str,
    output_dir: Path,
    append: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    warnings: list[str] = []

    missing_tables = [table_name for table_name in REQUIRED_CORE_TABLES if table_name not in tables or not isinstance(tables[table_name], list)]
    _record_validation(
        results,
        "required_tables_present",
        not missing_tables,
        "All expected tables are present in memory." if not missing_tables else "Missing required tables before export.",
        missing_tables=missing_tables,
    )

    snapshot_ok = bool(snapshot_id)
    _record_validation(
        results,
        "snapshot_id_present",
        snapshot_ok,
        "Snapshot id is available." if snapshot_ok else "Snapshot id is empty.",
    )

    mismatched_tables = []
    for table_name, rows in tables.items():
        for row in rows:
            if row.get("snapshot_id", "") != snapshot_id:
                mismatched_tables.append(table_name)
                break
    _record_validation(
        results,
        "snapshot_ids_match",
        not mismatched_tables,
        "All exported rows point to the current snapshot." if not mismatched_tables else "Some rows reference the wrong snapshot id.",
        tables=mismatched_tables,
    )

    duplicate_details = {}
    for table_name, key_fields in DUPLICATE_KEY_FIELDS.items():
        rows = tables.get(table_name, [])
        seen = set()
        duplicates = []
        for row in rows:
            key = tuple(row.get(field, "") for field in key_fields)
            if key in seen:
                duplicates.append(key)
                if len(duplicates) == 3:
                    break
            seen.add(key)
        if duplicates:
            duplicate_details[table_name] = {
                "key_fields": list(key_fields),
                "examples": [list(key) for key in duplicates],
            }
    _record_validation(
        results,
        "duplicate_keys",
        not duplicate_details,
        "No duplicate natural keys found in exported tables." if not duplicate_details else "Duplicate natural keys detected.",
        duplicates=duplicate_details,
    )

    if append and output_dir.exists():
        existing_files = [output_dir / f"{table_name}.csv" for table_name in TABLE_ORDER if (output_dir / f"{table_name}.csv").exists()]
        if existing_files:
            missing_files = [f"{table_name}.csv" for table_name in TABLE_ORDER if not (output_dir / f"{table_name}.csv").exists()]
            _record_validation(
                results,
                "append_target_complete",
                not missing_files,
                "Append target contains all required CSV tables." if not missing_files else "Append target is incomplete.",
                missing_files=missing_files,
            )

            schema_mismatches = {}
            duplicated_header_rows = {}
            for table_name in TABLE_ORDER:
                filepath = output_dir / f"{table_name}.csv"
                if not filepath.exists():
                    continue
                expected = _expected_fieldnames(table_name)
                with open(filepath, encoding="utf-8", newline="") as handle:
                    lines = handle.read().splitlines()
                if not lines:
                    schema_mismatches[table_name] = {
                        "expected": expected,
                        "actual": [],
                    }
                    continue
                actual_header = next(csv.reader([lines[0]]), [])
                if actual_header != expected:
                    schema_mismatches[table_name] = {
                        "expected": expected,
                        "actual": actual_header,
                    }
                header_line = _header_line(expected)
                duplicated_count = sum(1 for line in lines[1:] if line.strip() == header_line)
                if duplicated_count:
                    duplicated_header_rows[table_name] = duplicated_count

            _record_validation(
                results,
                "append_headers_match",
                not schema_mismatches,
                "Append target headers match the current schema." if not schema_mismatches else "Append target headers do not match the current schema.",
                mismatches=schema_mismatches,
            )
            _record_validation(
                results,
                "append_no_duplicate_headers",
                not duplicated_header_rows,
                "Append target does not contain duplicated header rows." if not duplicated_header_rows else "Append target contains duplicated header rows.",
                duplicates=duplicated_header_rows,
            )

    if not tables.get("characters"):
        warnings.append("characters.csv ist leer; pruefe, ob der richtige Save geladen wurde.")

    if not tables.get("account_metrics"):
        warnings.append("account_metrics.csv ist leer; pruefe, ob der Save ungewoehnlich formatiert ist.")

    failures = [result for result in results if not result["passed"]]
    if failures:
        message = failures[0]["message"]
        if failures[0]["name"] in {"append_target_complete", "append_headers_match"}:
            message += " Nutze ein neues Exportverzeichnis oder migriere den alten Export."
        raise ExportValidationError(message, validation_results=results)

    return results, warnings


def _validate_written_row_counts(
    output_dir: Path,
    expected_counts: dict[str, int],
    previous_counts: dict[str, int],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    mismatches = {}

    for table_name in TABLE_ORDER:
        filepath = output_dir / f"{table_name}.csv"
        actual_total = _count_csv_rows(filepath)
        expected_delta = expected_counts[table_name]
        previous_total = previous_counts[table_name]
        actual_delta = actual_total - previous_total
        if actual_delta != expected_delta:
            mismatches[table_name] = {
                "expected_delta": expected_delta,
                "actual_delta": actual_delta,
                "previous_total": previous_total,
                "actual_total": actual_total,
            }

    _record_validation(
        results,
        "written_row_counts_match",
        not mismatches,
        "Written row counts match the exported row counts." if not mismatches else "Written row counts do not match the exported row counts.",
        mismatches=mismatches,
    )

    if mismatches:
        raise ExportValidationError("Written row counts do not match the exported row counts.", validation_results=results)

    return results


def _write_manifest(filepath: Path, manifest: dict[str, Any]) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def export_tidy_csvs(
    data: dict,
    output_dir: Path,
    source_path: str = "",
    append: bool = False,
    timestamp: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    dry_run: bool = False,
) -> ExportResult:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    output_dir = Path(output_dir)
    metadata = _normalize_study_metadata(metadata)

    snapshot_id = make_snapshot_id(timestamp, source_path)
    snapshot_row = _build_snapshot_row(snapshot_id, timestamp, source_path, metadata)
    tables = _build_tables(data, snapshot_row, metadata)
    table_row_counts = {table_name: len(tables[table_name]) for table_name in TABLE_ORDER}
    paths = {table_name: output_dir / f"{table_name}.csv" for table_name in TABLE_ORDER}

    validation_results, warnings = _validate_tables(tables, snapshot_id, output_dir, append=append)
    manifest_path = None

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        previous_counts = {table_name: _count_csv_rows(paths[table_name]) for table_name in TABLE_ORDER}

        for table_name in TABLE_ORDER:
            fieldnames = _expected_fieldnames(table_name)
            _write_csv(tables[table_name], paths[table_name], append=append, fieldnames=fieldnames)

        _write_dataset_dictionary(output_dir)
        validation_results.extend(_validate_written_row_counts(output_dir, table_row_counts, previous_counts))

        manifest_path = output_dir / "run_manifests" / f"{snapshot_id}.json"
        manifest = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "export_dir": str(output_dir),
            "mode": "append" if append else "write",
            "source_path": source_path,
            "platform": snapshot_row["platform"],
            "python_version": sys.version.split()[0],
            "schema_version": SCHEMA_VERSION,
            "exporter_version": __version__,
            "git_commit": snapshot_row["git_commit"],
            "study_metadata": metadata,
            "table_row_counts": table_row_counts,
            "validation": validation_results,
            "warnings": warnings,
            "success": True,
        }
        _write_manifest(manifest_path, manifest)

    return ExportResult(
        snapshot_id=snapshot_id,
        timestamp=timestamp,
        output_dir=output_dir,
        source_path=source_path,
        append=append,
        dry_run=dry_run,
        paths=paths,
        table_row_counts=table_row_counts,
        validation=validation_results,
        warnings=warnings,
        manifest_path=manifest_path,
        study_metadata=metadata,
    )


def rows_to_csv_string(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
