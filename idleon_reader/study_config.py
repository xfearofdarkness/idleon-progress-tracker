"""Study workflow configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


class StudyConfigError(RuntimeError):
    """Raised when the study configuration is missing or invalid."""


@dataclass(frozen=True)
class StudyAccountProfile:
    account_label: str
    strategy_label: str
    export_subdir: str
    save_path: str = ""
    save_account: str = ""


@dataclass(frozen=True)
class StudyConfig:
    repo_root: Path
    default_export_root: str
    default_study_group: str
    allowed_tags: tuple[str, ...]
    allowed_milestone_tags: tuple[str, ...]
    allowed_run_types: tuple[str, ...]
    default_account: str
    accounts: dict[str, StudyAccountProfile]
    profiles_path: Path
    local_path: Path


DEFAULT_ALLOWED_TAGS = (
    "baseline",
    "session_start",
    "session_end",
    "reached_level_5",
    "reached_level_10",
    "reached_level_20",
    "class_advance",
    "quest_milestone",
    "boss_unlock",
)

DEFAULT_ALLOWED_MILESTONE_TAGS = (
    "reached_level_5",
    "reached_level_10",
    "reached_level_20",
    "class_advance",
    "quest_milestone",
    "boss_unlock",
)

DEFAULT_ALLOWED_RUN_TYPES = ("baseline", "checkpoint", "session_end", "milestone")


def repo_root_from_path(start: Optional[Path] = None) -> Path:
    base = start if start is not None else Path(__file__).resolve().parent.parent
    return base.resolve()


def profiles_template() -> str:
    return """[study]
default_export_root = "exports/study"
default_study_group = "main"
allowed_tags = [
  "baseline",
  "session_start",
  "session_end",
  "reached_level_5",
  "reached_level_10",
  "reached_level_20",
  "class_advance",
  "quest_milestone",
  "boss_unlock",
]
allowed_milestone_tags = [
  "reached_level_5",
  "reached_level_10",
  "reached_level_20",
  "class_advance",
  "quest_milestone",
  "boss_unlock",
]
allowed_run_types = ["baseline", "checkpoint", "session_end", "milestone"]

[accounts.A_speed]
account_label = "A_speed"
strategy_label = "speed"
export_subdir = "A_speed"

[accounts.B_skills]
account_label = "B_skills"
strategy_label = "skills"
export_subdir = "B_skills"

[accounts.C_balanced]
account_label = "C_balanced"
strategy_label = "balanced"
export_subdir = "C_balanced"
"""


def local_template() -> str:
    return """[local]
# Optional default account on this machine
default_account = "A_speed"

[accounts.A_speed]
# save_path = "/absolute/path/to/leveldb"
# save_account = "mySave"

[accounts.B_skills]
# save_path = "/absolute/path/to/leveldb"
# save_account = "mySave"

[accounts.C_balanced]
# save_path = "/absolute/path/to/leveldb"
# save_account = "mySave"
"""


def ensure_example_files(repo_root: Path) -> dict[str, Path]:
    created: dict[str, Path] = {}
    templates = {
        "study_profiles.toml.example": profiles_template(),
        "study_local.toml.example": local_template(),
    }
    for filename, content in templates.items():
        path = repo_root / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created[filename] = path
    return created


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StudyConfigError(f"Konfigurationsdatei fehlt: {path.name}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise StudyConfigError(f"Konfigurationsdatei ist ungueltig: {path.name}: {exc}") from exc


def load_study_config(repo_root: Optional[Path] = None) -> StudyConfig:
    root = repo_root_from_path(repo_root)
    profiles_path = root / "study_profiles.toml"
    local_path = root / "study_local.toml"

    profiles_data = _read_toml(profiles_path)
    local_data = _read_toml(local_path) if local_path.exists() else {}

    study_data = profiles_data.get("study")
    if not isinstance(study_data, dict):
        raise StudyConfigError("study_profiles.toml braucht einen [study]-Block.")

    accounts_data = profiles_data.get("accounts")
    if not isinstance(accounts_data, dict) or not accounts_data:
        raise StudyConfigError("study_profiles.toml braucht mindestens ein [accounts.<name>]-Profil.")

    local_accounts = local_data.get("accounts") if isinstance(local_data.get("accounts"), dict) else {}
    local_defaults = local_data.get("local") if isinstance(local_data.get("local"), dict) else {}

    allowed_tags = tuple(str(value) for value in study_data.get("allowed_tags", DEFAULT_ALLOWED_TAGS))
    allowed_milestone_tags = tuple(
        str(value) for value in study_data.get("allowed_milestone_tags", DEFAULT_ALLOWED_MILESTONE_TAGS)
    )
    allowed_run_types = tuple(
        str(value) for value in study_data.get("allowed_run_types", DEFAULT_ALLOWED_RUN_TYPES)
    )

    required_run_types = {"baseline", "checkpoint", "session_end", "milestone"}
    if not required_run_types.issubset(set(allowed_run_types)):
        raise StudyConfigError(
            "study_profiles.toml muss baseline, checkpoint, session_end und milestone in allowed_run_types enthalten."
        )

    if not set(allowed_milestone_tags).issubset(set(allowed_tags)):
        raise StudyConfigError("allowed_milestone_tags muessen Teilmenge von allowed_tags sein.")

    accounts: dict[str, StudyAccountProfile] = {}
    for profile_name, account_data in accounts_data.items():
        if not isinstance(account_data, dict):
            raise StudyConfigError(f"Profil '{profile_name}' ist ungueltig.")
        account_label = str(account_data.get("account_label", "")).strip()
        strategy_label = str(account_data.get("strategy_label", "")).strip()
        export_subdir = str(account_data.get("export_subdir", "")).strip()
        if not account_label or not strategy_label or not export_subdir:
            raise StudyConfigError(
                f"Profil '{profile_name}' braucht account_label, strategy_label und export_subdir."
            )
        local_profile = local_accounts.get(profile_name, {})
        save_path = ""
        save_account = ""
        if isinstance(local_profile, dict):
            save_path = str(local_profile.get("save_path", "")).strip()
            save_account = str(local_profile.get("save_account", "")).strip()
        accounts[profile_name] = StudyAccountProfile(
            account_label=account_label,
            strategy_label=strategy_label,
            export_subdir=export_subdir,
            save_path=save_path,
            save_account=save_account,
        )

    default_account = str(local_defaults.get("default_account", "")).strip()
    if default_account and default_account not in accounts:
        raise StudyConfigError(f"default_account '{default_account}' ist nicht in study_profiles.toml definiert.")

    return StudyConfig(
        repo_root=root,
        default_export_root=str(study_data.get("default_export_root", "exports/study")),
        default_study_group=str(study_data.get("default_study_group", "main")),
        allowed_tags=allowed_tags,
        allowed_milestone_tags=allowed_milestone_tags,
        allowed_run_types=allowed_run_types,
        default_account=default_account,
        accounts=accounts,
        profiles_path=profiles_path,
        local_path=local_path,
    )


def resolve_account(config: StudyConfig, account_name: str) -> StudyAccountProfile:
    try:
        return config.accounts[account_name]
    except KeyError as exc:
        known = ", ".join(sorted(config.accounts))
        raise StudyConfigError(f"Unbekannter Account '{account_name}'. Verfuegbar: {known}") from exc
