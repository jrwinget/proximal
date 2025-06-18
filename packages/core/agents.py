from __future__ import annotations
from typing import List, TypedDict, Annotated
import json
from datetime import date
from pydantic import BaseModel

from .models import Task, Sprint, Priority
from .memory import client as mem
from .providers.router import chat as chat_model


class DateEncoder(json.JSONEncoder):
    """Custom JSON encoder for date objects."""
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def _json(obj) -> str:
    """Convert a Pydantic model or list of models to JSON string."""
    if isinstance(obj, list) and all(isinstance(item, BaseModel) for item in obj):
        return json.dumps([item.model_dump() for item in obj], cls=DateEncoder)
    elif isinstance(obj, BaseModel):
        return json.dumps(obj.model_dump(), cls=DateEncoder)
    return json.dumps(obj, cls=DateEncoder)


async def plan_llm(state: dict) -> dict:
    """Transform goal into tasks."""
    goal = state["goal"]
    prompt = (
        "You are Trellis-Planner.\n\n"
        f"Transform the user goal into detailed Tasks.\nGoal: {goal}\n\n"
        "Return JSON list[Task] with fields (id, title, detail, priority, estimate_h)."
    )
    content = await chat_model([{"role": "user", "content": prompt}])
    tasks_data = json.loads(content)
    tasks = [Task.model_validate(task) for task in tasks_data]
    # persist initial plan in vector store
    mem.batch.add_data_objects([{"role": "planner", "content": _json(tasks)}], "Memory")
    return {"tasks": tasks}


async def prioritize_llm(state: dict) -> dict:
    """Assign priority levels to tasks."""
    tasks = state["tasks"]
    prompt = (
        "Assign priority levels P0-P3.\n\nTasks JSON:\n"
        + _json(tasks)
        + "\nReturn updated list."
    )
    content = await chat_model([{"role": "user", "content": prompt}])
    tasks_data = json.loads(content)
    updated_tasks = [Task.model_validate(task) for task in tasks_data]
    return {"tasks": updated_tasks}


async def estimate_llm(state: dict) -> dict:
    """Add time estimates to tasks."""
    tasks = state["tasks"]
    prompt = (
        "Insert realistic integer `estimate_h` for each task "
        "(developer hours, 1-100).\n\nTasks:\n" + _json(tasks)
    )
    content = await chat_model([{"role": "user", "content": prompt}])
    tasks_data = json.loads(content)
    updated_tasks = [Task.model_validate(task) for task in tasks_data]
    return {"tasks": updated_tasks}


async def package_llm(state: dict) -> dict:
    """Group tasks into sprints."""
    tasks = state["tasks"]
    prompt = (
        "Group tasks into 2-week sprints ordered chronologically.\n"
        "Each sprint needs name, start, end, tasks.\n\nTasks:\n" + _json(tasks)
    )
    content = await chat_model([{"role": "user", "content": prompt}])
    sprints_data = json.loads(content)
    sprints = [Sprint.model_validate(sprint) for sprint in sprints_data]
    # persist final sprint plan
    mem.batch.add_data_objects(
        [{"role": "packager", "content": _json(sprints)}], "Memory"
    )
    return {"sprints": sprints}