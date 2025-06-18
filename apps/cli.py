#!/usr/bin/env python3

import typer
import httpx
import json
import sys
from typing import Optional
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Trellis CLI - Transform ideas into actionable project plans")
console = Console()

# default API URL, can be overridden with environment variables
API_URL = "http://localhost:7315/plan"


@app.command()
def plan(
    goal: str = typer.Argument(..., help="Your project goal or idea"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (JSON format)"
    ),
    pretty: bool = typer.Option(True, help="Pretty print the output"),
):
    """
    Transform a goal or idea into a structured project plan with tasks and sprints.
    """
    console.print(f"[bold green]Planning:[/bold green] {goal}")

    try:
        with console.status("Generating plan..."):
            response = httpx.post(API_URL, json={"message": goal}, timeout=60.0)
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


@app.command()
def version():
    """Show the version of Trellis CLI."""
    console.print("[bold green]Trellis CLI[/bold green] v0.1.0")


if __name__ == "__main__":
    app()
