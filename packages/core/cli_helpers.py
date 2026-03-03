"""Progressive disclosure CLI helpers.

Separated from apps/cli.py to avoid merge conflicts with Phase 1 changes.
These functions produce formatted strings or interact with the user via
rich prompts. The main CLI module integrates them as needed.

Progressive CLI levels:
  level 1: proximal "Build a portfolio website"
  level 2: proximal plan "Build a website" --energy low
  level 3: proximal chat
  level 4: proximal --provider anthropic plan "Complex project"
"""

from __future__ import annotations

from typing import Any, Optional

from rich.console import Console
from rich.prompt import Prompt

from packages.core.models import EnergyLevel, UserProfile

# shared console instance for display helpers
_console = Console()


# ---------------------------------------------------------------------------
# plan display
# ---------------------------------------------------------------------------


def display_plan_compact(plan_data: list[dict[str, Any]]) -> str:
    """Render a plan as a compact single-line-per-task summary.

    Parameters
    ----------
    plan_data : list[dict[str, Any]]
        Plan data — a list of sprint dicts each containing a ``tasks`` list.

    Returns
    -------
    str
        Plain-text compact summary suitable for quick terminal output.
    """
    if not plan_data:
        return "No tasks in plan."

    lines: list[str] = []
    for sprint in plan_data:
        lines.append(f"== {sprint.get('name', 'Sprint')} ==")
        for task in sprint.get("tasks", []):
            status = "x" if task.get("done") else " "
            lines.append(
                f"  [{status}] {task.get('priority', '?')} "
                f"{task.get('title', 'Untitled')} "
                f"({task.get('estimate_h', '?')}h)"
            )
    return "\n".join(lines)


def display_plan_detailed(plan_data: list[dict[str, Any]]) -> str:
    """Render a plan as a detailed rich-table string.

    Parameters
    ----------
    plan_data : list[dict[str, Any]]
        Plan data — a list of sprint dicts each containing a ``tasks`` list.

    Returns
    -------
    str
        A detailed multi-line string with tables, dates, and summaries.
    """
    if not plan_data:
        return "No tasks in plan."

    lines: list[str] = []
    total_tasks = 0
    total_hours = 0

    for sprint in plan_data:
        name = sprint.get("name", "Sprint")
        start = sprint.get("start", "?")
        end = sprint.get("end", "?")
        lines.append(f"Sprint: {name}")
        lines.append(f"  Period: {start} to {end}")
        lines.append(
            f"  {'ID':<10} {'Task':<30} {'Priority':<10} "
            f"{'Hours':>6} {'Status':>8}"
        )
        lines.append(f"  {'-' * 70}")

        for task in sprint.get("tasks", []):
            tid = task.get("id", "?")
            title = task.get("title", "Untitled")
            priority = task.get("priority", "?")
            hours = task.get("estimate_h", 0)
            done = "Done" if task.get("done") else "Todo"
            lines.append(
                f"  {tid:<10} {title:<30} {priority:<10} "
                f"{hours:>6} {done:>8}"
            )
            total_tasks += 1
            total_hours += hours

        lines.append("")

    lines.append(f"Total: {total_tasks} tasks, {total_hours} hours")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# interactive prompts
# ---------------------------------------------------------------------------


def prompt_energy_level() -> EnergyLevel:
    """Ask the user to choose their current energy level.

    Returns
    -------
    EnergyLevel
        The selected energy level.
    """
    _console.print("\nHow is your energy right now?\n")
    _console.print("  1) Low   - Keep it gentle, short tasks only")
    _console.print("  2) Medium - A balanced session")
    _console.print("  3) High  - Ready for deep work\n")

    choice = Prompt.ask("Select", choices=["1", "2", "3"], default="2")

    mapping = {
        "1": EnergyLevel.low,
        "2": EnergyLevel.medium,
        "3": EnergyLevel.high,
    }
    return mapping[choice]


def prompt_profile_setup() -> UserProfile:
    """Run a first-run conversational profile builder.

    Asks the user a small set of questions and returns a populated
    UserProfile. Keeps it brief to avoid overwhelm.

    Returns
    -------
    UserProfile
        A newly created profile based on user responses.
    """
    _console.print("\nLet's set up your profile.\n")

    # name
    name = Prompt.ask("What should I call you?", default="Friend")
    if not name.strip():
        name = "Friend"

    # focus style
    _console.print("\nHow would you describe your focus style?")
    _console.print("  1) Hyperfocus - Long deep dives, hard to switch")
    _console.print("  2) Variable   - Depends on the day")
    _console.print("  3) Short-burst - Best in quick sprints\n")
    focus_choice = Prompt.ask("Select", choices=["1", "2", "3"], default="2")
    focus_map = {"1": "hyperfocus", "2": "variable", "3": "short-burst"}
    focus_style = focus_map[focus_choice]

    # transition difficulty
    _console.print("\nHow hard is switching between tasks?")
    _console.print("  1) Low      - Easy to switch")
    _console.print("  2) Moderate - Takes a moment")
    _console.print("  3) High     - Really struggle with transitions\n")
    trans_choice = Prompt.ask("Select", choices=["1", "2", "3"], default="2")
    trans_map = {"1": "low", "2": "moderate", "3": "high"}
    transition_difficulty = trans_map[trans_choice]

    # tone
    tone = Prompt.ask(
        "Preferred tone (warm / professional / direct / playful)",
        default="warm",
    )

    return UserProfile(
        name=name,
        focus_style=focus_style,
        transition_difficulty=transition_difficulty,
        tone=tone,
    )


# ---------------------------------------------------------------------------
# flag parsing helpers
# ---------------------------------------------------------------------------


def parse_energy_flag(value: str) -> Optional[EnergyLevel]:
    """Parse a CLI --energy or --low-spoons flag value into an EnergyLevel.

    Parameters
    ----------
    value : str
        The raw flag string (e.g. "low", "medium", "high", "low-spoons").

    Returns
    -------
    EnergyLevel or None
        The corresponding energy level, or None if the value is invalid.
    """
    if not value:
        return None

    normalised = value.strip().lower()

    # handle --low-spoons alias
    if normalised == "low-spoons":
        return EnergyLevel.low

    try:
        return EnergyLevel(normalised)
    except ValueError:
        return None
