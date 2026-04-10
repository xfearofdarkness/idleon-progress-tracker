# Export und Study-Workflow

Die Befehle auf dieser Seite setzen eine aktivierte Projekt-`venv` voraus.

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Standard-Export

CSV-Export:

```bash
python -m idleon_reader --csv exports/latest
```

Dry-Run:

```bash
python -m idleon_reader --csv exports/latest --dry-run
```

Append an denselben Exportordner:

```bash
python -m idleon_reader --csv exports/history --append
```

## Mehrere Accounts im selben Save

Wenn ein LevelDB-Save mehrere logische Accounts enthält, zuerst die Selector anzeigen:

```bash
python -m idleon_reader --list-save-accounts
```

Beispielausgabe:

```text
[1] mySave     1 Charaktere  fearofdarkness
[2] altSave    2 Charaktere  Alpha, Beta
```

Danach den gewünschten Account gezielt auswählen:

```bash
python -m idleon_reader --save-account mySave --csv exports/latest
```

Oder über die Nummer:

```bash
python -m idleon_reader --save-account 2 --csv exports/latest
```

## Export-Metadaten

Zusätzliche Metadaten werden direkt in `snapshots.csv`, `snapshot_tags.csv`
und das Manifest geschrieben.

Wichtige Flags:

- `--account-label`
- `--study-group`
- `--session-id`
- `--run-type`
- `--strategy-label`
- `--notes`
- `--playtime-minutes`
- `--tag` mehrfach wiederholbar

Beispiel:

```bash
python -m idleon_reader --csv exports/study \
  --account-label speed_run \
  --study-group pilot \
  --session-id s01 \
  --run-type baseline \
  --strategy-label speed \
  --playtime-minutes 15 \
  --tag baseline
```

## Study-Workflow

`study init-config` erzeugt:

- `study_profiles.toml`
- `study_local.toml`

Minimale lokale Konfiguration:

```toml
[local]
profile = "account_1"
save_path = "/absolute/path/to/leveldb"
save_selector = "mySave"
```

Bedeutung:

- `profile`: Profilname aus `study_profiles.toml`
- `save_path`: lokaler IdleOn-LevelDB-Pfad
- `save_selector`: Selector aus `--list-save-accounts`, nur bei mehreren Accounts nötig

Einfache Study-Kommandos:

```bash
python -m idleon_reader study baseline --tag baseline
python -m idleon_reader study session-start
python -m idleon_reader study checkpoint --playtime-minutes 30
python -m idleon_reader study milestone --tag reached_level_10 --playtime-minutes 45
python -m idleon_reader study session-end --playtime-minutes 60
python -m idleon_reader study status
```

Wenn kein `profile` gesetzt ist, muss es explizit angegeben werden:

```bash
python -m idleon_reader study session-start --account account_1
```
