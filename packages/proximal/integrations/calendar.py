from __future__ import annotations


def create_event(title: str, start: str, end: str, location: str | None = None) -> None:
    """Placeholder calendar event creator."""
    print(f"Event '{title}' from {start} to {end} at {location or 'TBD'}")
