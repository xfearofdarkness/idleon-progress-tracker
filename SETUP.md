# Setup For The Team

## Ziel

Alle Teammitglieder sollen denselben Export erzeugen koennen:

- gleicher CLI-Aufruf
- gleiche CSV-Tabellen
- gleiche Join-Keys
- gleiche R-Starterdatei

## macOS

### 1. Voraussetzungen

```bash
brew install leveldb
python3 --version
```

### 2. Projekt einrichten

```bash
git clone <repo-url>
cd idleon-progress-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Testen

```bash
python -m idleon_reader --info
python -m idleon_reader
python -m idleon_reader --csv exports/latest
```

Wenn IdleOn ueber CrossOver installiert ist, wird der Save automatisch erkannt.

## Windows

## Empfohlener Weg

Auf Windows braucht der Reader einen funktionierenden LevelDB-Zugriff. Dafuer
gibt es zwei praktikable Wege:

1. `leveldbutil.exe` bereitstellen
2. `plyvel` in der lokalen Python-Umgebung funktional installieren

Der robusteste Weg fuer das Team ist `leveldbutil.exe`.

### 1. Projekt einrichten

In PowerShell:

```powershell
git clone <repo-url>
cd idleon-progress-tracker
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. leveldbutil.exe bereitstellen

Es gibt drei unterstuetzte Orte:

1. `tools\leveldbutil.exe`
2. irgendwo auf `PATH`
3. Pfad in `IDLEON_LEVELDBUTIL`

Beispiel:

```powershell
$env:IDLEON_LEVELDBUTIL = "C:\tools\leveldbutil.exe"
```

### 3. Export testen

```powershell
python -m idleon_reader --info
python -m idleon_reader
python -m idleon_reader --csv exports\latest
```

## Gemeinsamer R-Workflow

Wichtige Tabellen:

- `characters.csv`: Charakter-level Daten
- `skills.csv`: pro Charakter und Skill eine Zeile
- `inventory_slots.csv`: Inventarslots
- `equipment_slots.csv`: Ausruestungsslots
- `quests.csv`: Quest-Zustaende
- `account_metrics.csv`: Account-Kennzahlen
- `cards.csv`: Karten-Collection
- `starsigns.csv`: Star Signs
- `data_dictionary.csv`: Spaltenbeschreibung

## Standard-Aufruf Fuer Snapshots

Fuer Zeitreihen:

```bash
python -m idleon_reader --csv exports/history --append
```

Dann koennen mehrere Exporte aus verschiedenen Zeitpunkten gemeinsam in R
ausgewertet werden.
