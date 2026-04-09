"""
Tests for the progress analyzer.
"""

import pytest
from idleon_reader.progress import (
    extract_characters,
    extract_account_info,
    extract_progress_summary,
    format_progress_report,
    CLASS_NAMES,
    SKILL_NAMES,
)


@pytest.fixture
def sample_save_data():
    """Create a sample save data dict that mimics IdleOn structure."""
    return {
        "mySave": {
            "PlayerNames": ["TestPlayer", "WarriorGuy", "MageLord"],
            "CharacterClass_0": 1,   # Journeyman
            "CharacterClass_1": 7,   # Blood Berserker
            "CharacterClass_2": 23,  # Bubonic Conjuror
            "Level": [50, 120, 95],
            "SkillLevels_0": [50, 30, 20, 25, 15, 10, 5, 0, 0, 0],
            "SkillLevels_1": [120, 80, 45, 10, 5, 0, 0, 0, 0, 0],
            "SkillLevels_2": [95, 10, 5, 15, 40, 60, 70, 0, 0, 0],
            "Money": 1500000,
            "GemsOwned": 250,
            "AFKtarget": [0, 1, 5],
            "AFKtype": [0, 1, 4],
            "Cards": {"card1": 1, "card2": 3, "card3": 0},
            "Stamps": [[1, 2, 0], [3, 0, 1]],
            "Statues": [1, 2, 0, 3, 0, 0, 1],
        }
    }


class TestExtractCharacters:
    def test_extracts_correct_count(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        assert len(chars) == 3

    def test_character_names(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        assert chars[0]["name"] == "TestPlayer"
        assert chars[1]["name"] == "WarriorGuy"
        assert chars[2]["name"] == "MageLord"

    def test_character_classes(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        assert chars[0]["class"] == "Journeyman"
        assert chars[1]["class"] == "Blood Berserker"
        assert chars[2]["class"] == "Bubonic Conjuror"

    def test_character_levels(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        assert chars[0]["level"] == 50
        assert chars[1]["level"] == 120
        assert chars[2]["level"] == 95

    def test_character_skills(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        skills_0 = chars[0]["skills"]
        assert "Character" in skills_0
        assert skills_0["Character"] == 50
        assert skills_0["Mining"] == 30

    def test_afk_activity(self, sample_save_data):
        chars = extract_characters(sample_save_data)
        assert chars[0]["afk_activity"] == "Fighting"
        assert chars[1]["afk_activity"] == "Mining"
        assert chars[2]["afk_activity"] == "Catching"

    def test_empty_data(self):
        chars = extract_characters({})
        assert chars == []

    def test_missing_fields(self):
        data = {
            "mySave": {
                "CharacterClass_0": 0,
            }
        }
        chars = extract_characters(data)
        assert len(chars) == 1
        assert chars[0]["class"] == "Beginner"


class TestExtractAccountInfo:
    def test_money(self, sample_save_data):
        info = extract_account_info(sample_save_data)
        assert info["money"] == 1500000

    def test_gems(self, sample_save_data):
        info = extract_account_info(sample_save_data)
        assert info["gems"] == 250

    def test_cards_counted(self, sample_save_data):
        info = extract_account_info(sample_save_data)
        assert info["cards_collected"] == 3  # dict has 3 keys

    def test_statues_counted(self, sample_save_data):
        info = extract_account_info(sample_save_data)
        assert info["statues_collected"] == 4  # 4 non-zero values

    def test_empty_data(self):
        info = extract_account_info({})
        assert info == {}


class TestProgressSummary:
    def test_summary_structure(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        assert "extraction_time" in summary
        assert "account" in summary
        assert "characters" in summary
        assert "recognized_keys" in summary

    def test_summary_characters(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        assert len(summary["characters"]) == 3


class TestFormatReport:
    def test_report_contains_header(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        report = format_progress_report(summary)
        assert "LEGENDS OF IDLEON" in report
        assert "SPIELERFORTSCHRITT" in report

    def test_report_contains_characters(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        report = format_progress_report(summary)
        assert "TestPlayer" in report
        assert "Journeyman" in report
        assert "Blood Berserker" in report

    def test_report_contains_account_info(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        report = format_progress_report(summary)
        assert "1,500,000" in report or "1500000" in report
        assert "250" in report

    def test_report_contains_disclaimer(self, sample_save_data):
        summary = extract_progress_summary(sample_save_data)
        report = format_progress_report(summary)
        assert "nicht veraendert" in report


class TestClassNames:
    def test_all_base_classes(self):
        assert CLASS_NAMES[0] == "Beginner"
        assert CLASS_NAMES[4] == "Warrior"
        assert CLASS_NAMES[11] == "Archer"
        assert CLASS_NAMES[18] == "Mage"

    def test_subclasses(self):
        assert CLASS_NAMES[7] == "Blood Berserker"
        assert CLASS_NAMES[16] == "Wind Walker"
        assert CLASS_NAMES[23] == "Bubonic Conjuror"


class TestSkillNames:
    def test_base_skills(self):
        assert SKILL_NAMES[0] == "Character"
        assert SKILL_NAMES[1] == "Mining"
        assert SKILL_NAMES[3] == "Choppin'"

    def test_world_skills(self):
        assert SKILL_NAMES[8] == "Construction"
        assert SKILL_NAMES[12] == "Sailing"
        assert SKILL_NAMES[16] == "Sneaking"
