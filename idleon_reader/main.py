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
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .finder import find_save_directory, get_save_info
from .ldb_reader import read_save_data
from .progress import extract_progress_summary, format_progress_report
from .export_tidy import export_tidy_csvs


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

    # Handle --csv (tidy export for R)
    if args.csv:
        print(f"[*] Exportiere tidy CSVs nach: {args.csv}/")
        source = str(db_path)
        paths = export_tidy_csvs(
            raw_data,
            output_dir=args.csv,
            source_path=source,
            append=args.append,
        )
        for table_name, filepath in sorted(paths.items()):
            row_count = sum(1 for _ in open(filepath)) - 1  # minus header
            print(f"    {table_name + '.csv':20s} {row_count:>5} Zeilen")
        mode = "angehaengt" if args.append else "geschrieben"
        print(f"[*] Fertig ({mode}). Lade in R mit:")
        print(f'    library(readr)')
        print(f'    snapshots <- read_csv("{args.csv}/snapshots.csv")')
        print(f'    chars     <- read_csv("{args.csv}/characters.csv")')
        print(f'    skills    <- read_csv("{args.csv}/skills.csv")')
        print(f'    inv       <- read_csv("{args.csv}/inventory_slots.csv")')
        print(f'    quests    <- read_csv("{args.csv}/quests.csv")')
        print(f'[*] Zusatzdatei: {args.csv}/data_dictionary.csv')
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


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.info:
        cmd_info()
    else:
        cmd_read(args)


if __name__ == "__main__":
    main()
