from __future__ import annotations

import pytest

from idleon_reader.save_accounts import (
    SaveAccountSelectionError,
    discover_save_accounts,
    select_save_account,
)


def _multi_account_data():
    return {
        "primary": {
            "Money": 111,
            "PlayerDATABASE": {
                "Alpha": {"CharacterClass": 1},
            },
        },
        "secondary": {
            "Money": 222,
            "PlayerDATABASE": {
                "Beta": {"CharacterClass": 2},
            },
        },
    }


def test_discover_save_accounts_finds_multiple_candidates():
    candidates = discover_save_accounts(_multi_account_data())

    assert [candidate.selector for candidate in candidates] == ["primary", "secondary"]
    assert candidates[0].character_names == ("Alpha",)
    assert candidates[1].character_names == ("Beta",)


def test_select_save_account_by_selector_wraps_selected_save():
    selected_data, selected_candidate, candidates = select_save_account(
        _multi_account_data(),
        selector="secondary",
        allow_prompt=False,
    )

    assert selected_candidate is not None
    assert selected_candidate.selector == "secondary"
    assert len(candidates) == 2
    assert tuple(selected_data["mySave"]["PlayerDATABASE"]) == ("Beta",)


def test_select_save_account_requires_choice_when_multiple_candidates_exist():
    with pytest.raises(SaveAccountSelectionError):
        select_save_account(_multi_account_data(), allow_prompt=False)
