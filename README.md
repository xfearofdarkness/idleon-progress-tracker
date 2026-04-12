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

Vor jedem Export IdleOn vollständig schließen. Das Tool bricht jetzt bewusst ab, wenn der Spielprozess noch läuft oder sich die Save-Dateien noch verändern. Das gilt auf macOS auch für CrossOver-/Wine-Starts, sofern der Prozessbezug zu IdleOn im Kommando erkennbar ist.

Standard-Export:

```bash
python -m idleon_reader --csv exports/latest
```

Wenn der Ordner bereits Exportdateien enthält, wird der nächste Snapshot standardmäßig angehängt.
Nur für einen bewussten Neuaufbau desselben Ordners:

```bash
python -m idleon_reader --csv exports/latest --overwrite
```

Wenn ein Save mehrere logische Accounts enthält:

```bash
python -m idleon_reader --list-save-accounts
python -m idleon_reader --save-account mySave --csv exports/latest
```

Wenn keine Charaktere erkannt werden, stoppt der CSV-Export standardmäßig.
Für denselben Lesevorgang zusätzlich den Rohsave sichern:

```bash
python -m idleon_reader --save-account mySave --csv exports/latest --debug-json
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

[backup]
root = "/absolute/path/outside/repo"
```

Optional kann das Studienprofil in `study_profiles.toml` auch den erwarteten Charakterbestand festlegen. Dann blockt der Study-Workflow automatisch, wenn im Save Charaktere fehlen:

```toml
[accounts.account_1]
account_label = "account_1"
strategy_label = "custom"
export_subdir = "account_1"
expected_character_names = ["Alpha"]
expected_character_count = 1
```

Danach funktionieren die einfachen Study-Kommandos ohne lange Flag-Ketten:

```bash
python -m idleon_reader study baseline --tag baseline
python -m idleon_reader study start
python -m idleon_reader study end --playtime-minutes 60
```

Wichtig:

- `baseline` und `end` sind die belastbaren Save-Snapshots.
- `start` legt nur den Studienkontext an und schreibt keinen Save-Export.
- Live-Checkpoints waehrend des Spielens sind bewusst nicht Teil des empfohlenen Workflows, weil IdleOn dabei keine verlaesslichen Voll-Saves liefert.

Nach jedem erfolgreichen Study-Export wird automatisch ein ZIP-Backup außerhalb des Repos geschrieben.
Ein bestehendes Backup kann manuell angezeigt oder wiederhergestellt werden:

```bash
python -m idleon_reader study list-backups
python -m idleon_reader study restore-backup /path/to/archive.zip
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
