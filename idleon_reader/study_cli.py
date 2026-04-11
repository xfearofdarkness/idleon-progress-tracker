"""Study workflow CLI built on top of the export core."""

from __future__ import annotations

import argparse
from pathlib import Path

from .export_tidy import ExportResult
from .study_backup import StudyBackupError, list_study_backups, restore_study_backup
from .study_config import (
    StudyConfigError,
    ensure_example_files,
    load_study_config,
    repo_root_from_path,
    resolve_account,
    resolve_account_name_by_label,
)
from .study_session import (
    StudySessionError,
    backup_now,
    baseline_export,
    checkpoint_export,
    load_session_state,
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

    backup_parser = subparsers.add_parser("backup-now", help="Erzeuge sofort ein Backup des aktuellen Study-Exports.")
    backup_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    backup_parser.add_argument(
        "--no-local-config",
        action="store_true",
        help="Schliesse study_local.toml fuer dieses Backup aus.",
    )
    backup_parser.set_defaults(handler=cmd_backup_now)

    list_parser = subparsers.add_parser("list-backups", help="Zeige vorhandene Study-Backups an.")
    list_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    list_parser.set_defaults(handler=cmd_list_backups)

    restore_parser = subparsers.add_parser("restore-backup", help="Stelle ein Study-Backup in einem Zielordner wieder her.")
    restore_parser.add_argument("archive", type=Path, help="Pfad zum ZIP-Archiv.")
    restore_parser.add_argument("--output-dir", type=Path, default=None, help="Optionaler Zielordner fuer den Restore.")
    restore_parser.add_argument("--overwrite", action="store_true", help="Vorhandenen Zielordner bewusst ersetzen.")
    restore_parser.set_defaults(handler=cmd_restore_backup)

    baseline_parser = subparsers.add_parser("baseline", help="Schreibe einen Baseline-Snapshot fuer einen Studienaccount.")
    baseline_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    _add_shared_export_arguments(baseline_parser, allow_playtime=False, allow_overwrite=True)
    baseline_parser.set_defaults(handler=cmd_baseline)

    session_start_parser = subparsers.add_parser("session-start", help="Starte eine Session und schreibe den ersten Snapshot.")
    session_start_parser.add_argument("--account", default="", help="Profilname aus study_profiles.toml.")
    _add_shared_export_arguments(session_start_parser, allow_playtime=False, allow_overwrite=True)
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
    allow_overwrite: bool = False,
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
    if allow_overwrite:
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Vorhandene Exportdateien in diesem Account-Ordner bewusst ersetzen.",
        )
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
    except (StudyConfigError, StudySessionError, StudyBackupError) as exc:
        print(f"[!] {exc}")
        return 1


def cmd_init_config(args: argparse.Namespace) -> int:
    del args
    repo_root = repo_root_from_path()
    created = ensure_example_files(repo_root)

    profiles_path = repo_root / "study_profiles.toml"
    if not profiles_path.exists():
        example = repo_root / "study_profiles.toml.example"
        profiles_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        created["study_profiles.toml"] = profiles_path

    local_path = repo_root / "study_local.toml"
    if not local_path.exists():
        example = repo_root / "study_local.toml.example"
        local_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        created["study_local.toml"] = local_path

    config = load_study_config(repo_root)

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


def _resolve_backup_account_name(config, account_name: str) -> str:
    if account_name:
        return account_name
    active_state = load_session_state(config.repo_root)
    if active_state is not None:
        return resolve_account_name_by_label(config, active_state.account_label)
    return default_account_name(config)


def cmd_backup_now(args: argparse.Namespace) -> int:
    config = load_study_config()
    account_name = _resolve_backup_account_name(config, args.account)
    record = backup_now(
        config,
        account_name=account_name,
        include_local_config=False if args.no_local_config else None,
    )
    print("[*] Backup erstellt")
    print(f"    Account: {record.account_label}")
    print(f"    Run-Type: {record.run_type}")
    print(f"    Snapshot-ID: {record.snapshot_id}")
    print(f"    Archiv: {record.archive_path}")
    print(f"    Groesse: {record.size_bytes} Bytes")
    return 0


def cmd_list_backups(args: argparse.Namespace) -> int:
    config = load_study_config()
    account_label = ""
    if args.account:
        account_label = resolve_account(config, args.account).account_label
    records, warnings = list_study_backups(config, account_label=account_label)
    if not records:
        print("[*] Keine Backups gefunden.")
    else:
        print("[*] Study-Backups")
        for record in records:
            print(
                f"    {record.created_at}  {record.account_label:15s}  "
                f"{record.run_type or '-':12s}  {record.snapshot_id:12s}  {record.size_bytes:>8} B"
            )
            print(f"      {record.archive_path}")
    if warnings:
        print("[*] Warnungen:")
        for warning in warnings:
            print(f"    - {warning}")
    return 0


def cmd_restore_backup(args: argparse.Namespace) -> int:
    result = restore_study_backup(
        repo_root=repo_root_from_path(),
        archive_path=args.archive,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )
    print("[*] Backup wiederhergestellt")
    print(f"    Archiv: {result.archive_path}")
    print(f"    Ziel:   {result.output_dir}")
    print(f"    Account: {result.backup_record.account_label}")
    print(f"    Snapshot-ID: {result.backup_record.snapshot_id}")
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
        overwrite=getattr(args, "overwrite", False),
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
        overwrite=getattr(args, "overwrite", False),
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
    validation_ok = all(entry["passed"] for entry in result.validation)

    print(f"[*] Snapshot-ID: {result.snapshot_id}")
    print(f"[*] Modus:       {'dry-run' if result.dry_run else result.mode}")
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
        if result.backup:
            if result.backup.get("success"):
                print("[*] Backup:        OK")
                print(f"[*] Archiv:        {result.backup.get('archive_path', '')}")
                if "size_bytes" in result.backup:
                    print(f"[*] Groesse:       {result.backup['size_bytes']} Bytes")
            elif result.backup.get("attempted"):
                print("[*] Backup:        FEHLER")
                print(f"[!] Backup konnte nicht geschrieben werden: {result.backup.get('error', '')}")
                print("[!] Exportdaten wurden trotzdem erfolgreich geschrieben.")
