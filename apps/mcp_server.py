"""MCP server exposing proximal planning capabilities.

Run with: proximal mcp-serve
Or configure in Claude Desktop / VS Code as an MCP server.

This module provides four tools over the Model Context Protocol (MCP):
  - plan_goal: break a goal into tasks with scheduling and breaks
  - break_down_task: split a task into subtasks or pomodoro sessions
  - draft_message: draft a professional message about a project/task
  - get_motivation: get encouragement for current work
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# provider helper
# ---------------------------------------------------------------------------


def _get_chat_fn() -> Callable[..., Coroutine[Any, Any, str]]:
    """Return the LLM chat function from the providers layer.

    Returns
    -------
    Callable
        Async callable that accepts a list of message dicts and returns a string.
    """
    # deferred import so the module can be loaded even when the full
    # proximal stack is not configured (e.g. during tests with mocks)
    from packages.core.providers.router import (
        chat as chat_model,  # type: ignore[import-untyped]
    )

    return chat_model


# ---------------------------------------------------------------------------
# tool handlers (pure async functions, easy to test without mcp transport)
# ---------------------------------------------------------------------------


async def handle_plan_goal(
    goal: str,
    energy: str = "medium",
    interactive: bool = False,
) -> str:
    """Break a goal into tasks, a schedule, and break reminders.

    Parameters
    ----------
    goal : str
        The user's goal to plan.
    energy : str
        Current energy level (low, medium, high).
    interactive : bool
        Reserved for future interactive clarification support.

    Returns
    -------
    str
        JSON string with keys ``tasks``, ``schedule``, and ``breaks``.
    """
    try:
        chat = _get_chat_fn()

        prompt = (
            "You are an expert project planner built for neurodiverse minds.\n\n"
            f"The user's current energy level is: {energy}.\n"
            "Adapt your plan complexity accordingly:\n"
            "- low energy: fewer tasks, shorter sessions, more breaks\n"
            "- medium energy: balanced plan\n"
            "- high energy: ambitious plan, longer focus blocks\n\n"
            f"Break this goal into actionable tasks:\n{goal}\n\n"
            "Return a JSON list of task objects. Each task must have:\n"
            '  id (string), title (string), detail (string), priority ("P0"-"P3"), '
            "estimate_h (integer), done (boolean, always false).\n"
            "Return ONLY the JSON array, no extra text."
        )

        messages = [{"role": "user", "content": prompt}]
        raw = await chat(messages)
        tasks = json.loads(raw)

        # build a simple schedule from the tasks
        schedule = _build_schedule(tasks)

        # insert break reminders
        breaks = _build_breaks(tasks, energy)

        return json.dumps({"tasks": tasks, "schedule": schedule, "breaks": breaks})

    except json.JSONDecodeError as exc:
        logger.warning("plan_goal: LLM returned invalid JSON: %s", exc)
        return json.dumps({"error": f"Failed to parse plan from LLM: {exc}"})
    except Exception as exc:
        logger.error("plan_goal failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Planning failed: {exc}"})


async def handle_break_down_task(
    task: str,
    method: str = "subtasks",
    hours: float = 4.0,
) -> str:
    """Break a single task into subtasks or pomodoro sessions.

    Parameters
    ----------
    task : str
        Description of the task to break down.
    method : str
        Either ``"subtasks"`` or ``"pomodoros"``.
    hours : float
        Estimated hours available for the task.

    Returns
    -------
    str
        JSON string with key ``items`` (list) and ``method``.
    """
    try:
        chat = _get_chat_fn()

        if method == "pomodoros":
            prompt = (
                f"Break down this task into 25-minute Pomodoro sessions:\n"
                f"Task: {task}\n"
                f"Available time: {hours} hours\n\n"
                "Return a JSON list of sessions. Each session has:\n"
                "  session_number (int), focus (string), deliverable (string).\n"
                "Return ONLY the JSON array."
            )
        else:
            prompt = (
                f"Break down this task into smaller, actionable subtasks:\n"
                f"Task: {task}\n"
                f"Available time: {hours} hours\n\n"
                "Return a JSON list of subtasks. Each subtask has:\n"
                "  title (string), detail (string), estimate_h (number), order (int).\n"
                "Return ONLY the JSON array."
            )

        messages = [{"role": "user", "content": prompt}]
        raw = await chat(messages)
        items = json.loads(raw)

        return json.dumps({"items": items, "method": method})

    except json.JSONDecodeError as exc:
        logger.warning("break_down_task: LLM returned invalid JSON: %s", exc)
        return json.dumps({"error": f"Failed to parse breakdown from LLM: {exc}"})
    except Exception as exc:
        logger.error("break_down_task failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Task breakdown failed: {exc}"})


async def handle_draft_message(
    context: str,
    message_type: str = "status_update",
    tone: str = "professional",
) -> str:
    """Draft a professional message about a project or task.

    Parameters
    ----------
    context : str
        Context about the project/task for the message.
    message_type : str
        One of ``status_update``, ``proposal``, ``progress``,
        ``help_request``, ``delegation``.
    tone : str
        One of ``professional``, ``casual``, ``direct``.

    Returns
    -------
    str
        JSON string with keys ``subject`` and ``body``.
    """
    try:
        chat = _get_chat_fn()

        prompt = (
            f"Draft a {message_type} message with a {tone} tone.\n\n"
            f"Context: {context}\n\n"
            "Return a JSON object with exactly two fields:\n"
            '  "subject": a concise email subject line,\n'
            '  "message": the full message body.\n'
            "Return ONLY the JSON object."
        )

        messages = [{"role": "user", "content": prompt}]
        raw = await chat(messages)

        try:
            data = json.loads(raw)
            subject = data.get("subject", f"Update: {context[:50]}")
            body = data.get("message", raw)
        except json.JSONDecodeError:
            # graceful fallback: use raw text as body
            subject = f"Update: {context[:50]}"
            body = raw

        return json.dumps({"subject": subject, "body": body})

    except Exception as exc:
        logger.error("draft_message failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Message drafting failed: {exc}"})


async def handle_get_motivation(
    context: str,
    energy: str = "medium",
) -> str:
    """Get encouragement tailored to current work and energy level.

    Parameters
    ----------
    context : str
        What the user is currently working on.
    energy : str
        Current energy level (low, medium, high).

    Returns
    -------
    str
        JSON string with key ``message``.
    """
    try:
        chat = _get_chat_fn()

        prompt = (
            "You are a supportive, neurodiverse-friendly motivational coach.\n\n"
            f"The user's current energy level is: {energy}.\n"
            f"They are working on: {context}\n\n"
            "Provide a short, genuine encouragement message (2-4 sentences).\n"
            "Adapt to their energy level:\n"
            "- low: gentle, validate their effort, suggest small wins\n"
            "- medium: balanced encouragement, acknowledge progress\n"
            "- high: energetic, ambitious, channel their momentum\n\n"
            "Be authentic -- avoid toxic positivity. Return plain text only."
        )

        messages = [{"role": "user", "content": prompt}]
        raw = await chat(messages)

        return json.dumps({"message": raw.strip()})

    except Exception as exc:
        logger.error("get_motivation failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Motivation generation failed: {exc}"})


# ---------------------------------------------------------------------------
# schedule / break helpers
# ---------------------------------------------------------------------------


def _build_schedule(tasks: list[dict]) -> list[dict]:
    """Build a simple hourly schedule from task list.

    Parameters
    ----------
    tasks : list[dict]
        List of task dicts with at least ``title`` and ``estimate_h``.

    Returns
    -------
    list[dict]
        Schedule entries with ``task``, ``start``, and ``end`` times.
    """
    schedule: list[dict] = []
    current = datetime.combine(datetime.today(), datetime.min.time()).replace(
        hour=9, minute=0
    )

    for task in tasks:
        hours = task.get("estimate_h", 1)
        end = current + timedelta(hours=hours)
        schedule.append(
            {
                "task": task.get("title", "Untitled"),
                "start": current.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
            }
        )
        current = end

    return schedule


def _build_breaks(tasks: list[dict], energy: str) -> list[dict]:
    """Insert break reminders based on energy level.

    Parameters
    ----------
    tasks : list[dict]
        List of task dicts.
    energy : str
        Energy level: low, medium, or high.

    Returns
    -------
    list[dict]
        Break reminders with ``after_task`` index and ``duration_min``.
    """
    # more frequent breaks at lower energy
    interval = {"low": 2, "medium": 3, "high": 4}.get(energy, 3)
    duration = {"low": 15, "medium": 10, "high": 5}.get(energy, 10)

    breaks: list[dict] = []
    for i in range(len(tasks)):
        if (i + 1) % interval == 0:
            breaks.append(
                {
                    "after_task": i,
                    "duration_min": duration,
                    "message": "Take a short break -- you've earned it.",
                }
            )

    return breaks


# ---------------------------------------------------------------------------
# MCP server setup (only when mcp package is installed)
# ---------------------------------------------------------------------------


def _create_mcp_server() -> Any:
    """Create and configure the MCP server with all tool registrations.

    Returns
    -------
    Server
        Configured MCP server instance, or None if mcp is not installed.
    """
    try:
        from mcp.server import Server
    except ImportError:
        return None

    server = Server("proximal")

    @server.tool()
    async def plan_goal(
        goal: str,
        energy: str = "medium",
        interactive: bool = False,
    ) -> str:
        """Break a goal into actionable tasks with scheduling and breaks.

        Parameters
        ----------
        goal : str
            The goal or project to plan.
        energy : str
            Current energy level: low, medium, or high. Adjusts plan complexity.
        interactive : bool
            Reserved for future interactive clarification support.

        Returns
        -------
        str
            JSON with tasks, schedule, and break reminders.
        """
        return await handle_plan_goal(goal, energy=energy, interactive=interactive)

    @server.tool()
    async def break_down_task(
        task: str,
        method: str = "subtasks",
        hours: float = 4.0,
    ) -> str:
        """Break a single task into subtasks or pomodoro sessions.

        Parameters
        ----------
        task : str
            The task to break down.
        method : str
            Either "subtasks" for actionable sub-items or "pomodoros" for
            25-minute focus sessions.
        hours : float
            Hours available for the task.

        Returns
        -------
        str
            JSON with list of subtasks or pomodoro sessions.
        """
        return await handle_break_down_task(task, method=method, hours=hours)

    @server.tool()
    async def draft_message(
        context: str,
        message_type: str = "status_update",
        tone: str = "professional",
    ) -> str:
        """Draft a professional message about a project or task.

        Parameters
        ----------
        context : str
            Context about the project/task for the message.
        message_type : str
            Type: status_update, proposal, progress, help_request, or delegation.
        tone : str
            Tone: professional, casual, or direct.

        Returns
        -------
        str
            JSON with subject and body fields.
        """
        return await handle_draft_message(context, message_type=message_type, tone=tone)

    @server.tool()
    async def get_motivation(
        context: str,
        energy: str = "medium",
    ) -> str:
        """Get encouragement for your current work.

        Parameters
        ----------
        context : str
            What you are currently working on.
        energy : str
            Current energy level: low, medium, or high.

        Returns
        -------
        str
            JSON with a motivational message.
        """
        return await handle_get_motivation(context, energy=energy)

    @server.tool()
    async def check_wellness(
        user_id: str = "default",
        days: int = 30,
    ) -> str:
        """Check wellness patterns and burnout risk indicators.

        Parameters
        ----------
        user_id : str
            User to check wellness for.
        days : int
            Number of days of history to analyze.

        Returns
        -------
        str
            JSON with wellness insights and recommendations.
        """
        try:
            from packages.core.capabilities.wellness import get_wellness_summary

            summary = await get_wellness_summary(user_id, days)
            return json.dumps(
                summary or {"status": "no_data", "message": "No wellness data yet."}
            )
        except Exception as exc:
            logger.error("check_wellness failed: %s", exc, exc_info=True)
            return json.dumps({"error": f"Wellness check failed: {exc}"})

    @server.tool()
    async def check_schedule_conflicts(
        tasks_json: str = "[]",
    ) -> str:
        """Check a set of tasks for scheduling conflicts with calendar.

        Parameters
        ----------
        tasks_json : str
            JSON string of task list to check.

        Returns
        -------
        str
            JSON with any detected conflicts.
        """
        try:
            from packages.core.capabilities.productivity import (
                check_schedule_conflicts as _check,
            )

            tasks = json.loads(tasks_json)
            result = await _check(tasks)
            return json.dumps(result)
        except Exception as exc:
            logger.error("check_schedule_conflicts failed: %s", exc, exc_info=True)
            return json.dumps({"error": f"Schedule conflict check failed: {exc}"})

    @server.tool()
    async def plan_from_voice(
        audio_path: str,
        energy: str = "medium",
    ) -> str:
        """Transcribe an audio file and create a plan from it.

        Parameters
        ----------
        audio_path : str
            Path to the audio file to transcribe.
        energy : str
            Current energy level: low, medium, or high.

        Returns
        -------
        str
            JSON with transcription and plan.
        """
        try:
            from packages.core.capabilities.voice import (
                extract_goals_from_transcript,
                transcribe_audio,
            )

            transcript = transcribe_audio(audio_path)
            goals = extract_goals_from_transcript(transcript)
            goal_text = "; ".join(goals) if goals else transcript

            plan_result = await handle_plan_goal(goal_text, energy=energy)
            result = {
                "transcript": transcript,
                "extracted_goals": goals,
                "plan": json.loads(plan_result),
            }
            return json.dumps(result)
        except ImportError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("plan_from_voice failed: %s", exc, exc_info=True)
            return json.dumps({"error": f"Voice planning failed: {exc}"})

    return server


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the MCP server over stdio transport."""
    from mcp.server.stdio import stdio_server

    server = _create_mcp_server()
    if server is None:
        raise ImportError(
            "MCP package not installed. Install with: pip install proximal[mcp]"
        )

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
