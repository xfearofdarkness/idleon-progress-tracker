# IdleOn Progress Tracker

Liest lokale Save-Daten aus **Legends of Idleon** und exportiert sie als
saubere CSV-Datensaetze fuer Data-Science-Workflows.

Der Export ist auf klare, auswertbare Tabellen ausgelegt:

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

## Installation

### macOS / Linux

```bash
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
bash scripts/install_tracker.sh
```

### Windows

In PowerShell:

```powershell
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1
```

Hinweis fuer Windows:

- `tools/leveldbutil.exe` liegt bereits im Repo.
- Dadurch muss auf Windows niemand `leveldb` selbst bauen.

## Nutzung

### Speicherort pruefen

```bash
python -m idleon_reader --info
```

### Bericht anzeigen

```bash
python -m idleon_reader
```

### CSV-Datensaetze exportieren

```bash
python -m idleon_reader --csv exports/latest
```

Oder ueber das Export-Skript:

```bash
bash scripts/export_tracker.sh
```

### Mehrere Zeitpunkte in dieselben CSVs schreiben

```bash
python -m idleon_reader --csv exports/history --append
```

Oder ueber das Export-Skript:

```bash
bash scripts/export_tracker.sh exports/history --append
```

Wichtig:

- `--append` haengt an dieselben CSV-Dateien im Zielordner an
- es gibt dabei nicht eine einzige Sammeldatei, sondern weiterhin eine Datei pro Tabelle
- fuer Zeitreihen ist also `exports/history/` als gemeinsamer Ordner gedacht

### Sichtbaren CLI-Output des Extractors anzeigen

```bash
bash scripts/show_extractor_output.sh
```

Optional mit Logdatei:

```bash
bash scripts/show_extractor_output.sh extractor-output.log
```

## Was der Installer macht

Die Installationsskripte:

- legen bei Bedarf `.venv` an
- aktualisieren `pip`
- installieren das Paket im Editable-Modus
- pruefen die wichtigsten Voraussetzungen
- geben die naechsten Befehle zum Testen aus

Die Export-Skripte:

- `scripts/export_tracker.sh`
- `scripts/export_tracker_windows.ps1`

starten direkt die Datenextraktion und schreiben die CSV-Dateien in einen
Ausgabeordner.

## Plattformhinweise

### macOS

- native Steam-Installationen werden erkannt
- CrossOver-Bottles werden erkannt
- wenn `leveldbutil` lokal fehlt, ist `brew install leveldb` empfohlen

### Windows

- das Repo enthaelt bereits `tools/leveldbutil.exe`
- der Reader nutzt die Datei automatisch
- falls noetig, kann zusaetzlich `IDLEON_LEVELDBUTIL` gesetzt werden
- Export-Skript auf Windows:
  `powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1`

## Tests

```bash
pytest -q
```

## Hinweise

- Das Tool liest nur Daten.
- IdleOn wird nicht gepatcht oder veraendert.
- Es wird keine Analyse- oder Plot-Logik mitexportiert, nur Daten.

## Lizenz

MIT
