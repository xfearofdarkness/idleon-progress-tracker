"""Session-state workflow helpers for study exports."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .export_tidy import ExportResult, export_tidy_csvs
from .finder import find_save_directory
from .ldb_reader import read_save_data
from .save_guard import SaveGuardError, ensure_save_ready, evaluate_save_health
from .save_accounts import SaveAccountSelectionError, select_save_account
from .study_backup import (
    BackupRecord,
    StudyBackupError,
    create_backup_from_latest_export,
    create_study_backup,
    update_export_manifest_backup_status,
)
from .study_config import (
    StudyAccountProfile,
    StudyConfig,
    StudyConfigError,
    resolve_account,
    resolve_account_name_by_label,
)


class StudySessionError(RuntimeError):
    """Raised when a study workflow action cannot be completed."""


@dataclass
class StudySessionState:
    account_label: str
    strategy_label: str
    study_group: str
    session_id: str
    save_path: str
    save_account: str
    export_dir: str
    started_at: str
    last_export_at: str
    last_snapshot_id: str
    status: str = "active"


@dataclass
class StudyStatus:
    active: bool
    state: Optional[StudySessionState]
    next_step: str
    last_manifest_path: Optional[Path] = None


def _player_database_from_selected_data(data: dict) -> dict[str, dict]:
    save = data.get("mySave", data)
    if not isinstance(save, dict):
        return {}
    player_db = save.get("PlayerDATABASE")
    if not isinstance(player_db, dict):
        return {}
    return player_db


def state_dir(repo_root: Path) -> Path:
    return repo_root / ".idleon-study"


def state_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "current_session.json"


def load_session_state(repo_root: Path) -> Optional[StudySessionState]:
    path = state_path(repo_root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("save_account", "")
    data.setdefault("last_export_at", "")
    data.setdefault("last_snapshot_id", "")
    normalized = {
        "account_label": data.get("account_label", ""),
        "strategy_label": data.get("strategy_label", ""),
        "study_group": data.get("study_group", ""),
        "session_id": data.get("session_id", ""),
        "save_path": data.get("save_path", ""),
        "save_account": data.get("save_account", ""),
        "export_dir": data.get("export_dir", ""),
        "started_at": data.get("started_at", ""),
        "last_export_at": data.get("last_export_at", ""),
        "last_snapshot_id": data.get("last_snapshot_id", ""),
        "status": data.get("status", "active"),
    }
    return StudySessionState(**normalized)


def save_session_state(repo_root: Path, state: StudySessionState) -> Path:
    path = state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def clear_session_state(repo_root: Path) -> None:
    path = state_path(repo_root)
    if path.exists():
        path.unlink()


def export_dir_for_account(config: StudyConfig, account: StudyAccountProfile, override: str = "") -> Path:
    if override:
        return (config.repo_root / override).resolve() if not Path(override).is_absolute() else Path(override)
    root = config.repo_root / config.default_export_root
    return root / account.export_subdir


def save_path_for_account(config: StudyConfig, account: StudyAccountProfile, override: str = "") -> Path:
    selected = override or account.save_path or config.default_save_path
    if selected:
        return Path(selected).expanduser()
    detected = find_save_directory()
    if detected is None:
        raise StudySessionError(
            "Kein Save-Pfad konfiguriert und keine automatische IdleOn-Erkennung moeglich."
        )
    return detected


def save_account_for_account(config: StudyConfig, account: StudyAccountProfile, override: str = "") -> str:
    return (override or account.save_account or config.default_save_account).strip()


def session_state_path(repo_root: Path) -> Path:
    return state_path(repo_root)


def _read_session_ids(snapshots_csv: Path) -> list[str]:
    if not snapshots_csv.exists():
        return []
    with open(snapshots_csv, encoding="utf-8", newline="") as handle:
        return [
            row.get("session_id", "")
            for row in csv.DictReader(handle)
            if row.get("session_id")
        ]


def next_session_id(account_label: str, export_dir: Path, now: Optional[datetime] = None) -> str:
    current = now or datetime.now()
    date_token = current.strftime("%Y%m%d")
    prefix = f"{account_label}-{date_token}-s"
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    max_number = 0
    for session_id in _read_session_ids(export_dir / "snapshots.csv"):
        match = pattern.match(session_id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{prefix}{max_number + 1:02d}"


def validate_tags(config: StudyConfig, tags: list[str]) -> list[str]:
    unknown = [tag for tag in tags if tag not in config.allowed_tags]
    if unknown:
        raise StudySessionError(
            f"Ungueltige Tags: {', '.join(unknown)}. Erlaubt: {', '.join(config.allowed_tags)}"
        )
    return tags


def validate_milestone_tags(config: StudyConfig, tags: list[str]) -> list[str]:
    if not tags:
        raise StudySessionError("study milestone braucht mindestens ein --tag.")
    unknown = [tag for tag in tags if tag not in config.allowed_milestone_tags]
    if unknown:
        raise StudySessionError(
            "Milestone-Tags muessen in allowed_milestone_tags stehen. "
            f"Ungueltig: {', '.join(unknown)}"
        )
    return tags


def validate_expected_characters(account: StudyAccountProfile, selected_data: dict) -> None:
    player_db = _player_database_from_selected_data(selected_data)
    actual_names = tuple(str(name) for name in player_db.keys())

    if account.expected_character_names:
        missing = [name for name in account.expected_character_names if name not in player_db]
        if missing:
            actual_display = ", ".join(actual_names) if actual_names else "keine"
            raise StudySessionError(
                "Der Save enthält nicht alle erwarteten Charaktere für dieses Studienprofil. "
                f"Fehlend: {', '.join(missing)}. Gefunden: {actual_display}."
            )

    if account.expected_character_count and len(actual_names) < account.expected_character_count:
        actual_display = ", ".join(actual_names) if actual_names else "keine"
        raise StudySessionError(
            "Der Save enthält weniger Charaktere als für dieses Studienprofil erwartet. "
            f"Erwartet: mindestens {account.expected_character_count}, gefunden: {len(actual_names)} "
            f"({actual_display})."
        )


def _perform_export(
    *,
    account: StudyAccountProfile,
    save_path: Path,
    save_account: str,
    output_dir: Path,
    append: bool,
    overwrite: bool,
    allow_empty_characters: bool,
    debug_json: bool,
    dry_run: bool,
    metadata: dict,
) -> tuple[ExportResult, str]:
    try:
        ensure_save_ready(save_path)
        raw_data = read_save_data(save_path)
    except SaveGuardError as exc:
        raise StudySessionError(str(exc)) from exc
    if not raw_data:
        raise StudySessionError("Keine Daten im Save gefunden.")
    try:
        selected_data, selected_candidate, _candidates = select_save_account(
            raw_data,
            selector=save_account,
            allow_prompt=True,
        )
    except SaveAccountSelectionError as exc:
        raise StudySessionError(str(exc)) from exc
    try:
        evaluate_save_health(selected_data)
    except SaveGuardError as exc:
        raise StudySessionError(str(exc)) from exc
    validate_expected_characters(account, selected_data)
    result = export_tidy_csvs(
        selected_data,
        output_dir=output_dir,
        source_path=str(save_path),
        append=append,
        overwrite=overwrite,
        allow_empty_characters=allow_empty_characters,
        debug_json=debug_json,
        dry_run=dry_run,
        metadata=metadata,
    )
    resolved_selector = selected_candidate.selector if selected_candidate is not None else save_account.strip()
    return result, resolved_selector


def _attach_backup_status(result: ExportResult, backup_status: dict[str, object]) -> None:
    result.backup = backup_status
    try:
        update_export_manifest_backup_status(result.manifest_path, backup_status)
    except Exception as exc:
        result.backup = {
            **backup_status,
            "manifest_error": str(exc),
        }


def _backup_success_dict(record, attempted: bool = True) -> dict[str, object]:
    return {
        "attempted": attempted,
        "success": True,
        "archive_path": str(record.archive_path),
        "created_at": record.created_at,
        "size_bytes": record.size_bytes,
    }


def _backup_failure_dict(error: Exception, attempted: bool = True) -> dict[str, object]:
    return {
        "attempted": attempted,
        "success": False,
        "error": str(error),
    }


def _run_automatic_backup(
    *,
    config: StudyConfig,
    account: StudyAccountProfile,
    result: ExportResult,
    session_state_file: Optional[Path],
) -> None:
    if result.dry_run:
        result.backup = {"attempted": False, "success": False}
        return

    try:
        record = create_study_backup(
            config=config,
            account=account,
            export_dir=result.output_dir,
            snapshot_id=result.snapshot_id,
            run_type=result.study_metadata.get("run_type", ""),
            study_group=result.study_metadata.get("study_group", ""),
            session_id=result.study_metadata.get("session_id", ""),
            session_state_path=session_state_file,
        )
        _attach_backup_status(result, _backup_success_dict(record))
    except StudyBackupError as exc:
        _attach_backup_status(result, _backup_failure_dict(exc))


def baseline_export(
    config: StudyConfig,
    *,
    account_name: str,
    notes: str = "",
    tags: Optional[list[str]] = None,
    save_path_override: str = "",
    save_account_override: str = "",
    output_dir_override: str = "",
    study_group_override: str = "",
    overwrite: bool = False,
    allow_empty_characters: bool = False,
    debug_json: bool = False,
    dry_run: bool = False,
) -> ExportResult:
    account = resolve_account(config, account_name)
    chosen_tags = validate_tags(config, tags or [])
    save_path = save_path_for_account(config, account, save_path_override)
    save_account = save_account_for_account(config, account, save_account_override)
    output_dir = export_dir_for_account(config, account, output_dir_override)
    metadata = {
        "account_label": account.account_label,
        "study_group": study_group_override or config.default_study_group,
        "session_id": "",
        "run_type": "baseline",
        "strategy_label": account.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "",
        "tags": chosen_tags,
    }
    result, _resolved_save_account = _perform_export(
        account=account,
        save_path=save_path,
        save_account=save_account,
        output_dir=output_dir,
        append=False,
        overwrite=overwrite,
        allow_empty_characters=allow_empty_characters,
        debug_json=debug_json,
        dry_run=dry_run,
        metadata=metadata,
    )
    _run_automatic_backup(
        config=config,
        account=account,
        result=result,
        session_state_file=None,
    )
    return result


def session_start(
    config: StudyConfig,
    *,
    account_name: str,
    notes: str = "",
    tags: Optional[list[str]] = None,
    save_path_override: str = "",
    save_account_override: str = "",
    output_dir_override: str = "",
    study_group_override: str = "",
    overwrite: bool = False,
    allow_empty_characters: bool = False,
    debug_json: bool = False,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> StudySessionState:
    if load_session_state(config.repo_root) is not None:
        raise StudySessionError("Es gibt bereits eine aktive Session. Beende sie erst mit study session-end.")

    account = resolve_account(config, account_name)
    del notes, tags, overwrite, allow_empty_characters, debug_json
    save_path = save_path_for_account(config, account, save_path_override)
    if not save_path.exists():
        raise StudySessionError(f"Save-Pfad existiert nicht: {save_path}")
    if not save_path.is_dir():
        raise StudySessionError(f"Save-Pfad ist kein Verzeichnis: {save_path}")
    save_account = save_account_for_account(config, account, save_account_override)
    output_dir = export_dir_for_account(config, account, output_dir_override)
    session_id = next_session_id(account.account_label, output_dir, now=now)
    started_at = (now or datetime.now()).isoformat(timespec="seconds")
    state = StudySessionState(
        account_label=account.account_label,
        strategy_label=account.strategy_label,
        study_group=study_group_override or config.default_study_group,
        session_id=session_id,
        save_path=str(save_path),
        save_account=save_account,
        export_dir=str(output_dir),
        started_at=started_at,
        last_export_at="",
        last_snapshot_id="",
    )
    if not dry_run:
        save_session_state(config.repo_root, state)
    return state


def _require_active_state(config: StudyConfig) -> StudySessionState:
    state = load_session_state(config.repo_root)
    if state is None:
        raise StudySessionError("Keine aktive Session gefunden. Starte zuerst study session-start.")
    return state


def checkpoint_export(
    config: StudyConfig,
    *,
    notes: str = "",
    playtime_minutes: Optional[int] = None,
    tags: Optional[list[str]] = None,
    allow_empty_characters: bool = False,
    debug_json: bool = False,
    dry_run: bool = False,
) -> None:
    del config, notes, playtime_minutes, tags, allow_empty_characters, debug_json, dry_run
    raise StudySessionError(
        "checkpoint ist nicht mehr Teil des empfohlenen Workflows. "
        "IdleOn liefert waehrend des Spielens keine verlaesslichen Voll-Saves. "
        "Nutze session-end nach sauberem Spielende."
    )


def milestone_export(
    config: StudyConfig,
    *,
    tags: list[str],
    notes: str = "",
    playtime_minutes: Optional[int] = None,
    allow_empty_characters: bool = False,
    debug_json: bool = False,
    dry_run: bool = False,
) -> None:
    del config, tags, notes, playtime_minutes, allow_empty_characters, debug_json, dry_run
    raise StudySessionError(
        "milestone ist nicht mehr Teil des empfohlenen Workflows. "
        "Leite Ereignisse spaeter aus baseline und session-end ab."
    )


def session_end(
    config: StudyConfig,
    *,
    notes: str = "",
    tags: Optional[list[str]] = None,
    allow_empty_characters: bool = False,
    debug_json: bool = False,
    dry_run: bool = False,
) -> tuple[ExportResult, StudySessionState]:
    state = _require_active_state(config)
    account = resolve_account(config, resolve_account_name_by_label(config, state.account_label))
    chosen_tags = validate_tags(config, tags or [])
    metadata = {
        "account_label": state.account_label,
        "study_group": state.study_group,
        "session_id": state.session_id,
        "run_type": "session_end",
        "strategy_label": state.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "",
        "tags": ["session_end", *chosen_tags],
    }
    result, _resolved_save_account = _perform_export(
        account=account,
        save_path=Path(state.save_path),
        save_account=state.save_account,
        output_dir=Path(state.export_dir),
        append=True,
        overwrite=False,
        allow_empty_characters=allow_empty_characters,
        debug_json=debug_json,
        dry_run=dry_run,
        metadata=metadata,
    )
    state.last_export_at = result.timestamp
    state.last_snapshot_id = result.snapshot_id
    if not dry_run:
        clear_session_state(config.repo_root)
    _run_automatic_backup(
        config=config,
        account=account,
        result=result,
        session_state_file=None,
    )
    return result, state


def backup_now(
    config: StudyConfig,
    *,
    account_name: str,
    include_local_config: Optional[bool] = None,
) -> BackupRecord:
    account = resolve_account(config, account_name)
    export_dir = export_dir_for_account(config, account)
    active_state = load_session_state(config.repo_root)
    session_file = None
    if active_state is not None and active_state.account_label == account.account_label:
        session_file = session_state_path(config.repo_root)
        export_dir = Path(active_state.export_dir)
    return create_backup_from_latest_export(
        config=config,
        account=account,
        export_dir=export_dir,
        include_local_config=include_local_config,
        session_state_path=session_file,
    )


def study_status(config: StudyConfig) -> StudyStatus:
    state = load_session_state(config.repo_root)
    if state is None:
        next_step = "Keine aktive Session. Nutze 'python -m idleon_reader study session-start --account <profilname>'."
        return StudyStatus(active=False, state=None, next_step=next_step)

    manifest_dir = Path(state.export_dir) / "run_manifests"
    last_manifest_path = None
    if state.last_snapshot_id:
        candidate = manifest_dir / f"{state.last_snapshot_id}.json"
        if candidate.exists():
            last_manifest_path = candidate

    return StudyStatus(
        active=True,
        state=state,
        next_step="Naechster Schritt: Spiel beenden und danach session-end ausfuehren.",
        last_manifest_path=last_manifest_path,
    )


def default_account_name(config: StudyConfig) -> str:
    if config.default_profile:
        return config.default_profile
    if len(config.accounts) == 1:
        return next(iter(config.accounts))
    raise StudyConfigError("Kein Profil gesetzt. Bitte --account angeben oder study_local.toml fuellen.")
