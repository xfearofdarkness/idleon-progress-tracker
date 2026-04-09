# IdleOn Progress Tracker

Extrahiert lokale Save-Daten aus **Legends of Idleon** und exportiert sie als
klare, analysierbare CSV-Datensaetze fuer R oder Python.

Der Fokus liegt jetzt auf einem Data-Science-Workflow:

- automatische Erkennung von IdleOn-Saves auf macOS, Windows und CrossOver
- lesender Zugriff ohne Spielmodifikation
- normalisierte CSV-Tabellen mit stabilen Join-Schluesseln
- `data_dictionary.csv` zur Dokumentation

## Schnellstart

```bash
git clone <repo-url>
cd idleon-progress-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Speicherort pruefen
python -m idleon_reader --info

# Bericht anzeigen
python -m idleon_reader

# CSV-Bundle fuer R erzeugen
python -m idleon_reader --csv exports/latest

# Reinen Extractor-Output sehen
bash scripts/show_extractor_output.sh
```

Danach liegen in `exports/latest/` unter anderem:

- `snapshots.csv`
- `account_metrics.csv`
- `characters.csv`
- `skills.csv`
- `inventory_slots.csv`
- `equipment_slots.csv`
- `quests.csv`
- `cards.csv`
- `starsigns.csv`
- `data_dictionary.csv`

## Was Ist Neu

Der Export ist auf eindeutige Datensaetze ausgelegt:

- `snapshot_id` verbindet alle Tabellen
- eine Beobachtung pro Zeile
- feste, dokumentierte Spalten
- JSON-Zellen nur dort, wo rohe Unterstrukturen sinnvoll erhalten bleiben
- leere Tabellen werden trotzdem mit Header geschrieben
- keine vorgefertigte Analyse-Logik im Export

## Plattformen

### macOS

- native Steam-Installation wird automatisch erkannt
- CrossOver-Bottles werden automatisch erkannt
- empfohlen: `brew install leveldb`

### Windows

Windows wird unterstuetzt, wenn eines dieser Backends verfuegbar ist:

1. `plyvel` funktioniert in der jeweiligen Python-Umgebung
2. `leveldbutil.exe` liegt auf `PATH`
3. `leveldbutil.exe` liegt im Repo unter `tools/leveldbutil.exe`
4. `IDLEON_LEVELDBUTIL` zeigt auf die Binary

Der praktikabelste Team-Weg fuer Windows ist:

1. Eine Person baut `leveldbutil.exe` einmal.
2. Die Datei wird unter `tools/leveldbutil.exe` eingecheckt oder intern verteilt.
3. Alle Windows-Nutzer verwenden danach denselben Repo-Stand.

Die Detailanleitung steht in [SETUP.md](/Users/jamiehuta/src/t3 code/Idleon Mod/idleon-progress-tracker/SETUP.md).

## CLI

```bash
# Auto-Erkennung
python -m idleon_reader

# Speicherort anzeigen
python -m idleon_reader --info

# Rohdaten als JSON
python -m idleon_reader --json --output save.json

# R-/CSV-Export
python -m idleon_reader --csv exports/latest

# Nur CLI-Output zeigen
bash scripts/show_extractor_output.sh

# Zeitreihen: an bestehende CSVs anhaengen
python -m idleon_reader --csv exports/history --append
```

## Tests

```bash
pip install pytest
pytest -q
```

## Hinweise

- Das Tool liest nur Daten.
- IdleOn wird nicht gepatcht oder veraendert.
- Wenn du Teammitglieder auf Windows hast, nutzt die Setup-Anleitung und die
  Skripte in `scripts/`.

## Lizenz

MIT
