#!/usr/bin/env python3
"""
IdleOn Progress Tracker - Main CLI Entry Point

Extracts player progress from local Legends of Idleon save files
without modifying the game data.

Usage:
    python -m idleon_reader                    # Auto-detect save location
    python -m idleon_reader --path /path/to/db # Specify LevelDB path
    python -m idleon_reader --json             # Export raw data as JSON
    python -m idleon_reader --json --output save_data.json
    python -m idleon_reader --csv exports/a --account-label A_speed --tag baseline
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .finder import find_save_directory, get_save_info
from .ldb_reader import read_save_data
from .progress import extract_progress_summary, format_progress_report
from .export_tidy import ExportValidationError, RUN_TYPE_CHOICES, export_tidy_csvs


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("muss eine ganze Zahl sein") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("muss groesser oder gleich 0 sein")
    return parsed


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idleon-progress-tracker",
        description=(
            "Extrahiert Spielerfortschritt aus lokalen Legends of Idleon "
            "Speicherdateien, ohne das Spiel zu modifizieren."
        ),
        epilog=(
            "Beispiele:\n"
            "  python -m idleon_reader                       Auto-Erkennung\n"
            "  python -m idleon_reader --path ~/mein-backup  Pfad angeben\n"
            "  python -m idleon_reader --json -o daten.json  JSON-Export\n"
            "  python -m idleon_reader --info                Speicherort-Info\n"
            "  python -m idleon_reader --csv exports/a --account-label A_speed --tag baseline\n"
            "  python -m idleon_reader --csv exports/a --dry-run --session-id s01\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path", "-p",
        type=Path,
        default=None,
        help="Pfad zum LevelDB-Verzeichnis (Standard: automatische Erkennung)",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Rohdaten als JSON ausgeben statt formatiertem Bericht",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Ausgabe in Datei schreiben statt auf die Konsole",
    )
    parser.add_argument(
        "--info", "-i",
        action="store_true",
        help="Zeige Informationen ueber den Speicherort an",
    )
    parser.add_argument(
        "--raw-keys",
        action="store_true",
        help="Zeige alle Rohdaten-Schluessel mit Typ-Information",
    )
    parser.add_argument(
        "--key", "-k",
        type=str,
        default=None,
        help="Extrahiere nur einen bestimmten Schluessel aus den Speicherdaten",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        metavar="DIR",
        help="Exportiere tidy CSVs fuer R-Analyse in das angegebene Verzeichnis",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="An bestehende CSVs anhaengen statt ueberschreiben (fuer Zeitreihen)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Baue den CSV-Export in-memory und pruefe ihn, ohne Dateien zu schreiben",
    )
    parser.add_argument(
        "--account-label",
        type=str,
        default="",
        help="Stabiles Studien-Label fuer den exportierten Account",
    )
    parser.add_argument(
        "--study-group",
        type=str,
        default="",
        help="Optionale Studiengruppe oder Kohorte fuer den Snapshot",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default="",
        help="Optionale Session-ID fuer den Snapshot",
    )
    parser.add_argument(
        "--run-type",
        type=str,
        choices=RUN_TYPE_CHOICES,
        default="",
        help="Optionale Klassifikation des Snapshot-Laufs",
    )
    parser.add_argument(
        "--strategy-label",
        type=str,
        default="",
        help="Optionales Label fuer die gespielte Strategie",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default="",
        help="Freitextnotiz fuer den Exportlauf",
    )
    parser.add_argument(
        "--playtime-minutes",
        type=_non_negative_int,
        default=None,
        help="Geschaetzte Spielzeit seit dem letzten Snapshot in Minuten",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Wiederholbares Event- oder Milestone-Tag fuer den Snapshot",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ausfuehrliche Ausgabe",
    )
    return parser


def cmd_info():
    """Show save file location information."""
    print("=" * 60)
    print("  IdleOn Speicherdaten - Standort-Information")
    print("=" * 60)

    info = get_save_info()

    print(f"  Betriebssystem:    {info['os']}")
    print()

    if info["save_found"]:
        print(f"  Speicherort:       {info['save_directory']}")
        print(f"  Dateien gefunden:  {info.get('ldb_file_count', 0)}")
        print(f"  Gesamtgroesse:     {info.get('total_size_kb', 0)} KB")
        print()
        if info.get("ldb_files"):
            print("  Dateien:")
            for f in info["ldb_files"]:
                print(f"    {f}")
    else:
        print("  [!] Kein Speicherort gefunden!")
        print()
        print("  Moegliche Ursachen:")
        print("    - IdleOn (Steam-Version) ist nicht installiert")
        print("    - Das Spiel wurde noch nie lokal gestartet")
        print("    - Die Speicherdaten liegen an einem anderen Ort")
        print()
        print("  Du kannst den Pfad manuell angeben mit: --path /pfad/zum/leveldb")

    if info["installation_found"]:
        print(f"\n  Installation:      {info['installation_directory']}")

    print()
    print("=" * 60)


def cmd_read(args):
    """Read and display save data."""
    # Find or validate the save directory
    db_path = args.path
    if db_path is None:
        print("[*] Suche IdleOn-Speicherdaten...")
        db_path = find_save_directory()
        if db_path is None:
            print("[!] Fehler: Konnte keine IdleOn-Speicherdaten finden.")
            print("    Bitte gib den Pfad manuell an: --path /pfad/zum/leveldb")
            sys.exit(1)
        print(f"[*] Gefunden: {db_path}")
    else:
        if not db_path.exists():
            print(f"[!] Fehler: Pfad existiert nicht: {db_path}")
            sys.exit(1)
        if not db_path.is_dir():
            print(f"[!] Fehler: Pfad ist kein Verzeichnis: {db_path}")
            sys.exit(1)

    # Read the data
    print("[*] Lese Speicherdaten...")
    try:
        raw_data = read_save_data(db_path)
    except Exception as e:
        print(f"[!] Fehler beim Lesen der Daten: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    if not raw_data:
        print("[!] Keine Daten gefunden in der Datenbank.")
        print("    Moeglicherweise ist die Datenbank leer oder in einem unbekannten Format.")
        sys.exit(1)

    print(f"[*] {len(raw_data)} Schluessel gelesen.")

    # Handle --raw-keys
    if args.raw_keys:
        print("\n  Gefundene Schluessel:")
        for key in sorted(raw_data.keys()):
            val = raw_data[key]
            type_info = type(val).__name__
            size_info = ""
            if isinstance(val, (list, dict)):
                size_info = f" ({len(val)} Eintraege)"
            elif isinstance(val, str):
                size_info = f" ({len(val)} Zeichen)"
            print(f"    {key:40s} [{type_info}{size_info}]")
        return

    # Handle --key
    if args.key:
        if args.key in raw_data:
            value = raw_data[args.key]
            if args.json:
                output = json.dumps(value, indent=2, ensure_ascii=False, default=str)
            else:
                output = str(value)
            _write_output(output, args.output)
        else:
            print(f"[!] Schluessel '{args.key}' nicht gefunden.")
            print(f"    Verfuegbare Schluessel: {', '.join(sorted(raw_data.keys()))}")
            sys.exit(1)
        return

    export_flags_used = any([
        args.append,
        args.dry_run,
        args.account_label,
        args.study_group,
        args.session_id,
        args.run_type,
        args.strategy_label,
        args.notes,
        args.playtime_minutes is not None,
        bool(args.tag),
    ])
    if export_flags_used and not args.csv:
        print("[!] Fehler: Studien- und Export-Flags koennen nur zusammen mit --csv DIR verwendet werden.")
        sys.exit(1)

    # Handle --csv (tidy export)
    if args.csv:
        action = "Pruefe tidy CSV-Export" if args.dry_run else "Exportiere tidy CSVs"
        print(f"[*] {action}: {args.csv}/")
        source = str(db_path)
        metadata = {
            "account_label": args.account_label,
            "study_group": args.study_group,
            "session_id": args.session_id,
            "run_type": args.run_type,
            "strategy_label": args.strategy_label,
            "notes": args.notes,
            "playtime_minutes_since_last_snapshot": (
                "" if args.playtime_minutes is None else args.playtime_minutes
            ),
            "tags": args.tag,
        }
        try:
            result = export_tidy_csvs(
                raw_data,
                output_dir=args.csv,
                source_path=source,
                append=args.append,
                metadata=metadata,
                dry_run=args.dry_run,
            )
        except ExportValidationError as exc:
            print(f"[!] Export-Validierung fehlgeschlagen: {exc}")
            if exc.validation_results:
                for validation in exc.validation_results:
                    status = "OK" if validation["passed"] else "FEHLER"
                    print(f"    [{status}] {validation['name']}: {validation['message']}")
            sys.exit(1)
        except Exception as exc:
            print(f"[!] Fehler beim CSV-Export: {exc}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        _print_export_summary(result)
        return

    # Handle --json (raw export)
    if args.json:
        print("[*] Exportiere Rohdaten als JSON...")
        output = json.dumps(raw_data, indent=2, ensure_ascii=False, default=str)
        _write_output(output, args.output)
        if args.output:
            print(f"[*] Daten exportiert nach: {args.output}")
        return

    # Default: formatted progress report
    print("[*] Analysiere Spielerfortschritt...")
    summary = extract_progress_summary(raw_data)
    report = format_progress_report(summary)
    _write_output(report, args.output)

    if args.output:
        print(f"[*] Bericht exportiert nach: {args.output}")

    # Also save the JSON summary alongside if output is specified
    if args.output:
        json_path = args.output.with_suffix(".json")
        json_output = json.dumps(summary, indent=2, ensure_ascii=False, default=str)
        json_path.write_text(json_output, encoding="utf-8")
        print(f"[*] JSON-Zusammenfassung: {json_path}")


def _write_output(content: str, output_path: Optional[Path] = None):
    """Write content to file or stdout."""
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    else:
        print(content)


def _print_export_summary(result):
    mode = "dry-run" if result.dry_run else ("append" if result.append else "write")
    validation_ok = all(entry["passed"] for entry in result.validation)

    print(f"[*] Snapshot-ID: {result.snapshot_id}")
    print(f"[*] Modus:       {mode}")
    print(f"[*] Exportpfad:  {result.output_dir}/")
    print(f"[*] Save-Pfad:   {result.source_path}")
    if result.study_metadata["account_label"]:
        print(f"[*] Account:     {result.study_metadata['account_label']}")
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

    if result.warnings:
        print("[*] Warnungen:")
        for warning in result.warnings:
            print(f"    - {warning}")


def main(argv: Optional[list[str]] = None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "study":
        from .study_cli import run_study_cli

        sys.exit(run_study_cli(argv[1:]))

    parser = create_parser()
    args = parser.parse_args(argv)

    if args.info:
        cmd_info()
    else:
        cmd_read(args)


if __name__ == "__main__":
    main()
