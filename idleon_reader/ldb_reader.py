"""
LevelDB Reader for IdleOn Save Data

Reads the LevelDB database used by IdleOn (Electron app) to store local save data.
Supports two reading strategies:
  1. Using the 'plyvel' library (fast, C-based)
  2. Raw file parsing fallback (pure Python, no dependencies)

The LevelDB key format for IdleOn is:
  _file://\\x00\\x01/<install_path>/resources/app.asar/distBuild/static/game/index.html:<key_name>
"""

import json
import struct
import os
from pathlib import Path
from typing import Any, Optional

from .haxe_decoder import try_decode_value, HaxeDecodeError


# ─── LevelDB Log File Parser (Pure Python Fallback) ────────────────────────

# LevelDB record types
RECORD_FULL = 1
RECORD_FIRST = 2
RECORD_MIDDLE = 3
RECORD_LAST = 4


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


# ─── LDB Table File Parser ─────────────────────────────────────────────────


def _read_ldb_file(filepath: Path) -> list[tuple[bytes, bytes]]:
    """
    Simplified reader for .ldb (SSTable) files.
    Extracts key-value pairs by scanning for recognizable patterns.
    This is a best-effort parser that looks for the mySave key.
    """
    pairs = []
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except (OSError, IOError):
        return pairs

    # Search for 'mySave' key marker in the raw data
    marker = b"mySave"
    search_pos = 0

    while True:
        idx = data.find(marker, search_pos)
        if idx == -1:
            break

        # Try to find the value following the key
        # The value typically starts with \x01 followed by the Haxe-serialized data
        # or it could be a direct JSON/text value
        value_start = idx + len(marker)

        # Look for the start of the value (skip any separator bytes)
        while value_start < len(data) and data[value_start] in (0x00, 0x01, 0x02):
            value_start += 1

        if value_start < len(data):
            # Try to extract a reasonable chunk of text
            value_end = value_start
            # Read until we hit non-text data or end of meaningful content
            while value_end < len(data):
                byte = data[value_end]
                # Stop at obvious binary data boundaries
                if byte < 0x09 and byte != 0x00:
                    break
                value_end += 1
                # Safety limit
                if value_end - value_start > 10_000_000:
                    break

            value = data[value_start:value_end]
            if value:
                pairs.append((marker, value))

        search_pos = idx + 1

    return pairs


# ─── High-Level Reader ──────────────────────────────────────────────────────


def read_with_plyvel(db_path: Path, idleon_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Read IdleOn save data using the plyvel library.

    Args:
        db_path: Path to the LevelDB directory.
        idleon_path: Path to the IdleOn installation (for key construction).

    Returns:
        Dictionary of decoded save data.
    """
    import plyvel

    db = plyvel.DB(str(db_path))
    result = {}

    try:
        for key_bytes, value_bytes in db:
            try:
                key_str = key_bytes.decode("utf-8", errors="replace")
                # Strip the LevelDB prefix format
                # Keys look like: _file://\x00\x01/.../index.html:keyName
                if ":" in key_str:
                    key_name = key_str.split(":")[-1]
                else:
                    key_name = key_str

                # Strip leading \x01 byte from value if present
                value_str = value_bytes.decode("utf-8", errors="replace")
                if value_str.startswith("\x01"):
                    value_str = value_str[1:]

                result[key_name] = try_decode_value(value_str)

            except (UnicodeDecodeError, ValueError):
                continue
    finally:
        db.close()

    return result


def read_raw(db_path: Path) -> dict[str, Any]:
    """
    Read IdleOn save data using raw file parsing (no external dependencies).

    Scans .log and .ldb files in the LevelDB directory for save data.

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

    # Parse .ldb files (SSTables)
    ldb_files = sorted(db_path.glob("*.ldb"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ldb_file in ldb_files:
        pairs = _read_ldb_file(ldb_file)
        for key_bytes, value_bytes in pairs:
            try:
                key_str = key_bytes.decode("utf-8", errors="replace") if isinstance(key_bytes, bytes) else str(key_bytes)
                value_str = value_bytes.decode("utf-8", errors="replace") if isinstance(value_bytes, bytes) else str(value_bytes)

                if value_str.startswith("\x01"):
                    value_str = value_str[1:]

                # Only add if not already found (log files are more recent)
                if key_str not in result:
                    result[key_str] = try_decode_value(value_str)

            except (UnicodeDecodeError, ValueError):
                continue

    return result


def read_save_data(db_path: Path, idleon_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Read IdleOn save data, trying plyvel first and falling back to raw parsing.

    Args:
        db_path: Path to the LevelDB directory.
        idleon_path: Optional path to the IdleOn installation.

    Returns:
        Dictionary of decoded save data.
    """
    # Try plyvel first
    try:
        import plyvel
        print("[*] Using plyvel for LevelDB access...")
        return read_with_plyvel(db_path, idleon_path)
    except ImportError:
        print("[*] plyvel not available, using raw file parser...")
    except Exception as e:
        print(f"[!] plyvel failed ({e}), falling back to raw parser...")

    # Fallback to raw parsing
    return read_raw(db_path)
