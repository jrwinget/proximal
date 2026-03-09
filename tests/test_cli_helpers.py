from unittest.mock import patch

import pytest

from packages.core.cli_helpers import (
    display_plan_compact,
    display_plan_detailed,
    parse_energy_flag,
    prompt_energy_level,
    prompt_profile_setup,
)
from packages.core.models import EnergyLevel, UserProfile

# ---------------------------------------------------------------------------
# sample fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_plan():
    """Minimal plan data for display testing."""
    return [
        {
            "name": "Sprint 1",
            "start": "2025-01-01",
            "end": "2025-01-14",
            "tasks": [
                {
                    "id": "abc1",
                    "title": "Set up project",
                    "detail": "Initialize repo and dependencies",
                    "priority": "P1",
                    "estimate_h": 4,
                    "done": False,
                },
                {
                    "id": "abc2",
                    "title": "Design schema",
                    "detail": "Create the data model",
                    "priority": "P0",
                    "estimate_h": 6,
                    "done": True,
                },
            ],
        }
    ]


# ---------------------------------------------------------------------------
# display_plan_compact
# ---------------------------------------------------------------------------


class TestDisplayPlanCompact:
    """Tests for the compact plan display function."""

    def test_returns_string(self, sample_plan):
        """Should return a non-empty string."""
        output = display_plan_compact(sample_plan)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_contains_task_titles(self, sample_plan):
        """Output should include task titles."""
        output = display_plan_compact(sample_plan)
        assert "Set up project" in output
        assert "Design schema" in output

    def test_contains_sprint_name(self, sample_plan):
        """Output should include sprint name."""
        output = display_plan_compact(sample_plan)
        assert "Sprint 1" in output

    def test_empty_plan(self):
        """Should handle empty plan gracefully."""
        output = display_plan_compact([])
        assert isinstance(output, str)

    def test_compact_is_shorter_than_detailed(self, sample_plan):
        """Compact output should be shorter than detailed output."""
        compact = display_plan_compact(sample_plan)
        detailed = display_plan_detailed(sample_plan)
        assert len(compact) <= len(detailed)


# ---------------------------------------------------------------------------
# display_plan_detailed
# ---------------------------------------------------------------------------


class TestDisplayPlanDetailed:
    """Tests for the detailed plan display function."""

    def test_returns_string(self, sample_plan):
        """Should return a non-empty string."""
        output = display_plan_detailed(sample_plan)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_contains_task_details(self, sample_plan):
        """Output should include task details and estimates."""
        output = display_plan_detailed(sample_plan)
        assert "Set up project" in output
        assert "P1" in output or "P0" in output

    def test_contains_sprint_dates(self, sample_plan):
        """Output should include sprint date range."""
        output = display_plan_detailed(sample_plan)
        assert "2025-01-01" in output
        assert "2025-01-14" in output

    def test_contains_hours(self, sample_plan):
        """Output should show hour estimates."""
        output = display_plan_detailed(sample_plan)
        # should contain total or per-task hours
        assert "4" in output or "6" in output

    def test_empty_plan(self):
        """Should handle empty plan gracefully."""
        output = display_plan_detailed([])
        assert isinstance(output, str)


# ---------------------------------------------------------------------------
# prompt_energy_level
# ---------------------------------------------------------------------------


class TestPromptEnergyLevel:
    """Tests for the energy level prompting function."""

    @patch("packages.core.cli_helpers.Prompt.ask", return_value="1")
    def test_returns_low(self, mock_ask):
        """Selecting option 1 should return low energy."""
        result = prompt_energy_level()
        assert result == EnergyLevel.low

    @patch("packages.core.cli_helpers.Prompt.ask", return_value="2")
    def test_returns_medium(self, mock_ask):
        """Selecting option 2 should return medium energy."""
        result = prompt_energy_level()
        assert result == EnergyLevel.medium

    @patch("packages.core.cli_helpers.Prompt.ask", return_value="3")
    def test_returns_high(self, mock_ask):
        """Selecting option 3 should return high energy."""
        result = prompt_energy_level()
        assert result == EnergyLevel.high

    @patch("packages.core.cli_helpers.Prompt.ask", return_value="2")
    def test_returns_energy_level_type(self, mock_ask):
        """Should return an EnergyLevel instance."""
        result = prompt_energy_level()
        assert isinstance(result, EnergyLevel)


# ---------------------------------------------------------------------------
# prompt_profile_setup
# ---------------------------------------------------------------------------


class TestPromptProfileSetup:
    """Tests for the profile setup prompting function."""

    @patch("packages.core.cli_helpers.Prompt.ask")
    def test_returns_user_profile(self, mock_ask):
        """Should return a UserProfile instance."""
        mock_ask.side_effect = [
            "Ada",  # name
            "2",  # focus_style -> variable
            "2",  # transition_difficulty -> moderate
            "warm",  # tone
        ]
        profile = prompt_profile_setup()
        assert isinstance(profile, UserProfile)

    @patch("packages.core.cli_helpers.Prompt.ask")
    def test_sets_name(self, mock_ask):
        """Should set the name from user input."""
        mock_ask.side_effect = [
            "Jordan",
            "1",  # focus_style
            "1",  # transition_difficulty
            "direct",  # tone
        ]
        profile = prompt_profile_setup()
        assert profile.name == "Jordan"

    @patch("packages.core.cli_helpers.Prompt.ask")
    def test_default_name_on_empty(self, mock_ask):
        """Empty name input should use the default name."""
        mock_ask.side_effect = [
            "",  # empty name
            "2",
            "2",
            "warm",
        ]
        profile = prompt_profile_setup()
        assert profile.name == "Friend"


# ---------------------------------------------------------------------------
# parse_energy_flag
# ---------------------------------------------------------------------------


class TestParseEnergyFlag:
    """Tests for parsing CLI energy flag values."""

    def test_parse_low(self):
        """'low' string should parse to EnergyLevel.low."""
        assert parse_energy_flag("low") == EnergyLevel.low

    def test_parse_medium(self):
        """'medium' string should parse to EnergyLevel.medium."""
        assert parse_energy_flag("medium") == EnergyLevel.medium

    def test_parse_high(self):
        """'high' string should parse to EnergyLevel.high."""
        assert parse_energy_flag("high") == EnergyLevel.high

    def test_parse_case_insensitive(self):
        """Should handle mixed case input."""
        assert parse_energy_flag("LOW") == EnergyLevel.low
        assert parse_energy_flag("Medium") == EnergyLevel.medium

    def test_low_spoons_alias(self):
        """'low-spoons' should map to EnergyLevel.low."""
        assert parse_energy_flag("low-spoons") == EnergyLevel.low

    def test_invalid_returns_none(self):
        """Invalid string should return None."""
        assert parse_energy_flag("invalid") is None
        assert parse_energy_flag("") is None
