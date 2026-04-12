"""Safety checks for reading IdleOn LevelDB saves reliably."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SaveGuardError(RuntimeError):
    """Raised when the local save state is unsafe for a reliable export."""


@dataclass(frozen=True)
class SaveHealth:
    key_count: int
    character_count: int
    global_indicator_count: int
    character_indicator_count: int


def _relevant_save_files(db_path: Path) -> list[Path]:
    files = []
    for path in db_path.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if path.suffix.lower() in {".log", ".ldb"} or name in {"LOG", "LOG.old", "MANIFEST-000001", "CURRENT", "LOCK"} or name.startswith("MANIFEST-"):
            files.append(path)
    return sorted(files, key=lambda item: item.name)


def _snapshot_files(db_path: Path) -> tuple[tuple[str, int, int], ...]:
    snapshot = []
    for path in _relevant_save_files(db_path):
        stat = path.stat()
        snapshot.append((path.name, stat.st_size, stat.st_mtime_ns))
    return tuple(snapshot)


def _matches_idleon_process(haystack: str) -> bool:
    text = haystack.lower()
    tokens = (
        "idleon",
        "legends-of-idleon",
        "legends of idleon",
    )
    return any(token in text for token in tokens)


def _windows_idleon_processes() -> list[str]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | Select-Object Name,CommandLine | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        payload = [payload]

    matches: list[str] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("Name", "")).strip()
        command_line = str(entry.get("CommandLine", "")).strip()
        haystack = f"{name} {command_line}".lower()
        if _matches_idleon_process(haystack):
            matches.append(name or command_line or "IdleOn-Prozess")
    return sorted(set(matches))


def _posix_idleon_processes() -> list[str]:
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,comm=,args="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    matches: list[str] = []
    for line in result.stdout.splitlines():
        if _matches_idleon_process(line):
            matches.append(line.strip())
    return sorted(set(matches))


def find_idleon_processes() -> list[str]:
    if sys.platform.startswith("win"):
        return _windows_idleon_processes()
    return _posix_idleon_processes()


def ensure_save_ready(
    db_path: Path,
    *,
    allow_live_game: bool = False,
    stability_wait_seconds: float = 1.0,
) -> None:
    if not db_path.exists():
        raise SaveGuardError(f"Save-Pfad existiert nicht: {db_path}")
    if not db_path.is_dir():
        raise SaveGuardError(f"Save-Pfad ist kein Verzeichnis: {db_path}")

    running = find_idleon_processes()
    if running and not allow_live_game:
        preview = ", ".join(running[:3])
        raise SaveGuardError(
            "IdleOn scheint noch zu laufen. Bitte das Spiel vollständig schliessen, "
            f"bevor du exportierst. Erkannte Prozesse: {preview}"
        )

    first = _snapshot_files(db_path)
    if not first:
        raise SaveGuardError(
            "Im Save-Verzeichnis wurden keine relevanten LevelDB-Dateien gefunden."
        )
    time.sleep(stability_wait_seconds)
    second = _snapshot_files(db_path)
    if first != second:
        raise SaveGuardError(
            "Die Save-Dateien verändern sich noch. Bitte kurz warten und den Export "
            "erneut starten, sobald IdleOn wirklich geschlossen ist."
        )


def evaluate_save_health(data: dict[str, Any]) -> SaveHealth:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        raise SaveGuardError("Save-Daten haben kein gueltiges Hauptobjekt.")

    player_db = save.get("PlayerDATABASE")
    if not isinstance(player_db, dict) or not player_db:
        raise SaveGuardError(
            "PlayerDATABASE fehlt oder ist leer. Der Save wurde nur teilweise gelesen."
        )

    key_count = len(save)
    character_count = len(player_db)
    global_indicator_count = sum(
        1
        for key in ("Cards", "Money", "GemsOwned", "StarSignsUnlocked", "PlayerNames")
        if key in save
    )
    first_character = next(iter(player_db.values()), {})
    if not isinstance(first_character, dict):
        raise SaveGuardError("Character-Daten sind unvollständig oder beschädigt.")
    character_indicator_count = sum(
        1
        for key in (
            "CharacterClass",
            "Lv0",
            "Exp0",
            "CurrentMap",
            "QuestStatus",
            "InventoryOrder",
        )
        if key in first_character
    )

    if key_count < 2 or character_indicator_count < 2:
        raise SaveGuardError(
            "Zu wenige erwartete Save-Daten gefunden. Der Read ist vermutlich unvollständig "
            "(keys="
            f"{key_count}, globale Indikatoren={global_indicator_count}, "
            f"Charakter-Indikatoren={character_indicator_count})."
        )

    if global_indicator_count == 0 and key_count < 4:
        raise SaveGuardError(
            "Zu wenige erwartete Save-Daten gefunden. Der Read ist vermutlich unvollständig "
            "(keys="
            f"{key_count}, globale Indikatoren={global_indicator_count}, "
            f"Charakter-Indikatoren={character_indicator_count})."
        )

    return SaveHealth(
        key_count=key_count,
        character_count=character_count,
        global_indicator_count=global_indicator_count,
        character_indicator_count=character_indicator_count,
    )
