# IdleOn Progress Tracker

Liest lokale IdleOn-Saves und exportiert saubere CSV-Datensätze für die Auswertung.

## Installation

macOS / Linux:

```bash
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
bash scripts/install_tracker.sh
```

Windows:

```powershell
git clone https://github.com/xfearofdarkness/idleon-progress-tracker.git
cd idleon-progress-tracker
powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1
```
## Hinweis

Für nachfolgende Commands mit `python -m idleon_reader ...` muss die Projekt-`venv` aktiv sein:

macOS / Linux:
```bash
source .venv/bin/activate
```

Windows
```powershell
.\.venv\Scripts\Activate.ps1
```

## Schneller Export

Standard-Export:

```bash
python -m idleon_reader --csv exports/latest
```

Wenn ein Save mehrere logische Accounts enthält:

```bash
python -m idleon_reader --list-save-accounts
python -m idleon_reader --save-account mySave --csv exports/latest
```

## Study-Workflow

`study init-config` legt die lokalen Konfigurationsdateien an:

```bash
python -m idleon_reader study init-config
```

Minimales lokales Beispiel:

```toml
[local]
profile = "account_1"
save_path = "/absolute/path/to/leveldb"
save_selector = "mySave"
```

Danach funktionieren die einfachen Study-Kommandos ohne lange Flag-Ketten:

```bash
python -m idleon_reader study baseline --tag baseline
python -m idleon_reader study session-start
python -m idleon_reader study checkpoint --playtime-minutes 30
python -m idleon_reader study session-end --playtime-minutes 60
```

## Weiterführende Doku

- [Export und CLI-Flags](./docs/export-and-study.md)

## Output

Ein Export schreibt unter anderem:

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

## Nur CLI-Output anzeigen

```bash
bash scripts/show_extractor_output.sh
```
