"""Profile management utilities.

Pure functions for creating and updating user profiles.
"""

from __future__ import annotations

from typing import Any

from packages.core.models import UserProfile


def create_default_profile() -> UserProfile:
    """Create a new user profile with all default values.

    Returns
    -------
    UserProfile
        A fresh profile with a unique auto-generated user_id.
    """
    return UserProfile()


def merge_profile_updates(
    existing: UserProfile,
    updates: dict[str, Any],
) -> UserProfile:
    """Create a new profile by merging updates into an existing one.

    Unknown keys in *updates* are silently ignored. The ``user_id`` is
    always preserved from the original profile.

    Parameters
    ----------
    existing : UserProfile
        The current profile to base the merge on.
    updates : dict[str, Any]
        A dict of field names to new values. Only known UserProfile
        fields are applied; unknown keys are ignored.

    Returns
    -------
    UserProfile
        A new UserProfile instance with the merged values.
    """
    # start from existing data
    current_data = existing.model_dump()

    # only apply keys that are valid UserProfile fields
    valid_fields = set(UserProfile.model_fields.keys())
    filtered_updates = {k: v for k, v in updates.items() if k in valid_fields}

    # merge, but always preserve user_id
    current_data.update(filtered_updates)
    current_data["user_id"] = existing.user_id

    return UserProfile(**current_data)
