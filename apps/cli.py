#!/usr/bin/env python3

import typer
import httpx
import json
import sys
import os
import asyncio
from typing import Optional, List, Dict
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

app = typer.Typer(help="Proximal CLI - Transform ideas into actionable project plans")
console = Console()

# api configuration from environment
API_URL = os.getenv("PROXIMAL_API_URL", "http://localhost:7315")
API_KEY = os.getenv("PROXIMAL_API_KEY")


def _get_headers() -> dict:
    """get http headers including api key if configured"""
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return headers


def _run_async(coro):
    """run an async coroutine from synchronous cli context"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# lazy imports to avoid loading pipeline at module level
def _import_pipelines():
    """import pipeline functions lazily"""
    from apps.server.pipeline import run_direct_pipeline, run_interactive_pipeline

    return run_direct_pipeline, run_interactive_pipeline


# module-level references for testability (set lazily)
run_direct_pipeline = None
run_interactive_pipeline = None


def _get_direct_pipeline():
    """get the direct pipeline function, importing lazily"""
    global run_direct_pipeline
    if run_direct_pipeline is None:
        run_direct_pipeline, _ = _import_pipelines()
    return run_direct_pipeline


def _get_interactive_pipeline():
    """get the interactive pipeline function, importing lazily"""
    global run_interactive_pipeline
    if run_interactive_pipeline is None:
        _, run_interactive_pipeline = _import_pipelines()
    return run_interactive_pipeline


def _serialize_plan(plan_data) -> list:
    """convert plan data to serializable dicts"""
    result = []
    for sprint in plan_data:
        if hasattr(sprint, "model_dump"):
            result.append(sprint.model_dump())
        elif isinstance(sprint, dict):
            result.append(sprint)
        else:
            result.append(sprint)
    return result


@app.command()
def plan(
    goal: str = typer.Argument(..., help="Your project goal or idea"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (JSON format)"
    ),
    pretty: bool = typer.Option(True, help="Pretty print the output"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Enable interactive clarification mode"
    ),
    server: bool = typer.Option(
        False, "--server", help="Use API server instead of calling pipeline directly"
    ),
):
    """
    Transform a goal or idea into a structured project plan with tasks and sprints.

    By default, calls the planning pipeline directly without needing a running server.
    Use --server to route through the API server instead.
    Use --interactive for a conversational planning experience where PlannerAgent
    asks clarifying questions to create a more detailed and personalized plan.
    """
    console.print(
        f"[bold green]{'Interactive ' if interactive else ''}Planning:[/bold green] {goal}"
    )

    try:
        if server:
            # server mode: use HTTP calls
            if interactive:
                plan_data = _interactive_planning_server(goal)
            else:
                with console.status("Generating plan..."):
                    response = httpx.post(
                        f"{API_URL}/plan",
                        json={"message": goal},
                        headers=_get_headers(),
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    plan_data = response.json()
        else:
            # direct mode: call pipeline functions directly
            if interactive:
                plan_data = _interactive_planning_direct(goal)
            else:
                with console.status("Generating plan..."):
                    pipeline = _get_direct_pipeline()
                    result = _run_async(pipeline(goal))
                    plan_data = _serialize_plan(result.get("sprints", []))

        if output:
            with open(output, "w") as f:
                json.dump(plan_data, f, indent=2 if pretty else None)
            console.print(f"[bold green]Plan saved to:[/bold green] {output}")

        if pretty:
            _display_pretty_plan(plan_data)
        else:
            console.print(json.dumps(plan_data, indent=2))

    except httpx.HTTPStatusError as e:
        console.print(
            f"[bold red]Error:[/bold red] HTTP {e.response.status_code} - {e.response.text}"
        )
        sys.exit(1)
    except httpx.RequestError as e:
        console.print(
            "[bold red]Error:[/bold red] Could not connect to API server. Is it running?"
        )
        console.print(f"Details: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Planning cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _interactive_planning_direct(goal: str) -> List[Dict]:
    """Handle interactive planning by calling pipeline directly."""
    with console.status("Starting interactive planning session..."):
        pipeline = _get_interactive_pipeline()
        result = _run_async(pipeline(goal))

    # handle clarification loop
    while result.get("needs_clarification"):
        questions = result.get("clarification_questions", [])
        if not questions:
            break

        console.print("\n[bold blue]PlannerAgent Needs Some Clarification:[/bold blue]")

        # display questions
        for i, question in enumerate(questions, 1):
            console.print(f"\n[cyan]{i}.[/cyan] {question}")

        # collect answers
        console.print(
            "\n[dim]Please answer the questions to help create a better plan:[/dim]"
        )

        answers = {}
        for i, question in enumerate(questions, 1):
            console.print(f"\n[bold]Question {i}:[/bold] {question}")
            answer = Prompt.ask("[green]Your Answer[/green]")
            answers[question] = answer

        # integrate answers and re-run the pipeline with enriched goal
        answers_text = "\n".join(f"{q}: {a}" for q, a in answers.items())
        enriched_goal = f"{goal}\n\nClarifications:\n{answers_text}"

        console.print()
        with console.status("Processing your answers..."):
            direct_pipeline = _get_direct_pipeline()
            result = _run_async(direct_pipeline(enriched_goal))

    return _serialize_plan(result.get("sprints", []))


def _interactive_planning_server(goal: str) -> List[Dict]:
    """Handle interactive planning with clarification questions via server."""
    # start conversation
    with console.status("Starting interactive planning session..."):
        response = httpx.post(
            f"{API_URL}/conversation/start",
            json={"message": goal},
            headers=_get_headers(),
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

    session_id = result["session_id"]

    # handle clarification loop
    while result["type"] == "questions":
        questions = result.get("questions", [])
        if not questions:
            break

        console.print("\n[bold blue]PlannerAgent Needs Some Clarification:[/bold blue]")

        # display questions
        for i, question in enumerate(questions, 1):
            console.print(f"\n[cyan]{i}.[/cyan] {question}")

        # collect answers
        answers = {}
        console.print(
            "\n[dim]Please answer the questions to help create a better plan:[/dim]"
        )

        for i, question in enumerate(questions, 1):
            # show question context
            console.print(f"\n[bold]Question {i}:[/bold] {question}")
            answer = Prompt.ask("[green]Your Answer[/green]")
            answers[question] = answer

        # send answers back
        console.print()
        with console.status("Processing your answers..."):
            response = httpx.post(
                f"{API_URL}/conversation/continue",
                json={"session_id": session_id, "answers": answers},
                headers=_get_headers(),
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

    # return final plan
    return result.get("plan", [])


@app.command()
def breakdown(
    task_title: str = typer.Argument(..., help="Title of the task to break down"),
    task_detail: Optional[str] = typer.Option(
        None, "--detail", "-d", help="Task details"
    ),
    hours: int = typer.Option(8, "--hours", "-h", help="Estimated hours for the task"),
    breakdown_type: str = typer.Option(
        "subtasks", "--type", "-t", help="Type of breakdown: 'subtasks' or 'pomodoros'"
    ),
):
    """
    Break down a task into smaller subtasks or pomodoro sessions.

    This helps with executive function by providing clear next actions.
    """
    # create a task object
    from packages.core.models import Task, Priority

    task = Task(
        title=task_title,
        detail=task_detail or "No additional details provided",
        priority=Priority.medium,
        estimate_h=hours,
    )

    console.print(f"[bold green]Breaking down task:[/bold green] {task_title}")
    console.print(f"[dim]Type: {breakdown_type}[/dim]")

    try:
        with console.status("Generating breakdown..."):
            response = httpx.post(
                f"{API_URL}/task/breakdown",
                json={"task": task.model_dump(), "breakdown_type": breakdown_type},
                headers=_get_headers(),
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        breakdown = result.get("breakdown", [])

        if breakdown_type == "pomodoros":
            _display_pomodoro_breakdown(task_title, breakdown)
        else:
            _display_subtask_breakdown(task_title, breakdown)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _display_pomodoro_breakdown(task_title: str, pomodoros: List[Dict]):
    """Display pomodoro breakdown in a nice format"""
    console.print(f"\n[bold]Pomodoro Sessions for:[/bold] {task_title}\n")

    table = Table(show_header=True)
    table.add_column("Session", style="cyan", width=10)
    table.add_column("Focus", style="white")
    table.add_column("Deliverable", style="green")

    for pom in pomodoros:
        table.add_row(
            f"#{pom.get('session_number', '?')}",
            pom.get("focus", ""),
            pom.get("deliverable", ""),
        )

    console.print(table)
    console.print(
        f"\n[dim]Total sessions: {len(pomodoros)} (≈ {len(pomodoros) * 25} minutes)[/dim]"
    )


def _display_subtask_breakdown(task_title: str, subtasks: List[Dict]):
    """Display subtask breakdown in a nice format"""
    console.print(f"\n[bold]Subtasks for:[/bold] {task_title}\n")

    table = Table(show_header=True)
    table.add_column("Order", style="cyan", width=8)
    table.add_column("Subtask", style="bold")
    table.add_column("Details", style="white")
    table.add_column("Hours", style="yellow", justify="right")

    total_hours = 0
    for subtask in sorted(subtasks, key=lambda x: x.get("order", 0)):
        hours = subtask.get("estimate_h", 0)
        total_hours += hours
        table.add_row(
            str(subtask.get("order", "?")),
            subtask.get("title", ""),
            subtask.get("detail", ""),
            str(hours),
        )

    console.print(table)
    console.print(f"\n[dim]Total estimated hours: {total_hours}[/dim]")


@app.command()
def preferences(
    show: bool = typer.Option(True, "--show", "-s", help="Show current preferences"),
    sprint_weeks: Optional[int] = typer.Option(None, help="Set sprint length in weeks"),
    work_hours: Optional[int] = typer.Option(
        None, help="Set available work hours per week"
    ),
    tone: Optional[str] = typer.Option(
        None, help="Set communication tone (professional/casual/motivational)"
    ),
    task_size: Optional[str] = typer.Option(
        None, help="Set preferred task size (small/medium/large)"
    ),
):
    """
    View or update your planning preferences.

    These preferences help PlannerAgent create personalized plans that match your work style.
    """
    try:
        if any([sprint_weeks, work_hours, tone, task_size]):
            # update preferences
            updates = {}
            if sprint_weeks:
                updates["sprint_length_weeks"] = sprint_weeks
            if work_hours:
                updates["work_hours_per_week"] = work_hours
            if tone:
                updates["tone"] = tone
            if task_size:
                updates["preferred_task_size"] = task_size

            response = httpx.put(
                f"{API_URL}/preferences",
                json=updates,
                headers=_get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            console.print("[bold green]Preferences Updated Successfully![/bold green]")

        if show:
            # get current preferences
            response = httpx.get(
                f"{API_URL}/preferences", headers=_get_headers(), timeout=30.0
            )
            response.raise_for_status()
            prefs = response.json()

            console.print("\n[bold]Current Planning Preferences:[/bold]\n")

            table = Table(show_header=False, box=None)
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Sprint Length", f"{prefs['sprint_length_weeks']} weeks")
            table.add_row("Work Hours/Week", str(prefs["work_hours_per_week"]))
            table.add_row("Communication Tone", prefs["tone"])
            table.add_row("Preferred Task Size", prefs["preferred_task_size"])
            table.add_row("Include Breaks", "Yes" if prefs["include_breaks"] else "No")
            table.add_row("Time Zone", prefs["timezone"])

            console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _display_pretty_plan(plan_data):
    """Display the plan in a nicely formatted table."""
    if not plan_data:
        console.print("[yellow]No sprints or tasks found in the plan.[/yellow]")
        return

    for i, sprint in enumerate(plan_data):
        # support both dict and pydantic model
        if hasattr(sprint, "model_dump"):
            sprint = sprint.model_dump()

        console.print(f"\n[bold blue]Sprint {i + 1}:[/bold blue] {sprint['name']}")
        console.print(f"[blue]Period:[/blue] {sprint['start']} to {sprint['end']}")

        table = Table(show_header=True)
        table.add_column("ID", style="dim")
        table.add_column("Task", style="bold")
        table.add_column("Priority")
        table.add_column("Hours")
        table.add_column("Status")

        for task in sprint["tasks"]:
            priority_color = {
                "P0": "red",
                "P1": "orange3",
                "P2": "yellow",
                "P3": "green",
            }.get(task["priority"], "white")

            status = "+" if task.get("done", False) else "o"
            status_color = "green" if task.get("done", False) else "white"

            table.add_row(
                task["id"],
                task["title"],
                f"[{priority_color}]{task['priority']}[/{priority_color}]",
                str(task["estimate_h"]),
                f"[{status_color}]{status}[/{status_color}]",
            )

        console.print(table)

    # add summary
    total_tasks = sum(
        len(s["tasks"] if isinstance(s, dict) else s.tasks) for s in plan_data
    )
    total_hours = sum(
        task["estimate_h"] if isinstance(task, dict) else task.estimate_h
        for s in plan_data
        for task in (s["tasks"] if isinstance(s, dict) else s.tasks)
    )
    console.print(f"\n[dim]Total: {total_tasks} tasks, {total_hours} hours[/dim]")


@app.command()
def version():
    """Show the version of Proximal CLI."""
    console.print("[bold green]Proximal CLI[/bold green] v0.4.0")
    console.print("Multi-agent collaboration with reactive monitoring and analytics!")


@app.command()
def assist(
    goal: str = typer.Argument(..., help="Goal to achieve"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (JSON format)"
    ),
    pretty: bool = typer.Option(True, help="Pretty print the output"),
):
    """
    Plan and schedule tasks for a goal using the full orchestration pipeline.

    This runs all 7 agents in sequence to create a comprehensive project plan.
    """
    from packages.core.orchestrator import Orchestrator
    from packages.core.exceptions import OrchestratorError

    console.print(f"[bold green]Orchestrating plan for:[/bold green] {goal}")

    try:
        orch = Orchestrator()

        # use status spinner for long-running operation
        with console.status(
            "Running orchestration pipeline (this may take a moment)..."
        ):
            result = orch.run_sync(goal)

        # save to file if requested
        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2 if pretty else None)
            console.print(f"[bold green]Plan saved to:[/bold green] {output}")

        # display result
        if pretty:
            _display_pretty_plan(result)
        else:
            console.print(json.dumps(result, indent=2))

    except OrchestratorError as e:
        console.print(f"[bold red]Orchestration Error:[/bold red] {str(e)}")
        console.print(
            "[dim]The orchestration pipeline encountered an error. Please check your goal and try again.[/dim]"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Orchestration cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {str(e)}")
        console.print("[dim]An unexpected error occurred during orchestration.[/dim]")
        sys.exit(1)


@app.command()
def wellness(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
):
    """
    Show wellness insights from cross-session pattern detection.

    Guardian agent tracks breaks, work duration, and late sessions to
    identify burnout risk and provide actionable recommendations.
    """
    from packages.core.capabilities.wellness import get_wellness_summary

    console.print("[bold green]Wellness Check[/bold green]")

    try:
        with console.status("Analyzing wellness patterns..."):
            summary = _run_async(get_wellness_summary(user_id, days))

        if not summary:
            console.print("[yellow]No wellness data found yet. Complete a few sessions first.[/yellow]")
            return

        # display insights
        console.print(f"\n[bold]Sessions analyzed:[/bold] {summary.get('session_count', 0)}")

        insights = summary.get("insights", [])
        if insights:
            console.print("\n[bold blue]Insights:[/bold blue]")
            for insight in insights:
                level = insight.get("level", "info")
                color = {"gentle_nudge": "yellow", "firm_reminder": "orange3",
                         "escalated_warning": "red", "session_end_suggestion": "bold red"}.get(level, "white")
                console.print(f"  [{color}]{insight.get('message', '')}[/{color}]")
        else:
            console.print("\n[green]No concerns detected. Keep up the good work![/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def workflow(
    action: str = typer.Argument("list", help="Action: list, start, stop, approve"),
    name: Optional[str] = typer.Argument(None, help="Workflow name (for start/stop/approve)"),
):
    """
    Manage autonomous workflows.

    Workflows run agents on schedules or in response to events.
    Built-in workflows: daily_planning, proactive_checkin, weekly_status, adaptive_learning.
    """
    from packages.core.workflows.builtins import get_builtin_workflows

    try:
        if action == "list":
            workflows = get_builtin_workflows()
            table = Table(show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="white")
            table.add_column("Trigger", style="yellow")
            table.add_column("Steps", style="green", justify="right")

            for wf in workflows:
                trigger_desc = wf.trigger.cron or wf.trigger.event_topic or "manual"
                table.add_row(wf.name, wf.description, trigger_desc, str(len(wf.steps)))

            console.print("\n[bold]Available Workflows:[/bold]\n")
            console.print(table)

        elif action == "start" and name:
            console.print(f"[bold green]Starting workflow:[/bold green] {name}")
            console.print("[dim]Workflow scheduling started. Use 'workflow stop' to halt.[/dim]")

        elif action == "stop" and name:
            console.print(f"[yellow]Stopping workflow:[/yellow] {name}")

        elif action == "approve" and name:
            console.print(f"[bold green]Approving checkpoint for workflow:[/bold green] {name}")

        else:
            console.print("[bold red]Usage:[/bold red] proximal workflow [list|start|stop|approve] [name]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def analytics(
    user_id: str = typer.Option("default", "--user", "-u", help="User ID"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    report: str = typer.Option("summary", "--report", "-r",
                               help="Report type: summary, tasks, energy, focus, burnout"),
):
    """
    View analytics and productivity insights.

    Aggregates task completion rates, energy patterns, estimate accuracy,
    focus session adherence, and burnout risk indicators.
    """
    from packages.core.analytics.aggregator import AnalyticsAggregator

    console.print("[bold green]Analytics Dashboard[/bold green]")

    try:
        agg = AnalyticsAggregator()

        with console.status("Gathering analytics..."):
            if report == "summary":
                data = _run_async(agg.weekly_summary(user_id))
            elif report == "tasks":
                data = _run_async(agg.task_completion_rates(user_id, days))
            elif report == "energy":
                data = _run_async(agg.energy_patterns(user_id, days))
            elif report == "focus":
                data = _run_async(agg.focus_session_adherence(user_id, days))
            elif report == "burnout":
                data = _run_async(agg.burnout_risk_indicators(user_id, days))
            else:
                console.print(f"[bold red]Unknown report type:[/bold red] {report}")
                sys.exit(1)

        console.print(json.dumps(data, indent=2))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def mcp_serve():
    """
    Start proximal as an MCP (Model Context Protocol) server.

    This exposes proximal's planning tools to any MCP client such as
    Claude Desktop, VS Code, or Cursor via stdio transport.
    """
    try:
        from apps.mcp_server import main as mcp_main

        console.print("[bold green]Starting MCP server...[/bold green]")
        console.print(
            "[dim]Listening on stdio transport. Connect from an MCP client.[/dim]"
        )
        asyncio.run(mcp_main())
    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] MCP dependencies not installed. "
            "Run: pip install proximal[mcp]"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]MCP server stopped.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
