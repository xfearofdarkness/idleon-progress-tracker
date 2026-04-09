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
from .study_config import StudyAccountProfile, StudyConfig, StudyConfigError, resolve_account


class StudySessionError(RuntimeError):
    """Raised when a study workflow action cannot be completed."""


@dataclass
class StudySessionState:
    account_label: str
    strategy_label: str
    study_group: str
    session_id: str
    save_path: str
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


def state_dir(repo_root: Path) -> Path:
    return repo_root / ".idleon-study"


def state_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "current_session.json"


def load_session_state(repo_root: Path) -> Optional[StudySessionState]:
    path = state_path(repo_root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return StudySessionState(**data)


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


def save_path_for_account(account: StudyAccountProfile, override: str = "") -> Path:
    selected = override or account.save_path
    if selected:
        return Path(selected).expanduser()
    detected = find_save_directory()
    if detected is None:
        raise StudySessionError(
            "Kein Save-Pfad konfiguriert und keine automatische IdleOn-Erkennung moeglich."
        )
    return detected


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


def _perform_export(
    *,
    save_path: Path,
    output_dir: Path,
    append: bool,
    dry_run: bool,
    metadata: dict,
) -> ExportResult:
    if not save_path.exists():
        raise StudySessionError(f"Save-Pfad existiert nicht: {save_path}")
    if not save_path.is_dir():
        raise StudySessionError(f"Save-Pfad ist kein Verzeichnis: {save_path}")
    raw_data = read_save_data(save_path)
    if not raw_data:
        raise StudySessionError("Keine Daten im Save gefunden.")
    return export_tidy_csvs(
        raw_data,
        output_dir=output_dir,
        source_path=str(save_path),
        append=append,
        dry_run=dry_run,
        metadata=metadata,
    )


def baseline_export(
    config: StudyConfig,
    *,
    account_name: str,
    notes: str = "",
    tags: Optional[list[str]] = None,
    save_path_override: str = "",
    output_dir_override: str = "",
    study_group_override: str = "",
    dry_run: bool = False,
) -> ExportResult:
    account = resolve_account(config, account_name)
    chosen_tags = validate_tags(config, tags or [])
    save_path = save_path_for_account(account, save_path_override)
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
    return _perform_export(
        save_path=save_path,
        output_dir=output_dir,
        append=False,
        dry_run=dry_run,
        metadata=metadata,
    )


def session_start(
    config: StudyConfig,
    *,
    account_name: str,
    notes: str = "",
    tags: Optional[list[str]] = None,
    save_path_override: str = "",
    output_dir_override: str = "",
    study_group_override: str = "",
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> tuple[ExportResult, StudySessionState]:
    if load_session_state(config.repo_root) is not None:
        raise StudySessionError("Es gibt bereits eine aktive Session. Beende sie erst mit study session-end.")

    account = resolve_account(config, account_name)
    extra_tags = validate_tags(config, tags or [])
    save_path = save_path_for_account(account, save_path_override)
    output_dir = export_dir_for_account(config, account, output_dir_override)
    session_id = next_session_id(account.account_label, output_dir, now=now)
    metadata = {
        "account_label": account.account_label,
        "study_group": study_group_override or config.default_study_group,
        "session_id": session_id,
        "run_type": "checkpoint",
        "strategy_label": account.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "",
        "tags": ["session_start", *extra_tags],
    }
    result = _perform_export(
        save_path=save_path,
        output_dir=output_dir,
        append=False,
        dry_run=dry_run,
        metadata=metadata,
    )
    started_at = (now or datetime.now()).isoformat(timespec="seconds")
    state = StudySessionState(
        account_label=account.account_label,
        strategy_label=account.strategy_label,
        study_group=metadata["study_group"],
        session_id=session_id,
        save_path=str(save_path),
        export_dir=str(output_dir),
        started_at=started_at,
        last_export_at=result.timestamp,
        last_snapshot_id=result.snapshot_id,
    )
    if not dry_run:
        save_session_state(config.repo_root, state)
    return result, state


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
    dry_run: bool = False,
) -> tuple[ExportResult, StudySessionState]:
    state = _require_active_state(config)
    chosen_tags = validate_tags(config, tags or [])
    metadata = {
        "account_label": state.account_label,
        "study_group": state.study_group,
        "session_id": state.session_id,
        "run_type": "checkpoint",
        "strategy_label": state.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "" if playtime_minutes is None else playtime_minutes,
        "tags": chosen_tags,
    }
    result = _perform_export(
        save_path=Path(state.save_path),
        output_dir=Path(state.export_dir),
        append=True,
        dry_run=dry_run,
        metadata=metadata,
    )
    state.last_export_at = result.timestamp
    state.last_snapshot_id = result.snapshot_id
    if not dry_run:
        save_session_state(config.repo_root, state)
    return result, state


def milestone_export(
    config: StudyConfig,
    *,
    tags: list[str],
    notes: str = "",
    playtime_minutes: Optional[int] = None,
    dry_run: bool = False,
) -> tuple[ExportResult, StudySessionState]:
    state = _require_active_state(config)
    chosen_tags = validate_milestone_tags(config, tags)
    metadata = {
        "account_label": state.account_label,
        "study_group": state.study_group,
        "session_id": state.session_id,
        "run_type": "milestone",
        "strategy_label": state.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "" if playtime_minutes is None else playtime_minutes,
        "tags": chosen_tags,
    }
    result = _perform_export(
        save_path=Path(state.save_path),
        output_dir=Path(state.export_dir),
        append=True,
        dry_run=dry_run,
        metadata=metadata,
    )
    state.last_export_at = result.timestamp
    state.last_snapshot_id = result.snapshot_id
    if not dry_run:
        save_session_state(config.repo_root, state)
    return result, state


def session_end(
    config: StudyConfig,
    *,
    notes: str = "",
    playtime_minutes: Optional[int] = None,
    tags: Optional[list[str]] = None,
    dry_run: bool = False,
) -> tuple[ExportResult, StudySessionState]:
    state = _require_active_state(config)
    chosen_tags = validate_tags(config, tags or [])
    metadata = {
        "account_label": state.account_label,
        "study_group": state.study_group,
        "session_id": state.session_id,
        "run_type": "session_end",
        "strategy_label": state.strategy_label,
        "notes": notes,
        "playtime_minutes_since_last_snapshot": "" if playtime_minutes is None else playtime_minutes,
        "tags": ["session_end", *chosen_tags],
    }
    result = _perform_export(
        save_path=Path(state.save_path),
        output_dir=Path(state.export_dir),
        append=True,
        dry_run=dry_run,
        metadata=metadata,
    )
    state.last_export_at = result.timestamp
    state.last_snapshot_id = result.snapshot_id
    if not dry_run:
        clear_session_state(config.repo_root)
    return result, state


def study_status(config: StudyConfig) -> StudyStatus:
    state = load_session_state(config.repo_root)
    if state is None:
        next_step = "Keine aktive Session. Nutze 'python -m idleon_reader study session-start --account A_speed'."
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
        next_step="Naechster Schritt: checkpoint, milestone oder session-end.",
        last_manifest_path=last_manifest_path,
    )


def default_account_name(config: StudyConfig) -> str:
    if config.default_account:
        return config.default_account
    if len(config.accounts) == 1:
        return next(iter(config.accounts))
    raise StudyConfigError("Kein default_account gesetzt. Bitte --account angeben oder study_local.toml fuellen.")
