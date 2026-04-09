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

## Studien-Workflow

Für die eigentliche Erhebung ist der `study`-Workflow der empfohlene Einstieg.
Er baut auf denselben CSV-Exports auf, reduziert aber manuelle Eingaben durch:

- feste Account-Profile in `study_profiles.toml`
- lokale Save-Pfade in `study_local.toml`
- automatische Session-IDs
- aktiven Session-Kontext in `.idleon-study/current_session.json`
- kontrollierte Run-Types und Tags

Die rohe Export-CLI bleibt weiterhin verfügbar, falls ihr einzelne Exporte
manuell fahren wollt.

## Einmalige Study-Konfiguration

Im Repo liegt bereits eine getrackte `study_profiles.toml` mit den drei
Studienaccounts:

- `A_speed`
- `B_skills`
- `C_balanced`

Einmal lokal initialisieren:

```bash
python -m idleon_reader study init-config
```

Danach `study_local.toml` öffnen und bei Bedarf lokale Save-Pfade oder einen
`default_account` eintragen. Diese Datei ist bewusst git-ignoriert.

Wichtige Dateien:

- `study_profiles.toml`: getrackte Studienprofile und erlaubte Tags
- `study_profiles.toml.example`: Vorlage
- `study_local.toml`: lokale maschinenspezifische Overrides
- `study_local.toml.example`: Vorlage
- `.idleon-study/current_session.json`: aktiver Session-Zustand

## Baseline-Workflow

Der erste Snapshot eines neuen Accounts wird als Baseline ohne aktive Session
erfasst.

Beispiel:

```bash
python -m idleon_reader study baseline --account A_speed --tag baseline
```

Optional könnt ihr zusätzlich setzen:

- `--notes`
- `--study-group`
- `--save-path`
- `--output-dir`
- `--dry-run`

## Session-Workflow

### Session starten

```bash
python -m idleon_reader study session-start --account A_speed
```

Dabei passiert automatisch:

- Session-ID wird erzeugt, z. B. `A_speed-20260409-s01`
- `run_type` wird auf `checkpoint` gesetzt
- das Tag `session_start` wird ergänzt
- der Session-Kontext wird lokal gespeichert

### Checkpoint erfassen

```bash
python -m idleon_reader study checkpoint --playtime-minutes 30
```

Optional:

- `--notes`
- `--tag`
- `--dry-run`

### Milestone erfassen

```bash
python -m idleon_reader study milestone --tag reached_level_10 --playtime-minutes 45
```

Für `milestone` sind nur Tags erlaubt, die in `study_profiles.toml` unter
`allowed_milestone_tags` definiert sind.

### Session beenden

```bash
python -m idleon_reader study session-end --playtime-minutes 60
```

Dabei passiert automatisch:

- `run_type` wird auf `session_end` gesetzt
- das Tag `session_end` wird ergänzt
- nach erfolgreichem Export wird die aktive Session gelöscht

## Status prüfen

```bash
python -m idleon_reader study status
```

Die Ausgabe zeigt unter anderem:

- aktiven Account
- Strategie
- Session-ID
- Save-Pfad
- Exportpfad
- Startzeit
- letzte Snapshot-ID
- letzten sinnvollen nächsten Schritt

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

Die zentrale Join-Basis bleibt `snapshot_id`. Für Studienkontext kommen unter
anderem diese Felder hinzu:

- `account_label`
- `study_group`
- `session_id`
- `run_type`
- `strategy_label`
- `notes`
- `playtime_minutes_since_last_snapshot`

Zusätzliche Ereignisse landen normalisiert in `snapshot_tags.csv`.

## Kontinuierlich an dieselben Dateien anhängen

Ja. Der Workflow schreibt pro Account immer in denselben Verlaufspfad, also zum
Beispiel:

- `exports/study/A_speed/`
- `exports/study/B_skills/`
- `exports/study/C_balanced/`

Neue Snapshots werden an denselben CSV-Satz angehängt. Alte Exporte mit
abweichendem Schema werden bewusst blockiert, damit keine stillen Join-Probleme
entstehen.

## Dry-Run / Vorschau

Mit `--dry-run` wird ein Export komplett gebaut und validiert, aber nichts auf
die Platte geschrieben.

Beispiele:

```bash
python -m idleon_reader study session-start --account A_speed --dry-run --tag baseline
python -m idleon_reader study checkpoint --dry-run --playtime-minutes 20
```

## Wann die rohe Export-CLI sinnvoll ist

Der ursprüngliche CSV-Export bleibt für Sonderfälle nützlich, zum Beispiel wenn
ihr bewusst außerhalb des Studien-Workflows arbeiten wollt.

### macOS / Linux

```bash
bash scripts/export_tracker.sh exports/latest
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1 exports\latest
```

Oder direkt:

```bash
python -m idleon_reader --csv exports/latest --account-label A_speed --run-type checkpoint
```

## CLI-Output anzeigen

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
- IdleOn wird nicht gepatcht oder verändert.
- Es wird keine Analyse- oder Plot-Logik mitexportiert, nur Daten.

## Lizenz

MIT
