# IdleOn Progress Tracker

Liest lokale Save-Daten aus **Legends of Idleon** und exportiert sie als
saubere CSV-Datensaetze fuer ein Data-Science-Projekt.

## Installation

### macOS / Linux

```bash
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
bash scripts/install_tracker.sh
```

### Windows

```powershell
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1
```

Hinweis fuer Windows:

- `tools/leveldbutil.exe` liegt bereits im Repo
- dadurch muss auf Windows niemand `leveldb` selbst bauen

## Daten extrahieren

### macOS / Linux

Standard-Export:

```bash
bash scripts/export_tracker.sh
```

In einen bestimmten Ordner:

```bash
bash scripts/export_tracker.sh exports/latest
```

### Windows

Standard-Export:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1
```

In einen bestimmten Ordner:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\latest
```

## Kontinuierlich an dieselben Dateien anhängen

Ja. Das Tool kann neue Snapshots an denselben Satz CSV-Dateien anhängen.

Wichtig:

- es wird nicht an eine einzige Datei angehängt
- stattdessen werden dieselben Tabellen im Zielordner erweitert
- verbunden werden die Datensaetze über `snapshot_id`

### macOS / Linux

```bash
bash scripts/export_tracker.sh exports/history --append
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\history --append
```

## Exportierte Dateien

Ein Export erzeugt:

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

## Optional: CLI-Output anzeigen

Wenn du nur den sichtbaren Extractor-Output sehen willst:

```bash
bash scripts/show_extractor_output.sh
```

Optional mit Logdatei:

```bash
bash scripts/show_extractor_output.sh extractor-output.log
```

## Hinweise

- Das Tool liest nur Daten.
- IdleOn wird nicht gepatcht oder veraendert.
- Es wird keine Analyse- oder Plot-Logik mitexportiert, nur Daten.

## Lizenz

MIT
