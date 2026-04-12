from __future__ import annotations

from pathlib import Path

import pytest

from idleon_reader.save_guard import SaveGuardError, ensure_save_ready, evaluate_save_health


def test_ensure_save_ready_requires_existing_directory(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(SaveGuardError, match="existiert nicht"):
        ensure_save_ready(missing, stability_wait_seconds=0)


def test_ensure_save_ready_rejects_running_process(monkeypatch, tmp_path):
    (tmp_path / "000001.log").write_bytes(b"abc")
    monkeypatch.setattr("idleon_reader.save_guard.find_idleon_processes", lambda: ["IdleOn.exe"])

    with pytest.raises(SaveGuardError, match="scheint noch zu laufen"):
        ensure_save_ready(tmp_path, stability_wait_seconds=0)


def test_ensure_save_ready_rejects_changing_files(monkeypatch, tmp_path):
    file_path = tmp_path / "000001.log"
    file_path.write_bytes(b"abc")
    monkeypatch.setattr("idleon_reader.save_guard.find_idleon_processes", lambda: [])

    snapshots = [
        (("000001.log", 3, 1),),
        (("000001.log", 4, 2),),
    ]
    monkeypatch.setattr("idleon_reader.save_guard._snapshot_files", lambda _path: snapshots.pop(0))

    with pytest.raises(SaveGuardError, match="verändern sich noch|veraendern sich noch"):
        ensure_save_ready(tmp_path, stability_wait_seconds=0)


def test_evaluate_save_health_accepts_plausible_save():
    health = evaluate_save_health(
        {
            "mySave": {
                "Money": 1,
                "GemsOwned": 2,
                "Cards": {},
                "PlayerNames": ["Alpha"],
                "PlayerDATABASE": {
                    "Alpha": {
                        "CharacterClass": 1,
                        "Lv0": [1],
                        "CurrentMap": 2,
                    }
                },
            }
        }
    )

    assert health.key_count == 5
    assert health.character_count == 1
    assert health.global_indicator_count >= 2
    assert health.character_indicator_count >= 2


def test_evaluate_save_health_rejects_missing_player_database():
    with pytest.raises(SaveGuardError, match="PlayerDATABASE fehlt oder ist leer"):
        evaluate_save_health({"mySave": {"Money": 1}})


def test_evaluate_save_health_rejects_degraded_save():
    with pytest.raises(SaveGuardError, match="unvollständig|unvollstaendig"):
        evaluate_save_health(
            {
                "mySave": {
                    "Money": 1,
                    "PlayerDATABASE": {
                        "Alpha": {
                            "CharacterClass": 1,
                        }
                    },
                }
            }
        )
