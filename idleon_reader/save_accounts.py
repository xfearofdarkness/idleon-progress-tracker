"""Detect and select logical IdleOn save accounts from decoded LevelDB data."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Optional


class SaveAccountSelectionError(RuntimeError):
    """Raised when a logical save account cannot be selected."""


@dataclass(frozen=True)
class SaveAccountCandidate:
    selector: str
    display_name: str
    character_count: int
    character_names: tuple[str, ...]
    has_player_database: bool
    data: dict[str, Any]


def _save_shape_score(value: Any) -> int:
    if not isinstance(value, dict):
        return 0

    score = 0
    player_db = value.get("PlayerDATABASE")
    if isinstance(player_db, dict) and player_db:
        score += 4

    player_names = value.get("PlayerNames")
    if isinstance(player_names, list) and player_names:
        score += 2

    if "Money" in value:
        score += 1
    if "GemsOwned" in value:
        score += 1
    if "Cards" in value:
        score += 1
    if "StarSignsUnlocked" in value:
        score += 1
    if any(str(key).startswith("CharacterClass_") for key in value):
        score += 1
    if "CharacterClass" in value:
        score += 1
    return score


def _looks_like_save_dict(value: Any) -> bool:
    return _save_shape_score(value) >= 3


def _character_names_for_save(value: dict[str, Any]) -> tuple[str, ...]:
    player_db = value.get("PlayerDATABASE")
    if isinstance(player_db, dict) and player_db:
        return tuple(str(name) for name in player_db.keys())

    names = value.get("PlayerNames")
    if isinstance(names, list) and names:
        return tuple(str(name) for name in names if str(name).strip())

    return tuple()


def _display_name(selector: str, names: tuple[str, ...]) -> str:
    if names:
        preview = ", ".join(names[:3])
        if len(names) > 3:
            preview += ", ..."
        return f"{selector} ({preview})"
    return selector


def discover_save_accounts(raw_data: dict[str, Any]) -> list[SaveAccountCandidate]:
    found: dict[str, SaveAccountCandidate] = {}

    def visit(value: Any, path: str, depth: int) -> None:
        if _looks_like_save_dict(value):
            names = _character_names_for_save(value)
            player_db = value.get("PlayerDATABASE")
            found[path] = SaveAccountCandidate(
                selector=path,
                display_name=_display_name(path, names),
                character_count=len(names),
                character_names=names,
                has_player_database=isinstance(player_db, dict) and bool(player_db),
                data=value,
            )
            return

        if depth >= 2:
            return

        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path != "root" else str(key)
                visit(child, child_path, depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_path = f"{path}[{index}]"
                visit(child, child_path, depth + 1)

    visit(raw_data, "root", 0)
    if "root" in found and len(found) > 1:
        # If nested save candidates exist, prefer the more specific candidates.
        found.pop("root", None)

    return sorted(found.values(), key=lambda candidate: candidate.selector)


def format_save_account_candidates(candidates: list[SaveAccountCandidate]) -> list[str]:
    lines = []
    for index, candidate in enumerate(candidates, start=1):
        names = ", ".join(candidate.character_names[:3]) if candidate.character_names else "keine Charakternamen erkannt"
        if len(candidate.character_names) > 3:
            names += ", ..."
        suffix = ""
        if not candidate.has_player_database:
            suffix = "  [wahrscheinlich unvollständig]"
        lines.append(
            f"    [{index}] {candidate.selector:20s} "
            f"{candidate.character_count:>2} Charaktere  {names}{suffix}"
        )
    return lines


def select_save_account(
    raw_data: dict[str, Any],
    selector: str = "",
    *,
    allow_prompt: bool = True,
) -> tuple[dict[str, Any], Optional[SaveAccountCandidate], list[SaveAccountCandidate]]:
    candidates = discover_save_accounts(raw_data)
    if not candidates:
        return raw_data, None, []

    if len(candidates) == 1 and not selector:
        candidate = candidates[0]
        return {"mySave": candidate.data}, candidate, candidates

    if selector:
        selector = selector.strip()
        for index, candidate in enumerate(candidates, start=1):
            if selector == candidate.selector or selector == str(index):
                return {"mySave": candidate.data}, candidate, candidates
        raise SaveAccountSelectionError(
            "Gewuenschter Save-Account wurde nicht gefunden.\n"
            + "\n".join(format_save_account_candidates(candidates))
        )

    if allow_prompt and sys.stdin.isatty():
        print("[*] Mehrere Save-Accounts erkannt:")
        for line in format_save_account_candidates(candidates):
            print(line)
        chosen = input("Auswahl eingeben (Nummer oder selector): ").strip()
        return select_save_account(raw_data, chosen, allow_prompt=False)

    raise SaveAccountSelectionError(
        "Mehrere Save-Accounts erkannt. Bitte mit --save-account auswaehlen oder zuerst --list-save-accounts aufrufen.\n"
        + "\n".join(format_save_account_candidates(candidates))
    )
