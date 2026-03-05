from packages.core.models import UserProfile
from packages.core.profiles import create_default_profile, merge_profile_updates

# ---------------------------------------------------------------------------
# UserProfile model
# ---------------------------------------------------------------------------


class TestUserProfile:
    """Tests for the UserProfile pydantic model."""

    def test_default_construction(self):
        """Should create a profile with all default values."""
        profile = UserProfile()
        assert profile.name == "Friend"
        assert profile.focus_style == "variable"
        assert profile.transition_difficulty == "moderate"
        assert profile.time_blindness == "moderate"
        assert profile.decision_fatigue == "moderate"
        assert profile.overwhelm_threshold == 5
        assert profile.peak_hours == [10, 11, 14, 15]
        assert profile.low_energy_days == []
        assert profile.max_daily_hours == 6.0
        assert profile.preferred_session_minutes == 25
        assert profile.tone == "warm"
        assert profile.verbosity == "medium"
        assert profile.celebration_style == "quiet"

    def test_user_id_auto_generated(self):
        """Each profile should get a unique auto-generated user_id."""
        p1 = UserProfile()
        p2 = UserProfile()
        assert isinstance(p1.user_id, str)
        assert len(p1.user_id) == 8
        assert p1.user_id != p2.user_id

    def test_custom_values(self):
        """Should accept custom values for all fields."""
        profile = UserProfile(
            name="Ada",
            focus_style="hyperfocus",
            transition_difficulty="high",
            time_blindness="high",
            decision_fatigue="low",
            overwhelm_threshold=3,
            peak_hours=[9, 10],
            low_energy_days=["Monday"],
            max_daily_hours=4.0,
            preferred_session_minutes=15,
            tone="direct",
            verbosity="minimal",
            celebration_style="data-driven",
        )
        assert profile.name == "Ada"
        assert profile.focus_style == "hyperfocus"
        assert profile.overwhelm_threshold == 3
        assert profile.tone == "direct"
        assert profile.celebration_style == "data-driven"

    def test_serialization_roundtrip(self):
        """Profile should survive json serialization and deserialization."""
        original = UserProfile(name="Test")
        data = original.model_dump()
        restored = UserProfile(**data)
        assert restored.name == original.name
        assert restored.user_id == original.user_id
        assert restored.peak_hours == original.peak_hours

    def test_to_prompt_context_returns_string(self):
        """to_prompt_context should return a non-empty string."""
        profile = UserProfile()
        ctx = profile.to_prompt_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_to_prompt_context_contains_name(self):
        """Prompt context should reference the user's name."""
        profile = UserProfile(name="Jordan")
        ctx = profile.to_prompt_context()
        assert "Jordan" in ctx

    def test_to_prompt_context_contains_tone(self):
        """Prompt context should reference the communication tone."""
        profile = UserProfile(tone="playful")
        ctx = profile.to_prompt_context()
        assert "playful" in ctx.lower()

    def test_to_prompt_context_contains_focus_style(self):
        """Prompt context should reference focus style."""
        profile = UserProfile(focus_style="hyperfocus")
        ctx = profile.to_prompt_context()
        assert "hyperfocus" in ctx.lower()

    def test_to_prompt_context_contains_session_duration(self):
        """Prompt context should reference session minutes."""
        profile = UserProfile(preferred_session_minutes=50)
        ctx = profile.to_prompt_context()
        assert "50" in ctx

    def test_to_prompt_context_contains_overwhelm_threshold(self):
        """Prompt context should reference overwhelm threshold."""
        profile = UserProfile(overwhelm_threshold=3)
        ctx = profile.to_prompt_context()
        assert "3" in ctx


# ---------------------------------------------------------------------------
# create_default_profile
# ---------------------------------------------------------------------------


class TestCreateDefaultProfile:
    """Tests for the create_default_profile function."""

    def test_returns_user_profile(self):
        """Should return a UserProfile instance."""
        profile = create_default_profile()
        assert isinstance(profile, UserProfile)

    def test_has_unique_id(self):
        """Each default profile should have a unique id."""
        p1 = create_default_profile()
        p2 = create_default_profile()
        assert p1.user_id != p2.user_id

    def test_default_name(self):
        """Default profile should use the default name."""
        profile = create_default_profile()
        assert profile.name == "Friend"


# ---------------------------------------------------------------------------
# merge_profile_updates
# ---------------------------------------------------------------------------


class TestMergeProfileUpdates:
    """Tests for the merge_profile_updates function."""

    def test_applies_partial_update(self):
        """Should update only specified fields."""
        original = UserProfile(name="Original", tone="warm")
        updated = merge_profile_updates(original, {"tone": "direct"})
        assert updated.tone == "direct"
        assert updated.name == "Original"

    def test_preserves_user_id(self):
        """Merging should not change the user_id."""
        original = UserProfile()
        updated = merge_profile_updates(original, {"name": "New Name"})
        assert updated.user_id == original.user_id

    def test_multiple_fields(self):
        """Should update multiple fields simultaneously."""
        original = UserProfile()
        updates = {
            "name": "Alex",
            "focus_style": "short-burst",
            "tone": "professional",
            "max_daily_hours": 4.0,
        }
        updated = merge_profile_updates(original, updates)
        assert updated.name == "Alex"
        assert updated.focus_style == "short-burst"
        assert updated.tone == "professional"
        assert updated.max_daily_hours == 4.0

    def test_empty_updates_returns_copy(self):
        """Empty updates dict should return a profile equal to the original."""
        original = UserProfile(name="Same")
        updated = merge_profile_updates(original, {})
        assert updated.name == "Same"
        assert updated.user_id == original.user_id

    def test_returns_new_instance(self):
        """Should return a new instance, not mutate the original."""
        original = UserProfile(name="Before")
        updated = merge_profile_updates(original, {"name": "After"})
        assert original.name == "Before"
        assert updated.name == "After"

    def test_ignores_unknown_fields(self):
        """Unknown keys in updates should be ignored, not raise errors."""
        original = UserProfile()
        updated = merge_profile_updates(original, {"nonexistent_field": "value"})
        assert updated.name == original.name
