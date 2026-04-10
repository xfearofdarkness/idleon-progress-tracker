"""Study workflow CLI built on top of the export core."""

from __future__ import annotations

import argparse

from .export_tidy import ExportResult
from .study_config import StudyConfigError, ensure_example_files, load_study_config
from .study_session import (
    StudySessionError,
    baseline_export,
    checkpoint_export,
    default_account_name,
    milestone_export,
    session_end,
    session_start,
    study_status,
)


def create_study_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idleon-progress-tracker study",
        description="Gefuehrter Studien-Workflow fuer IdleOn-Exports.",
    )
    subparsers = parser.add_subparsers(dest="study_command", required=True)

    init_parser = subparsers.add_parser("init-config", help="Erzeuge Beispiel- und lokale Studien-Konfigurationsdateien.")
    init_parser.set_defaults(handler=cmd_init_config)

    status_parser = subparsers.add_parser("status", help="Zeige den aktiven Session-Kontext an.")
    status_parser.set_defaults(handler=cmd_status)

    baseline_parser = subparsers.add_parser("baseline", help="Schreibe einen Baseline-Snapshot fuer einen Studienaccount.")
    baseline_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    _add_shared_export_arguments(baseline_parser, allow_playtime=False)
    baseline_parser.set_defaults(handler=cmd_baseline)

    session_start_parser = subparsers.add_parser("session-start", help="Starte eine Session und schreibe den ersten Snapshot.")
    session_start_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    _add_shared_export_arguments(session_start_parser, allow_playtime=False)
    session_start_parser.set_defaults(handler=cmd_session_start)

    checkpoint_parser = subparsers.add_parser("checkpoint", help="Schreibe einen Checkpoint fuer die aktive Session.")
    _add_shared_export_arguments(
        checkpoint_parser,
        allow_save_path=False,
        allow_save_account=False,
        allow_output_dir=False,
        allow_study_group=False,
    )
    checkpoint_parser.set_defaults(handler=cmd_checkpoint)

    milestone_parser = subparsers.add_parser("milestone", help="Schreibe einen Milestone-Snapshot fuer die aktive Session.")
    _add_shared_export_arguments(
        milestone_parser,
        allow_save_path=False,
        allow_save_account=False,
        allow_output_dir=False,
        allow_study_group=False,
    )
    milestone_parser.set_defaults(handler=cmd_milestone)

    session_end_parser = subparsers.add_parser("session-end", help="Beende die aktive Session mit dem letzten Snapshot.")
    _add_shared_export_arguments(
        session_end_parser,
        allow_save_path=False,
        allow_save_account=False,
        allow_output_dir=False,
        allow_study_group=False,
    )
    session_end_parser.set_defaults(handler=cmd_session_end)

    return parser


def _add_shared_export_arguments(
    parser: argparse.ArgumentParser,
    *,
    allow_playtime: bool = True,
    allow_save_path: bool = True,
    allow_save_account: bool = True,
    allow_output_dir: bool = True,
    allow_study_group: bool = True,
) -> None:
    if allow_save_path:
        parser.add_argument("--save-path", default="", help="Optionaler Override fuer den Save-Pfad.")
    if allow_save_account:
        parser.add_argument(
            "--save-account",
            default="",
            help="Optionaler selector oder Index, falls ein Save mehrere Accounts enthaelt.",
        )
    if allow_output_dir:
        parser.add_argument("--output-dir", default="", help="Optionaler Override fuer den Zielordner.")
    if allow_study_group:
        parser.add_argument("--study-group", default="", help="Optionaler Override fuer die Studiengruppe.")
    parser.add_argument("--notes", default="", help="Freitextnotiz fuer diesen Export.")
    parser.add_argument("--tag", action="append", default=[], help="Zusatz-Tag fuer den Export.")
    parser.add_argument("--dry-run", action="store_true", help="Validiere und zeige den Export, ohne Dateien zu schreiben.")
    if allow_playtime:
        parser.add_argument(
            "--playtime-minutes",
            type=_non_negative_int,
            default=None,
            help="Geschaetzte Spielzeit seit dem letzten Snapshot in Minuten.",
        )


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("muss groesser oder gleich 0 sein")
    return parsed


def run_study_cli(argv: list[str]) -> int:
    parser = create_study_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (StudyConfigError, StudySessionError) as exc:
        print(f"[!] {exc}")
        return 1


def cmd_init_config(args: argparse.Namespace) -> int:
    del args
    config = load_study_config()
    created = ensure_example_files(config.repo_root)

    local_path = config.repo_root / "study_local.toml"
    if not local_path.exists():
        example = config.repo_root / "study_local.toml.example"
        local_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        created["study_local.toml"] = local_path

    print("[*] Studien-Konfiguration:")
    print(f"    Profile: {config.profiles_path}")
    print(f"    Lokal:   {config.local_path}")
    if created:
        print("[*] Erstellt:")
        for path in created.values():
            print(f"    {path}")
    else:
        print("[*] Keine neuen Dateien noetig.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    del args
    config = load_study_config()
    status = study_status(config)
    print("[*] Studien-Status")
    if not status.active or status.state is None:
        print("    Session: keine aktiv")
        print(f"    Hinweis: {status.next_step}")
        return 0

    state = status.state
    print("    Session: aktiv")
    print(f"    Account: {state.account_label}")
    print(f"    Strategie: {state.strategy_label}")
    print(f"    Studiengruppe: {state.study_group}")
    print(f"    Session-ID: {state.session_id}")
    print(f"    Save-Pfad: {state.save_path}")
    if state.save_account:
        print(f"    Save-Account: {state.save_account}")
    print(f"    Exportpfad: {state.export_dir}")
    print(f"    Gestartet: {state.started_at}")
    print(f"    Letzter Export: {state.last_export_at}")
    print(f"    Letzte Snapshot-ID: {state.last_snapshot_id}")
    if status.last_manifest_path:
        print(f"    Letztes Manifest: {status.last_manifest_path}")
    print(f"    Naechster Schritt: {status.next_step}")
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    config = load_study_config()
    account_name = args.account or default_account_name(config)
    result = baseline_export(
        config,
        account_name=account_name,
        notes=args.notes,
        tags=args.tag,
        save_path_override=args.save_path,
        save_account_override=args.save_account,
        output_dir_override=args.output_dir,
        study_group_override=args.study_group,
        dry_run=args.dry_run,
    )
    _print_export_summary(result)
    if args.save_account:
        print(f"[*] Save-Account: {args.save_account}")
    return 0


def cmd_session_start(args: argparse.Namespace) -> int:
    config = load_study_config()
    account_name = args.account or default_account_name(config)
    result, state = session_start(
        config,
        account_name=account_name,
        notes=args.notes,
        tags=args.tag,
        save_path_override=args.save_path,
        save_account_override=args.save_account,
        output_dir_override=args.output_dir,
        study_group_override=args.study_group,
        dry_run=args.dry_run,
    )
    _print_export_summary(result)
    if state.save_account:
        print(f"[*] Save-Account: {state.save_account}")
    if not args.dry_run:
        print(f"[*] Aktive Session: {state.session_id}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    config = load_study_config()
    result, _state = checkpoint_export(
        config,
        notes=args.notes,
        playtime_minutes=args.playtime_minutes,
        tags=args.tag,
        dry_run=args.dry_run,
    )
    _print_export_summary(result)
    return 0


def cmd_milestone(args: argparse.Namespace) -> int:
    config = load_study_config()
    result, _state = milestone_export(
        config,
        tags=args.tag,
        notes=args.notes,
        playtime_minutes=args.playtime_minutes,
        dry_run=args.dry_run,
    )
    _print_export_summary(result)
    return 0


def cmd_session_end(args: argparse.Namespace) -> int:
    config = load_study_config()
    result, state = session_end(
        config,
        notes=args.notes,
        playtime_minutes=args.playtime_minutes,
        tags=args.tag,
        dry_run=args.dry_run,
    )
    _print_export_summary(result)
    if not args.dry_run:
        print(f"[*] Session beendet: {state.session_id}")
    return 0


def _print_export_summary(result: ExportResult) -> None:
    mode = "dry-run" if result.dry_run else ("append" if result.append else "write")
    validation_ok = all(entry["passed"] for entry in result.validation)

    print(f"[*] Snapshot-ID: {result.snapshot_id}")
    print(f"[*] Modus:       {mode}")
    print(f"[*] Exportpfad:  {result.output_dir}/")
    print(f"[*] Save-Pfad:   {result.source_path}")
    if result.study_metadata["account_label"]:
        print(f"[*] Account:     {result.study_metadata['account_label']}")
    if result.study_metadata["session_id"]:
        print(f"[*] Session-ID:  {result.study_metadata['session_id']}")
    print(f"[*] Validierung: {'OK' if validation_ok else 'FEHLER'}")
    print("[*] Tabellen:")
    for table_name in sorted(result.table_row_counts):
        print(f"    {table_name + '.csv':20s} {result.table_row_counts[table_name]:>5} neue Zeilen")
    if result.dry_run:
        print("[*] No files written (--dry-run).")
    else:
        print(f"[*] Dokumentation: {result.output_dir}/data_dictionary.csv")
        if result.manifest_path:
            print(f"[*] Manifest:      {result.manifest_path}")
