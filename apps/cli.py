#!/usr/bin/env python3

import typer
import httpx
import json
import sys
from typing import Optional, List, Dict
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.markdown import Markdown

app = typer.Typer(help="Trellis CLI - Transform ideas into actionable project plans")
console = Console()

# default API URL, can be overridden with environment variables
API_URL = "http://localhost:7315"


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
):
    """
    Transform a goal or idea into a structured project plan with tasks and sprints.

    Use --interactive for a conversational planning experience where Trellis
    asks clarifying questions to create a more detailed and personalized plan.
    """
    console.print(
        f"[bold green]{'Interactive ' if interactive else ''}Planning:[/bold green] {goal}"
    )

    try:
        if interactive:
            plan_data = _interactive_planning(goal)
        else:
            # One-shot planning
            with console.status("Generating plan..."):
                response = httpx.post(
                    f"{API_URL}/plan", json={"message": goal}, timeout=60.0
                )
                response.raise_for_status()
                plan_data = response.json()

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
            f"[bold red]Error:[/bold red] Could not connect to API server. Is it running?"
        )
        console.print(f"Details: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Planning cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _interactive_planning(goal: str) -> List[Dict]:
    """Handle interactive planning with clarification questions"""
    # start conversation
    with console.status("Starting interactive planning session..."):
        response = httpx.post(
            f"{API_URL}/conversation/start", json={"message": goal}, timeout=60.0
        )
        response.raise_for_status()
        result = response.json()

    session_id = result["session_id"]

    # handle clarification loop
    while result["type"] == "questions":
        questions = result.get("questions", [])
        if not questions:
            break

        console.print("\n[bold blue]Trellis needs some clarification:[/bold blue]")

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
            answer = Prompt.ask("[green]Your answer[/green]")
            answers[question] = answer

        # send answers back
        console.print()
        with console.status("Processing your answers..."):
            response = httpx.post(
                f"{API_URL}/conversation/continue",
                json={"session_id": session_id, "answers": answers},
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

    These preferences help Trellis create personalized plans that match your work style.
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

            response = httpx.put(f"{API_URL}/preferences", json=updates, timeout=30.0)
            response.raise_for_status()
            console.print("[bold green]Preferences updated successfully![/bold green]")

        if show:
            # get current preferences
            response = httpx.get(f"{API_URL}/preferences", timeout=30.0)
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

            status = "✓" if task.get("done", False) else "○"
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
    total_tasks = sum(len(sprint["tasks"]) for sprint in plan_data)
    total_hours = sum(
        task["estimate_h"] for sprint in plan_data for task in sprint["tasks"]
    )
    console.print(f"\n[dim]Total: {total_tasks} tasks, {total_hours} hours[/dim]")


@app.command()
def version():
    """Show the version of Trellis CLI."""
    console.print("[bold green]Trellis CLI[/bold green] v0.2.0")
    console.print("Now with interactive planning and task breakdown! 🌱")


@app.command()
def assist(goal: str = typer.Argument(..., help="Goal to achieve")):
    """Plan and schedule tasks for a goal using Proximal."""
    from packages.proximal.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run(goal)
    console.print(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
