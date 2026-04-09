# IdleOn Progress Tracker

Extrahiert den Spielerfortschritt aus lokalen **Legends of Idleon** (von lavaflame2) Speicherdateien, **ohne das Spiel zu modifizieren**.

## Was macht dieses Tool?

- Liest die lokale LevelDB-Datenbank der Steam-Version von IdleOn
- Dekodiert das Haxe-Serialisierungsformat (Stencyl-Engine)
- Zeigt Charaktere, Level, Klassen, Faehigkeiten und Account-Daten an
- Exportiert Rohdaten als JSON fuer weitere Analyse
- **Rein lesender Zugriff** - es wird nichts veraendert!

## Installation

```bash
# Repository klonen
git clone <repo-url>
cd idleon-progress-tracker

# (Optional) Virtuelle Umgebung
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Installieren
pip install -e .

# Optional: Schnellerer LevelDB-Zugriff (braucht C-Compiler)
pip install plyvel
```

**Keine externen Abhaengigkeiten noetig!** Das Tool funktioniert mit reinem Python 3.10+.
Optional kann `plyvel` fuer schnelleren LevelDB-Zugriff installiert werden.

## Verwendung

### Automatische Erkennung
```bash
# Findet die Speicherdaten automatisch und zeigt den Fortschritt an
python -m idleon_reader
```

### Speicherort-Information
```bash
# Zeigt wo die Speicherdaten liegen
python -m idleon_reader --info
```

### JSON-Export
```bash
# Exportiere alle Rohdaten als JSON
python -m idleon_reader --json

# In Datei speichern
python -m idleon_reader --json --output meine_daten.json
```

### Manueller Pfad
```bash
# Wenn die Auto-Erkennung nicht funktioniert
python -m idleon_reader --path /pfad/zum/leveldb-verzeichnis
```

### Einzelne Schluessel auslesen
```bash
# Zeige alle verfuegbaren Schluessel
python -m idleon_reader --raw-keys

# Bestimmten Schluessel als JSON exportieren
python -m idleon_reader --key mySave --json
```

## Speicherorte

Das Tool sucht automatisch an diesen Stellen:

| OS | Pfad |
|---|---|
| **Windows** | `%APPDATA%\legends-of-idleon\Local Storage\leveldb` |
| **macOS** | `~/Library/Application Support/legends-of-idleon/Local Storage/leveldb` |
| **Linux** | `~/.config/legends-of-idleon/Local Storage/leveldb` |

## Architektur

```
idleon_reader/
  __init__.py       - Package-Initialisierung
  __main__.py       - Entry Point fuer `python -m`
  main.py           - CLI mit argparse
  finder.py         - Automatische Speicherort-Erkennung
  ldb_reader.py     - LevelDB-Leser (plyvel + Pure-Python-Fallback)
  haxe_decoder.py   - Haxe-Serialisierungsformat-Dekoder
  progress.py       - Fortschritts-Extraktion und Formatierung
```

### Wie es funktioniert

1. **Finder** lokalisiert die LevelDB-Datenbank im Dateisystem
2. **LDB Reader** liest die Key-Value-Paare aus der Datenbank
   - Versucht zuerst `plyvel` (schnell, C-basiert)
   - Faellt zurueck auf den eingebauten Raw-Parser (reines Python)
3. **Haxe Decoder** dekodiert die Haxe-serialisierten Werte in Python-Datenstrukturen
4. **Progress Analyzer** extrahiert menschenlesbare Informationen

### Haxe-Serialisierungsformat

IdleOn basiert auf der Stencyl-Engine (Haxe). Die Speicherdaten verwenden das
[Haxe Serialization Format](https://haxe.org/manual/std-serialization-format.html):

- `i123` = Integer 123
- `y5:hello` = String "hello"
- `ai1i2i3h` = Array [1, 2, 3]
- `by3:keyi42h` = StringMap {"key": 42}
- `n` = null, `t` = true, `f` = false

## Tests

```bash
pip install pytest
pytest tests/ -v
```

## Hinweise

- **Nur lesender Zugriff**: Dieses Tool veraendert keine Spieldaten
- **Backup empfohlen**: Erstelle Sicherungskopien bevor du mit Speicherdaten arbeitest
- **Steam-Version**: Funktioniert mit der Steam-Desktop-Version von IdleOn
- **Nicht offiziell**: Kein Zusammenhang mit lavaflame2 oder dem Idleon-Team

## Verwandte Projekte

- [idleon-saver](https://github.com/desophos/idleon-saver) - Konvertiert Speicherdaten zu/von JSON (mit GUI)
- [idleon-data](https://github.com/Corbeno/idleon-data) - Daten-Mapping fuer IdleOn
- [IdleonToolbox](https://github.com/Morta1/IdleonToolbox) - Web-basierter Fortschritts-Tracker
- [Idleon-Api-Downloader](https://github.com/Corbeno/Idleon-Api-Downloader) - Chrome-Extension fuer API-Daten

## Lizenz

MIT License
