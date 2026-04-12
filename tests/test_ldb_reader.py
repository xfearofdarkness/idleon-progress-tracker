from pathlib import Path

import pytest

from idleon_reader import ldb_reader


def test_read_save_data_uses_leveldbutil_first(monkeypatch, capsys):
    monkeypatch.setattr(ldb_reader, "read_with_leveldbutil", lambda _path: {"mySave": {"Money": 1}})

    def fail_raw(_path):
        raise AssertionError("raw parser should not be used when leveldbutil succeeds")

    monkeypatch.setattr(ldb_reader, "read_raw", fail_raw)

    result = ldb_reader.read_save_data(Path("/tmp/fake-db"))

    output = capsys.readouterr().out
    assert result == {"mySave": {"Money": 1}}
    assert "Trying leveldbutil dump..." in output
    assert "Falling back to raw log parser..." not in output


def test_read_save_data_falls_back_when_leveldbutil_returns_no_entries(monkeypatch, capsys):
    monkeypatch.setattr(ldb_reader, "read_with_leveldbutil", lambda _path: {})
    monkeypatch.setattr(ldb_reader, "read_raw", lambda _path: {"mySave": {"Money": 2}})

    result = ldb_reader.read_save_data(Path("/tmp/fake-db"))

    output = capsys.readouterr().out
    assert result == {"mySave": {"Money": 2}}
    assert "leveldbutil produced no decoded save entries" in output
    assert "Falling back to raw log parser..." in output


def test_read_with_leveldbutil_raises_when_all_file_dumps_fail(tmp_path, monkeypatch):
    (tmp_path / "000002.ldb").write_bytes(b"")

    def fail(_path):
        raise ldb_reader.subprocess.CalledProcessError(returncode=1, cmd="leveldbutil dump", output="bad file")

    monkeypatch.setattr(ldb_reader, "_iter_leveldbutil_entries", fail)

    with pytest.raises(ldb_reader.subprocess.CalledProcessError) as exc_info:
        ldb_reader.read_with_leveldbutil(tmp_path)

    assert "000002.ldb" in str(exc_info.value.output)


def test_read_with_leveldbutil_ignores_log_only_directories(tmp_path, monkeypatch):
    (tmp_path / "000001.log").write_bytes(b"")

    def fail(_path):
        raise AssertionError("leveldbutil should not be called for .log files")

    monkeypatch.setattr(ldb_reader, "_iter_leveldbutil_entries", fail)

    assert ldb_reader.read_with_leveldbutil(tmp_path) == {}


def test_read_raw_can_recover_my_save_from_ldb_heuristic(tmp_path):
    payload = b'prefixmySave\x01{"Money":123,"PlayerDATABASE":{"Alpha":{"CharacterClass":1}}}\x00suffix'
    (tmp_path / "000003.ldb").write_bytes(payload)

    result = ldb_reader.read_raw(tmp_path)

    assert "mySave" in result
    assert result["mySave"]["Money"] == 123
    assert "Alpha" in result["mySave"]["PlayerDATABASE"]
