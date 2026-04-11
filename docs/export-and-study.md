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

Wenn im Zielordner bereits ein Export liegt, wird automatisch an denselben Verlauf angehängt.

Dry-Run:

```bash
python -m idleon_reader --csv exports/latest --dry-run
```

Explizit an denselben Exportordner anhängen:

```bash
python -m idleon_reader --csv exports/history --append
```

Vorhandenen Export bewusst ersetzen:

```bash
python -m idleon_reader --csv exports/history --overwrite
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

[backup]
root = "/absolute/path/outside/repo"
include_local_config = true
```

Bedeutung:

- `profile`: Profilname aus `study_profiles.toml`
- `save_path`: lokaler IdleOn-LevelDB-Pfad
- `save_selector`: Selector aus `--list-save-accounts`, nur bei mehreren Accounts nötig
- `backup.root`: lokaler Backup-Ordner außerhalb des Repos
- `backup.include_local_config`: nimmt `study_local.toml` mit ins Archiv auf

Einfache Study-Kommandos:

```bash
python -m idleon_reader study baseline --tag baseline
python -m idleon_reader study session-start
python -m idleon_reader study checkpoint --playtime-minutes 30
python -m idleon_reader study milestone --tag reached_level_10 --playtime-minutes 45
python -m idleon_reader study session-end --playtime-minutes 60
python -m idleon_reader study status
```

Wenn ein Account-Verlauf bewusst neu aufgebaut werden soll:

```bash
python -m idleon_reader study baseline --overwrite --tag baseline
```

Wenn kein `profile` gesetzt ist, muss es explizit angegeben werden:

```bash
python -m idleon_reader study session-start --account account_1
```

## Study-Backups

Nach jedem erfolgreichen Study-Export wird automatisch ein ZIP-Backup geschrieben.
Der Backup-Ordner muss außerhalb des Repos liegen.

Backup manuell anstoßen:

```bash
python -m idleon_reader study backup-now
python -m idleon_reader study backup-now --account account_1
python -m idleon_reader study backup-now --no-local-config
```

Vorhandene Backups anzeigen:

```bash
python -m idleon_reader study list-backups
python -m idleon_reader study list-backups --account account_1
```

Backup wiederherstellen:

```bash
python -m idleon_reader study restore-backup /path/to/archive.zip
python -m idleon_reader study restore-backup /path/to/archive.zip --output-dir restores/recovery-01
python -m idleon_reader study restore-backup /path/to/archive.zip --output-dir restores/recovery-01 --overwrite
```

Wichtige Regeln:

- Backup-Fehler werden klar angezeigt, machen den Export aber nicht ungueltig.
- `--dry-run` erzeugt keine Backups.
- Restore schreibt standardmaessig in einen neuen Zielordner.
- `study_local.toml` wird standardmaessig mitgesichert und kann bei `backup-now` per `--no-local-config` ausgeschlossen werden.
