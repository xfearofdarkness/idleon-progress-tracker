# IdleOn Progress Tracker

Liest lokale Save-Daten aus **Legends of Idleon** und exportiert sie als
saubere CSV-Datensätze für ein Data-Science-Projekt.

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

Hinweis für Windows:

- `tools/leveldbutil.exe` liegt bereits im Repo
- dadurch muss auf Windows niemand `leveldb` selbst bauen

## Daten extrahieren

Wenn ein Save mehrere logische Accounts enthält:

```bash
python -m idleon_reader --list-save-accounts
python -m idleon_reader --save-account mySave --csv exports/latest
```

### macOS / Linux

Standard-Export:

```bash
bash scripts/export_tracker.sh
```

Bestimmten Zielordner verwenden:

```bash
bash scripts/export_tracker.sh exports/latest
```

### Windows

Standard-Export:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1
```

Bestimmten Zielordner verwenden:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\latest
```

## Studien-Metadaten beim Export

Die Export-Skripte reichen zusätzliche CLI-Flags direkt an `python -m idleon_reader`
weiter. Zusätzliche Metadaten landen direkt im Snapshot-Export.

Beispiel macOS / Linux:

```bash
bash scripts/export_tracker.sh exports/study_a \
  --account-label speed_run \
  --study-group pilot \
  --session-id s01 \
  --run-type baseline \
  --strategy-label speed \
  --playtime-minutes 15 \
  --tag session_start \
  --tag baseline
```

Beispiel Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\study_a `
  --account-label speed_run `
  --study-group pilot `
  --session-id s01 `
  --run-type baseline `
  --strategy-label speed `
  --playtime-minutes 15 `
  --tag session_start `
  --tag baseline
```

Verfügbare Zusatzflags:

- `--account-label`
- `--study-group`
- `--session-id`
- `--run-type manual|baseline|checkpoint|session_end|milestone`
- `--strategy-label`
- `--notes`
- `--playtime-minutes`
- `--tag` mehrfach wiederholbar

## Dry-Run / Vorschau

Mit `--dry-run` wird der Export komplett gebaut und validiert, aber nichts auf
die Platte geschrieben.

macOS / Linux:

```bash
bash scripts/export_tracker.sh exports/preview --dry-run --account-label speed_run
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\preview --dry-run --account-label speed_run
```

## Kontinuierlich an dieselben Dateien anhängen

Neue Snapshots werden an denselben Satz CSV-Dateien im Zielordner angehängt.

Wichtig:

- es wird nicht an eine einzige Datei angehängt
- stattdessen werden dieselben Tabellen im Zielordner erweitert
- verbunden werden die Datensätze über `snapshot_id`
- Append auf alte Exporte mit abweichendem Schema wird bewusst blockiert

macOS / Linux:

```bash
bash scripts/export_tracker.sh exports/history --append --session-id s02 --tag session_end
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\history --append --session-id s02 --tag session_end
```

## Exportierte Dateien

Ein Export erzeugt:

- `snapshots.csv`
- `snapshot_tags.csv`
- `account_metrics.csv`
- `characters.csv`
- `skills.csv`
- `inventory_slots.csv`
- `equipment_slots.csv`
- `quests.csv`
- `cards.csv`
- `starsigns.csv`
- `data_dictionary.csv`
- `run_manifests/<snapshot_id>.json`

## CLI-Output anzeigen

Nur den sichtbaren Extractor-Output anzeigen:

```bash
bash scripts/show_extractor_output.sh
```

Optional mit Logdatei:

```bash
bash scripts/show_extractor_output.sh extractor-output.log
```

## Hinweise

- Das Tool liest nur Daten.
- IdleOn wird nicht gepatcht oder verändert.
- Es wird keine Analyse- oder Plot-Logik mitexportiert, nur Daten.

## Lizenz

MIT
