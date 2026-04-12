"""
LevelDB Reader for IdleOn Save Data

Reads the LevelDB database used by IdleOn (Electron app) to store local save data.
Supports these strategies:
  1. Using the `leveldbutil dump` CLI (reliable for Chromium/Electron LevelDB files)
  2. Parsing LevelDB log files directly as a last-resort fallback

The LevelDB key format for IdleOn is:
  _file://\\x00\\x01/<install_path>/resources/app.asar/distBuild/static/game/index.html:<key_name>
"""

import shutil
import struct
import subprocess
import os
from pathlib import Path
from typing import Any, Optional

from .haxe_decoder import try_decode_value


# ─── LevelDB Log File Parser (Pure Python Fallback) ────────────────────────

# LevelDB record types
RECORD_FULL = 1
RECORD_FIRST = 2
RECORD_MIDDLE = 3
RECORD_LAST = 4

LEVELDBUTIL_LDB_VALUE_MARKER = " : val => "


def _parse_log_records(filepath: Path) -> list[bytes]:
    """
    Parse records from a LevelDB .log file.
    LevelDB log files use a block-based format with 32KB blocks.
    """
    BLOCK_SIZE = 32768
    HEADER_SIZE = 7  # 4 (checksum) + 2 (length) + 1 (type)
    records = []

    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except (OSError, IOError):
        return records

    pos = 0
    current_record = b""

    while pos < len(data):
        # Align to block boundary header
        if pos + HEADER_SIZE > len(data):
            break

        # Read header
        # checksum = struct.unpack_from("<I", data, pos)[0]
        length = struct.unpack_from("<H", data, pos + 4)[0]
        record_type = data[pos + 6]

        pos += HEADER_SIZE

        if pos + length > len(data):
            break

        payload = data[pos : pos + length]
        pos += length

        if record_type == RECORD_FULL:
            records.append(payload)
            current_record = b""
        elif record_type == RECORD_FIRST:
            current_record = payload
        elif record_type == RECORD_MIDDLE:
            current_record += payload
        elif record_type == RECORD_LAST:
            current_record += payload
            records.append(current_record)
            current_record = b""

        # Skip to next block boundary if needed
        block_offset = pos % BLOCK_SIZE
        remaining_in_block = BLOCK_SIZE - block_offset
        if remaining_in_block < HEADER_SIZE and remaining_in_block > 0:
            pos += remaining_in_block

    return records


def _parse_write_batch(record: bytes) -> list[tuple[bytes, bytes]]:
    """
    Parse key-value pairs from a LevelDB WriteBatch record.

    WriteBatch format:
      - 8 bytes: sequence number
      - 4 bytes: count
      - entries: each is 1-byte type + varint key_len + key [+ varint val_len + val]
    """
    pairs = []
    if len(record) < 12:
        return pairs

    pos = 8  # skip sequence number
    count = struct.unpack_from("<I", record, pos)[0]
    pos += 4

    for _ in range(count):
        if pos >= len(record):
            break

        entry_type = record[pos]
        pos += 1

        if entry_type == 1:  # Put
            # Read key
            key_len, pos = _read_varint(record, pos)
            if key_len is None or pos + key_len > len(record):
                break
            key = record[pos : pos + key_len]
            pos += key_len

            # Read value
            val_len, pos = _read_varint(record, pos)
            if val_len is None or pos + val_len > len(record):
                break
            value = record[pos : pos + val_len]
            pos += val_len

            pairs.append((key, value))

        elif entry_type == 0:  # Delete
            key_len, pos = _read_varint(record, pos)
            if key_len is None or pos + key_len > len(record):
                break
            pos += key_len  # skip deleted key

    return pairs


def _read_varint(data: bytes, pos: int) -> tuple[Optional[int], int]:
    """Read a variable-length integer from data at the given position."""
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result, pos
        shift += 7
    return None, pos


def _find_leveldbutil() -> Optional[str]:
    """Find the leveldbutil executable if it is installed."""
    env_override = Path(
        os.environ.get("IDLEON_LEVELDBUTIL", "")
    ) if os.environ.get("IDLEON_LEVELDBUTIL") else None
    repo_tools = Path(__file__).resolve().parent.parent / "tools"
    candidates = [
        str(env_override) if env_override else None,
        shutil.which("leveldbutil"),
        shutil.which("leveldbutil.exe"),
        str(repo_tools / "leveldbutil"),
        str(repo_tools / "leveldbutil.exe"),
        "/opt/homebrew/bin/leveldbutil",
        "/usr/local/bin/leveldbutil",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def _decode_leveldbutil_literal(value: str) -> str:
    """Decode a single-quoted leveldbutil string with C-style backslash escapes."""
    if len(value) < 2 or value[0] != "'" or value[-1] != "'":
        raise ValueError("Malformed leveldbutil string literal")
    inner = value[1:-1]
    return inner.encode("utf-8", errors="surrogateescape").decode("unicode_escape")


def _normalize_key_name(key_str: str) -> str:
    """Reduce Chromium/Electron LevelDB keys to the logical save key name."""
    if ":" in key_str:
        return key_str.rsplit(":", 1)[-1]
    return key_str


def _decode_entry(key_str: str, value_str: str) -> tuple[str, Any]:
    """Decode a single logical key/value entry from the LevelDB dump."""
    if value_str.startswith("\x01"):
        value_str = value_str[1:]
    return _normalize_key_name(key_str), try_decode_value(value_str)


def _iter_leveldbutil_entries(filepath: Path) -> list[tuple[str, str, Optional[str]]]:
    """
    Parse a file via `leveldbutil dump`.

    Returns tuples of (action, key, value) where action is "put" or "del".
    """
    leveldbutil = _find_leveldbutil()
    if leveldbutil is None:
        raise FileNotFoundError("leveldbutil not found")

    proc = subprocess.run(
        [leveldbutil, "dump", str(filepath)],
        check=True,
        capture_output=True,
        text=True,
    )

    entries = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("put "):
            body = stripped[4:]
            key_sep = body.find("' '")
            if key_sep == -1:
                continue
            key_literal = body[: key_sep + 1]
            value_literal = body[key_sep + 2 :]
            entries.append(
                (
                    "put",
                    _decode_leveldbutil_literal(key_literal),
                    _decode_leveldbutil_literal(value_literal),
                )
            )
            continue

        if stripped.startswith("del "):
            entries.append(("del", _decode_leveldbutil_literal(stripped[4:]), None))
            continue

        key_sep = line.find("' @ ")
        if key_sep != -1 and LEVELDBUTIL_LDB_VALUE_MARKER in line:
            key_literal = line[: key_sep + 1]
            _, _, value_literal = line.partition(LEVELDBUTIL_LDB_VALUE_MARKER)
            entries.append(
                (
                    "put",
                    _decode_leveldbutil_literal(key_literal),
                    _decode_leveldbutil_literal(value_literal),
                )
            )

    return entries


def read_with_leveldbutil(db_path: Path) -> dict[str, Any]:
    """
    Read IdleOn save data using the `leveldbutil dump` CLI.

    This is more reliable than the built-in raw byte scanner for Chromium/Electron
    LevelDB files and works well on systems where `leveldbutil` is installed.
    """
    result = {}
    attempted_files = 0
    failed_files: list[tuple[str, str]] = []

    log_files = sorted(db_path.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for log_file in log_files:
        attempted_files += 1
        try:
            entries = _iter_leveldbutil_entries(log_file)
        except subprocess.CalledProcessError as exc:
            failed_files.append((str(log_file.name), str(exc)))
            continue
        for action, key_str, value_str in entries:
            key_name = _normalize_key_name(key_str)
            if action == "del":
                result.pop(key_name, None)
                continue
            try:
                key_name, decoded = _decode_entry(key_str, value_str or "")
                result[key_name] = decoded
            except (ValueError, SyntaxError):
                continue

    ldb_files = sorted(db_path.glob("*.ldb"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ldb_file in ldb_files:
        attempted_files += 1
        try:
            entries = _iter_leveldbutil_entries(ldb_file)
        except subprocess.CalledProcessError as exc:
            failed_files.append((str(ldb_file.name), str(exc)))
            continue
        for action, key_str, value_str in entries:
            if action != "put":
                continue
            key_name = _normalize_key_name(key_str)
            if key_name in result:
                continue
            try:
                key_name, decoded = _decode_entry(key_str, value_str or "")
                result[key_name] = decoded
            except (ValueError, SyntaxError):
                continue

    if not result and attempted_files and len(failed_files) == attempted_files:
        sample = "; ".join(f"{name}: {message}" for name, message in failed_files[:3])
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=f"leveldbutil dump ({attempted_files} files)",
            output=sample,
        )

    return result


# ─── High-Level Reader ──────────────────────────────────────────────────────


def read_raw(db_path: Path) -> dict[str, Any]:
    """
    Read IdleOn save data using raw LevelDB log parsing.

    This last-resort fallback only parses `.log` write batches. It avoids
    attempting to scrape `.ldb` SSTables heuristically because that produced
    ambiguous and misleading data.

    Args:
        db_path: Path to the LevelDB directory.

    Returns:
        Dictionary of decoded save data.
    """
    result = {}

    # Parse .log files (Write-Ahead Log - most recent data)
    log_files = sorted(db_path.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for log_file in log_files:
        records = _parse_log_records(log_file)
        for record in records:
            pairs = _parse_write_batch(record)
            for key_bytes, value_bytes in pairs:
                try:
                    key_str = key_bytes.decode("utf-8", errors="replace")

                    if ":" in key_str:
                        key_name = key_str.split(":")[-1]
                    else:
                        key_name = key_str

                    value_str = value_bytes.decode("utf-8", errors="replace")
                    if value_str.startswith("\x01"):
                        value_str = value_str[1:]

                    result[key_name] = try_decode_value(value_str)

                except (UnicodeDecodeError, ValueError):
                    continue

    return result


def read_save_data(db_path: Path, idleon_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Read IdleOn save data, preferring leveldbutil and falling back to raw parsing.

    Args:
        db_path: Path to the LevelDB directory.
        idleon_path: Optional path to the IdleOn installation.

    Returns:
        Dictionary of decoded save data.
    """
    # Try leveldbutil before the built-in raw parser
    try:
        print("[*] Trying leveldbutil dump...")
        result = read_with_leveldbutil(db_path)
        if result:
            return result
        print("[!] leveldbutil produced no decoded save entries, falling back to raw log parser...")
    except FileNotFoundError:
        print("[*] leveldbutil not available.")
    except subprocess.CalledProcessError as e:
        print(f"[!] leveldbutil failed ({e}), falling back to raw parser...")
    except Exception as e:
        print(f"[!] leveldbutil parsing failed ({e}), falling back to raw parser...")

    # Fallback to raw parsing
    print("[*] Falling back to raw log parser...")
    return read_raw(db_path)
