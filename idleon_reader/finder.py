"""
Save File Finder

Locates IdleOn save data on various operating systems.
IdleOn stores its data as an Electron app using LevelDB in the Local Storage path.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional


# CrossOver stores Windows app data inside bottle directories on macOS.
CROSSOVER_BOTTLE_ROOT = (
    Path.home() / "Library" / "Application Support" / "CrossOver" / "Bottles"
)


def _crossover_save_paths() -> list[Path]:
    """Collect possible IdleOn save paths from CrossOver bottles on macOS."""
    if not CROSSOVER_BOTTLE_ROOT.exists():
        return []

    candidates = []
    for bottle_dir in CROSSOVER_BOTTLE_ROOT.iterdir():
        if not bottle_dir.is_dir():
            continue

        roaming = (
            bottle_dir
            / "drive_c"
            / "users"
            / "crossover"
            / "AppData"
            / "Roaming"
            / "legends-of-idleon"
        )
        candidates.extend(
            [
                roaming / "Local Storage" / "leveldb",
                roaming / "IndexedDB" / "file__0.indexeddb.leveldb",
            ]
        )

    return candidates


def _crossover_install_paths() -> list[Path]:
    """Collect possible IdleOn install paths from CrossOver Steam bottles on macOS."""
    if not CROSSOVER_BOTTLE_ROOT.exists():
        return []

    candidates = []
    for bottle_dir in CROSSOVER_BOTTLE_ROOT.iterdir():
        if not bottle_dir.is_dir():
            continue

        candidates.extend(
            [
                bottle_dir
                / "drive_c"
                / "Program Files (x86)"
                / "Steam"
                / "steamapps"
                / "common"
                / "Legends of Idleon",
                bottle_dir
                / "drive_c"
                / "Program Files"
                / "Steam"
                / "steamapps"
                / "common"
                / "Legends of Idleon",
            ]
        )

    return candidates


# Known save file locations by OS
SAVE_PATHS = {
    "Windows": [
        # Primary: Electron Local Storage
        Path(os.environ.get("APPDATA", "")) / "legends-of-idleon" / "Local Storage" / "leveldb",
        # Alternative: IndexedDB
        Path(os.environ.get("APPDATA", ""))
        / "legends-of-idleon"
        / "IndexedDB"
        / "file__0.indexeddb.leveldb",
    ],
    "Darwin": [  # macOS
        Path.home()
        / "Library"
        / "Application Support"
        / "legends-of-idleon"
        / "Local Storage"
        / "leveldb",
        Path.home()
        / "Library"
        / "Application Support"
        / "legends-of-idleon"
        / "IndexedDB"
        / "file__0.indexeddb.leveldb",
    ] + _crossover_save_paths(),
    "Linux": [
        Path.home() / ".config" / "legends-of-idleon" / "Local Storage" / "leveldb",
        Path.home()
        / ".config"
        / "legends-of-idleon"
        / "IndexedDB"
        / "file__0.indexeddb.leveldb",
    ],
}

# Common Steam installation paths for the IdleOn executable
STEAM_IDLEON_PATHS = {
    "Windows": [
        Path("C:/Program Files (x86)/Steam/steamapps/common/Legends of Idleon"),
        Path("C:/Program Files/Steam/steamapps/common/Legends of Idleon"),
    ],
    "Darwin": [
        Path.home()
        / "Library"
        / "Application Support"
        / "Steam"
        / "steamapps"
        / "common"
        / "Legends of Idleon",
    ] + _crossover_install_paths(),
    "Linux": [
        Path.home() / ".steam" / "steam" / "steamapps" / "common" / "Legends of Idleon",
        Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Legends of Idleon",
    ],
}


def get_os_name() -> str:
    """Get the normalized OS name."""
    return platform.system()


def find_save_directory() -> Optional[Path]:
    """
    Automatically find the IdleOn save data directory.

    Returns:
        Path to the LevelDB directory, or None if not found.
    """
    os_name = get_os_name()
    candidates = SAVE_PATHS.get(os_name, [])

    for path in candidates:
        if path.exists() and path.is_dir():
            # Verify it contains LevelDB files
            ldb_files = list(path.glob("*.ldb")) + list(path.glob("*.log"))
            if ldb_files:
                return path

    return None


def find_idleon_installation() -> Optional[Path]:
    """
    Find the IdleOn game installation directory (needed for LevelDB key construction).

    Returns:
        Path to the IdleOn installation, or None if not found.
    """
    os_name = get_os_name()
    candidates = STEAM_IDLEON_PATHS.get(os_name, [])

    for path in candidates:
        if path.exists() and path.is_dir():
            return path

    return None


def list_ldb_files(directory: Path) -> list[Path]:
    """List all LevelDB-related files in the given directory."""
    extensions = ["*.ldb", "*.log", "*.sst", "*.MANIFEST*", "CURRENT", "LOCK"]
    files = []
    for ext in extensions:
        files.extend(directory.glob(ext))
    return sorted(files)


def get_save_info() -> dict:
    """
    Get comprehensive information about the save file location.

    Returns:
        Dictionary with save path info and status.
    """
    save_dir = find_save_directory()
    install_dir = find_idleon_installation()

    info = {
        "os": get_os_name(),
        "save_directory": str(save_dir) if save_dir else None,
        "save_found": save_dir is not None,
        "installation_directory": str(install_dir) if install_dir else None,
        "installation_found": install_dir is not None,
    }

    if save_dir:
        files = list_ldb_files(save_dir)
        info["ldb_files"] = [str(f) for f in files]
        info["ldb_file_count"] = len(files)
        total_size = sum(f.stat().st_size for f in files if f.exists())
        info["total_size_bytes"] = total_size
        info["total_size_kb"] = round(total_size / 1024, 2)

    return info
