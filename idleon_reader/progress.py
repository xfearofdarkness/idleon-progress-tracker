"""
Progress Analyzer

Extracts and formats meaningful player progress information from the raw IdleOn
save data dictionary. Maps internal keys to human-readable names.
"""

from typing import Any, Optional
from datetime import datetime


# ─── Skill Name Mappings ────────────────────────────────────────────────────

SKILL_NAMES = {
    0: "Character",
    1: "Mining",
    2: "Smithing",
    3: "Choppin'",
    4: "Fishing",
    5: "Alchemy",
    6: "Catching",
    7: "Trapping",
    8: "Construction",
    9: "Worship",
    10: "Cooking",
    11: "Breeding",
    12: "Sailing",
    13: "Divinity",
    14: "Gaming",
    15: "Farming",
    16: "Sneaking",
    17: "Summoning",
}

# ─── Class Name Mappings ────────────────────────────────────────────────────

CLASS_NAMES = {
    # Beginner line
    0: "Beginner",
    1: "Journeyman",
    2: "Maestro",
    3: "Virtuoso",
    # Warrior line
    4: "Warrior",
    5: "Barbarian",
    6: "Squire",
    7: "Blood Berserker",
    8: "Death Bringer",
    9: "Divine Knight",
    10: "Royal Guardian",
    # Archer line
    11: "Archer",
    12: "Bowman",
    13: "Hunter",
    14: "Siege Breaker",
    15: "Mayheim",
    16: "Wind Walker",
    17: "Beast Master",
    # Mage line
    18: "Mage",
    19: "Wizard",
    20: "Shaman",
    21: "Elemental Sorcerer",
    22: "Spiritual Monk",
    23: "Bubonic Conjuror",
    24: "Arcane Cultist",
}

# ─── Known Save Data Keys ──────────────────────────────────────────────────

# This maps known internal key prefixes/names to human-readable descriptions
KNOWN_KEYS = {
    "mySave": "Main save data blob",
    "CharacterClass_": "Character classes",
    "SkillLevels_": "Skill levels per character",
    "SkillLevelsMAX_": "Max skill levels per character",
    "PlayerNames": "Character names",
    "Level": "Character levels",
    "Money": "Money/coins",
    "GemsOwned": "Gems owned",
    "PVStatList": "Player stat list",
    "StarSigns": "Active star signs",
    "KillAll": "Kill counts",
    "AnvilPA": "Anvil production",
    "CauldronInfo": "Alchemy cauldron info",
    "BribeStatus": "Bribe/corruption status",
    "Cards": "Card collection",
    "CardEquip": "Equipped cards",
    "Stamps": "Stamp collection",
    "Statues": "Statue collection",
    "Quest": "Quest progress",
    "Tasks": "Task/milestone progress",
    "Inventory": "Inventory items",
    "Equipment": "Equipped items",
    "Storage": "Storage/chest items",
    "GemShop": "Gem shop purchases",
    "AFKtarget": "AFK activity target",
    "AFKtype": "AFK activity type",
    "Constellations": "Constellation progress",
    "Tower": "Tower defense progress",
    "Divinity": "Divinity progress",
    "Sailing": "Sailing progress",
    "Cooking": "Cooking progress",
    "Breeding": "Breeding progress",
    "Gaming": "Gaming (sprout) progress",
    "Farming": "Farming progress",
    "Sneaking": "Sneaking (Jade Emporium) progress",
    "Summoning": "Summoning progress",
}


# ─── Progress Extraction Functions ──────────────────────────────────────────


def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from the data dict, handling nested structures."""
    if key in data:
        return data[key]
    # Try case-insensitive match
    for k, v in data.items():
        if k.lower() == key.lower():
            return v
    return default


def _find_keys_with_prefix(data: dict, prefix: str) -> dict:
    """Find all keys starting with the given prefix."""
    return {k: v for k, v in data.items() if k.startswith(prefix)}


def extract_characters(data: dict) -> list[dict]:
    """
    Extract character information from save data.

    Returns a list of character dicts with name, class, level, skills, etc.
    """
    characters = []

    # The save data may be nested inside 'mySave' or at the top level
    save = data.get("mySave", data)

    if not isinstance(save, dict):
        return characters

    # Try to find character count
    # Characters are typically indexed as CharacterClass_0, CharacterClass_1, etc.
    char_classes = _find_keys_with_prefix(save, "CharacterClass_")
    if not char_classes:
        # Try alternative: flat list under 'CharacterClass'
        flat_classes = save.get("CharacterClass", [])
        if isinstance(flat_classes, list):
            for i, cls in enumerate(flat_classes):
                char_classes[f"CharacterClass_{i}"] = cls

    num_chars = len(char_classes)
    if num_chars == 0:
        # Try to infer from other indexed keys
        for key in save:
            if key.startswith("SkillLevels_"):
                try:
                    idx = int(key.split("_")[1])
                    num_chars = max(num_chars, idx + 1)
                except (ValueError, IndexError):
                    pass

    for i in range(num_chars):
        char = {"index": i}

        # Class
        class_id = save.get(f"CharacterClass_{i}")
        if class_id is not None:
            try:
                class_id = int(class_id)
                char["class_id"] = class_id
                char["class"] = CLASS_NAMES.get(class_id, f"Unknown ({class_id})")
            except (ValueError, TypeError):
                char["class"] = str(class_id)

        # Name
        names = save.get("PlayerNames", [])
        if isinstance(names, list) and i < len(names):
            char["name"] = names[i]

        # Level
        levels = save.get("Level", [])
        if isinstance(levels, list) and i < len(levels):
            char["level"] = levels[i]

        # Skills
        skill_levels = save.get(f"SkillLevels_{i}")
        if isinstance(skill_levels, (list, dict)):
            skills = {}
            if isinstance(skill_levels, list):
                for j, level in enumerate(skill_levels):
                    skill_name = SKILL_NAMES.get(j, f"Skill_{j}")
                    if level and level != 0:
                        skills[skill_name] = level
            elif isinstance(skill_levels, dict):
                for j, level in skill_levels.items():
                    try:
                        j_int = int(j)
                    except (ValueError, TypeError):
                        j_int = j
                    skill_name = SKILL_NAMES.get(j_int, f"Skill_{j}")
                    if level and level != 0:
                        skills[skill_name] = level
            char["skills"] = skills

        # AFK activity
        afk_targets = save.get("AFKtarget", [])
        afk_types = save.get("AFKtype", [])
        if isinstance(afk_targets, list) and i < len(afk_targets):
            char["afk_target"] = afk_targets[i]
        if isinstance(afk_types, list) and i < len(afk_types):
            afk_type = afk_types[i]
            afk_labels = {0: "Fighting", 1: "Mining", 2: "Choppin'", 3: "Fishing",
                          4: "Catching", 5: "Trapping", 6: "Worship", 7: "Laboratory"}
            char["afk_activity"] = afk_labels.get(afk_type, f"Type {afk_type}")

        characters.append(char)

    return characters


def extract_account_info(data: dict) -> dict:
    """Extract account-level information."""
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return {}

    info = {}

    # Money
    money = save.get("Money")
    if money is not None:
        info["money"] = money

    # Gems
    gems = save.get("GemsOwned")
    if gems is not None:
        info["gems"] = gems

    # Cards collected
    cards = save.get("Cards")
    if isinstance(cards, (list, dict)):
        if isinstance(cards, list):
            info["cards_collected"] = sum(1 for c in cards if c)
        else:
            info["cards_collected"] = len(cards)

    # Stamps
    stamps = save.get("Stamps")
    if isinstance(stamps, (list, dict)):
        if isinstance(stamps, list):
            info["stamps_unlocked"] = sum(1 for s in stamps if s)
        elif isinstance(stamps, dict):
            total = 0
            for category, stamp_list in stamps.items():
                if isinstance(stamp_list, list):
                    total += sum(1 for s in stamp_list if s)
            info["stamps_unlocked"] = total

    # Statues
    statues = save.get("Statues")
    if isinstance(statues, (list, dict)):
        if isinstance(statues, list):
            info["statues_collected"] = sum(1 for s in statues if s)
        else:
            info["statues_collected"] = len(statues)

    return info


def extract_progress_summary(data: dict) -> dict:
    """
    Create a comprehensive progress summary from the raw save data.

    Returns a structured dictionary with all extractable progress information.
    """
    summary = {
        "extraction_time": datetime.now().isoformat(),
        "data_keys_found": list(data.keys()) if isinstance(data, dict) else [],
        "account": extract_account_info(data),
        "characters": extract_characters(data),
    }

    save = data.get("mySave", data)

    # Add raw data sections for keys we recognize
    if isinstance(save, dict):
        recognized = {}
        unrecognized = {}
        for key, value in save.items():
            matched = False
            for known_prefix, description in KNOWN_KEYS.items():
                if key.startswith(known_prefix):
                    recognized[key] = {"description": description, "type": type(value).__name__}
                    if isinstance(value, list):
                        recognized[key]["length"] = len(value)
                    elif isinstance(value, dict):
                        recognized[key]["keys_count"] = len(value)
                    matched = True
                    break
            if not matched:
                unrecognized[key] = type(value).__name__

        summary["recognized_keys"] = recognized
        summary["unrecognized_keys"] = unrecognized

    return summary


# ─── Formatting ─────────────────────────────────────────────────────────────


def format_progress_report(summary: dict) -> str:
    """Format the progress summary as a human-readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  LEGENDS OF IDLEON - SPIELERFORTSCHRITT")
    lines.append("=" * 70)
    lines.append(f"  Extrahiert am: {summary.get('extraction_time', 'unbekannt')}")
    lines.append("")

    # Account info
    account = summary.get("account", {})
    if account:
        lines.append("-" * 70)
        lines.append("  ACCOUNT-INFORMATIONEN")
        lines.append("-" * 70)
        if "money" in account:
            lines.append(f"  Geld:              {account['money']:,}" if isinstance(account['money'], (int, float)) else f"  Geld:              {account['money']}")
        if "gems" in account:
            lines.append(f"  Edelsteine:        {account['gems']}")
        if "cards_collected" in account:
            lines.append(f"  Karten gesammelt:  {account['cards_collected']}")
        if "stamps_unlocked" in account:
            lines.append(f"  Stempel freigesch.:{account['stamps_unlocked']}")
        if "statues_collected" in account:
            lines.append(f"  Statuen gesammelt: {account['statues_collected']}")
        lines.append("")

    # Characters
    characters = summary.get("characters", [])
    if characters:
        lines.append("-" * 70)
        lines.append(f"  CHARAKTERE ({len(characters)} gefunden)")
        lines.append("-" * 70)

        for char in characters:
            name = char.get("name", f"Charakter {char.get('index', '?')}")
            char_class = char.get("class", "Unbekannt")
            level = char.get("level", "?")
            lines.append("")
            lines.append(f"  [{char.get('index', '?')}] {name}")
            lines.append(f"      Klasse: {char_class}  |  Level: {level}")

            # AFK
            if "afk_activity" in char:
                lines.append(f"      AFK-Aktivitaet: {char['afk_activity']}")

            # Skills
            skills = char.get("skills", {})
            if skills:
                lines.append("      Faehigkeiten:")
                for skill_name, skill_level in sorted(skills.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0):
                    lines.append(f"        {skill_name:20s} Lv. {skill_level}")

    else:
        lines.append("  Keine Charaktere gefunden.")
        lines.append("")
        lines.append("  Hinweis: Die Speicherdaten koennten in einem anderen Format vorliegen.")
        lines.append("  Versuche, die Rohdaten mit --json zu exportieren und manuell zu pruefen.")

    # Data keys overview
    recognized = summary.get("recognized_keys", {})
    unrecognized = summary.get("unrecognized_keys", {})
    if recognized or unrecognized:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  DATEN-UEBERSICHT")
        lines.append("-" * 70)
        lines.append(f"  Erkannte Schluessel:     {len(recognized)}")
        lines.append(f"  Unbekannte Schluessel:   {len(unrecognized)}")

        if recognized:
            lines.append("")
            lines.append("  Erkannte Datenbereiche:")
            for key, info in sorted(recognized.items()):
                desc = info.get("description", "")
                dtype = info.get("type", "")
                extra = ""
                if "length" in info:
                    extra = f" ({info['length']} Eintraege)"
                elif "keys_count" in info:
                    extra = f" ({info['keys_count']} Schluessel)"
                lines.append(f"    {key:30s} {desc:30s} [{dtype}{extra}]")

    # Top-level keys
    data_keys = summary.get("data_keys_found", [])
    if data_keys:
        lines.append("")
        lines.append("-" * 70)
        lines.append(f"  GEFUNDENE TOP-LEVEL SCHLUESSEL ({len(data_keys)})")
        lines.append("-" * 70)
        for key in sorted(data_keys):
            lines.append(f"    {key}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  Hinweis: Dieses Tool liest nur Daten. Das Spiel wird nicht veraendert.")
    lines.append("=" * 70)

    return "\n".join(lines)
