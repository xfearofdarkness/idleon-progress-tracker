# IdleOn Progress Tracker

Liest lokale Save-Daten aus **Legends of Idleon** und exportiert sie als
saubere, analysierbare CSV-Datensaetze fuer Data-Science-Workflows in R oder
Python.

Das Tool ist auf einen klaren Forschungs- und Projekt-Workflow ausgelegt:

- automatische Erkennung von IdleOn-Saves auf macOS, Windows und CrossOver
- rein lesender Zugriff ohne Aenderung am Spielstand
- normalisierte CSV-Tabellen mit stabilen Join-Schluesseln
- dokumentierte Spalten ueber `data_dictionary.csv`
- keine vorgefertigte Analyse- oder Plot-Logik im Export

## Schnellstart

```bash
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Speicherort pruefen
python -m idleon_reader --info

# Menschenlesbaren Bericht anzeigen
python -m idleon_reader

# CSV-Datensaetze exportieren
python -m idleon_reader --csv exports/latest
```

Wenn du nur den direkten CLI-Output des Extractors sehen willst:

```bash
bash scripts/show_extractor_output.sh
```

## Exportierte Datensaetze

Ein Export nach `exports/latest/` erzeugt diese Dateien:

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

Der Export ist bewusst auf eindeutige, auswertbare Tabellen ausgelegt:

- `snapshot_id` verbindet alle Tabellen
- eine Beobachtung pro Zeile
- feste, dokumentierte Spalten
- JSON-Zellen nur dort, wo rohe Unterstrukturen erhalten bleiben sollen
- auch leere Tabellen werden mit Header geschrieben

## Plattformen

### macOS

- native Steam-Installation wird automatisch erkannt
- CrossOver-Bottles werden automatisch erkannt
- empfohlen: `brew install leveldb`

### Windows

Windows funktioniert, wenn mindestens ein nutzbarer LevelDB-Zugriff vorhanden
ist:

1. `plyvel` funktioniert in der lokalen Python-Umgebung
2. `leveldbutil.exe` liegt auf `PATH`
3. `leveldbutil.exe` liegt im Repo unter `tools/leveldbutil.exe`
4. `IDLEON_LEVELDBUTIL` zeigt auf die Binary

Fuer Teams ist der pragmatischste Weg:

1. Eine Person baut `leveldbutil.exe` einmal.
2. Die Binary wird unter `tools/leveldbutil.exe` abgelegt oder intern verteilt.
3. Alle Windows-Nutzer verwenden denselben Repo-Stand.

Die genauere Anleitung steht in [SETUP.md](./SETUP.md).

## CLI

```bash
# Auto-Erkennung und Bericht
python -m idleon_reader

# Speicherort anzeigen
python -m idleon_reader --info

# Rohdaten als JSON exportieren
python -m idleon_reader --json --output save.json

# CSV-Datensaetze exportieren
python -m idleon_reader --csv exports/latest

# Mehrere Zeitpunkte in dieselben CSVs schreiben
python -m idleon_reader --csv exports/history --append

# Nur den sichtbaren CLI-Output des Extractors zeigen
bash scripts/show_extractor_output.sh
```

## Tests

```bash
pip install pytest
pytest -q
```

## Hinweise

- Das Tool liest nur Daten.
- IdleOn wird nicht gepatcht oder veraendert.
- Fuer Team-Setups auf Windows sind die Skripte in `scripts/` und die Hinweise
  in `SETUP.md` relevant.

## Lizenz

MIT
