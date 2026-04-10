# IdleOn Progress Tracker

Liest lokale IdleOn-Saves und exportiert saubere CSV-Datensätze für eure Auswertung.

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

`tools/leveldbutil.exe` liegt bereits im Repo. Auf Windows muss deshalb niemand LevelDB selbst bauen.

## Schneller Export

Normale Übersicht:

```bash
python -m idleon_reader
```

CSV-Export:

```bash
python -m idleon_reader --csv exports/latest
```

Wenn ein Save mehrere logische Accounts enthält:

```bash
python -m idleon_reader --list-save-accounts
python -m idleon_reader --save-account mySave --csv exports/latest
```

## Study-Workflow

Der `study`-Workflow ist für wiederholte Exporte mit festen Profilen gedacht.

Wichtige Begriffe:

- `Profilname`: der Name unter `[accounts.<name>]` in `study_profiles.toml`
- `profile`: genau so ein Profilname
- `save_selector`: ein Selector aus `python -m idleon_reader --list-save-accounts`

Aktuelle Profilnamen im Repo:

- `speed_run`
- `skill_focus`
- `balanced_run`

Einmal initialisieren:

```bash
python -m idleon_reader study init-config
```

Dann `study_local.toml` ausfüllen. Das ist die lokale, git-ignorierte Datei für deinen Rechner.

Beispiel:

```toml
[local]
# Optionaler Standard für study-Kommandos ohne --account
profile = "speed_run"

# Optional, falls Auto-Erkennung nicht reicht
save_path = "/absolute/path/to/leveldb"

# Nur nötig, wenn ein LevelDB-Save mehrere logische Accounts enthält
save_selector = "mySave"
```

Das ist absichtlich alles. Für normale Nutzung brauchst du lokal nur:

- `profile`
- optional `save_path`
- optional `save_selector`

Nur wenn ein einzelner Rechner je Profil verschiedene lokale Werte braucht, kannst du zusätzlich manuell `[accounts.<profilname>]`-Blöcke anlegen.

## Study-Befehle

Baseline:

```bash
python -m idleon_reader study baseline --tag baseline
```

Session starten:

```bash
python -m idleon_reader study session-start
```

Checkpoint:

```bash
python -m idleon_reader study checkpoint --playtime-minutes 30
```

Milestone:

```bash
python -m idleon_reader study milestone --tag reached_level_10 --playtime-minutes 45
```

Session beenden:

```bash
python -m idleon_reader study session-end --playtime-minutes 60
```

Status:

```bash
python -m idleon_reader study status
```

## Output

Ein Export schreibt unter anderem:

- `snapshots.csv`
- `snapshot_tags.csv`
- `characters.csv`
- `skills.csv`
- `inventory_slots.csv`
- `equipment_slots.csv`
- `quests.csv`
- `cards.csv`
- `starsigns.csv`
- `account_metrics.csv`
- `data_dictionary.csv`
- `run_manifests/<snapshot_id>.json`

Für Zeitreihen wird an dieselben CSV-Dateien angehängt. Alte Exportordner mit abweichendem Schema werden bewusst blockiert.

## Dry-Run

```bash
python -m idleon_reader --csv exports/latest --dry-run
python -m idleon_reader study session-start --dry-run
```

## Nur CLI-Output anzeigen

```bash
bash scripts/show_extractor_output.sh
```
