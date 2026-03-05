from __future__ import annotations
from typing import List, Dict
import json
from datetime import date
from pydantic import BaseModel

from ..models import Task, Sprint
from .. import memory
from ..providers.router import chat as chat_model
from ..session import session_manager
from .registry import register_agent
from .base import BaseAgent


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


@register_agent("planner")
class PlannerAgent(BaseAgent):
    """Orchestrator that clarifies, plans, prioritizes, estimates, and packages tasks into sprints."""

    name = "planner"

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return "PlannerAgent()"

    async def run(self, context) -> any:
        """Run the planner pipeline within a shared context."""
        goal = context.goal

        # read decision-fatigue settings from user profile
        profile = getattr(context, "user_profile", None)
        decision_fatigue = getattr(profile, "decision_fatigue", "moderate")
        overwhelm_threshold = getattr(profile, "overwhelm_threshold", 5)

        result = await self.plan_llm({
            "goal": goal,
            "decision_fatigue": decision_fatigue,
        })
        tasks = result.get("tasks", [])

        # cap tasks when decision fatigue is high to reduce choice paralysis
        if decision_fatigue == "high":
            # sort by priority (P0 first) before trimming
            priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            tasks = sorted(
                tasks,
                key=lambda t: priority_order.get(str(t.priority), 4),
            )
            tasks = tasks[:overwhelm_threshold]

        context.tasks = [t.model_dump() for t in tasks]

        # mark the first task as the recommended starting point
        if decision_fatigue == "high" and context.tasks:
            context.tasks[0]["recommended_next"] = True

        return context.tasks

    def can_contribute(self, context) -> bool:
        return True

    async def clarify_llm(self, state: dict) -> dict:
        """Check if clarification is needed and generate questions"""
        goal = state["goal"]
        session_id = state.get("session_id")

        # get conversation context if in a session
        context_messages = []
        if session_id:
            session = session_manager.get_session(session_id)
            if session:
                context_messages = session.get_context()

        # get user preferences for context
        preferences = session_manager.get_user_preferences()
        pref_context = preferences.to_prompt_context()

        # get relevant past projects for context
        relevant_history = session_manager.get_relevant_history(goal, limit=2)
        history_context = ""
        if relevant_history:
            history_context = "\nRelevant past projects:\n"
            for hist in relevant_history:
                history_context += f"- Goal: {hist['goal']}\n"

        prompt = (
            "You are Planner-Clarifier, an AI assistant that helps clarify project requirements.\n\n"
            f"{pref_context}\n"
            f"{history_context}\n"
            f"User's goal: {goal}\n\n"
            "Analyze if this goal has enough information for detailed project planning. "
            "Consider: target audience, platform/technology, timeline, key features, constraints.\n\n"
            "If clarification would significantly improve the plan quality, generate 1-3 targeted questions. "
            "If the goal is already clear enough, return an empty list.\n\n"
            'Return JSON: {"needs_clarification": bool, "questions": [list of question strings]}'
        )

        messages = [{"role": "system", "content": prompt}]
        messages.extend(context_messages)
        messages.append({"role": "user", "content": f"Analyze this goal: {goal}"})

        content = await chat_model(messages)

        try:
            result = json.loads(content)
            needs_clarification = result.get("needs_clarification", False)
            questions = result.get("questions", [])

            # limit questions based on session state
            if session_id:
                session = session_manager.get_session(session_id)
                if (
                    session
                    and session.clarification_count >= session.max_clarifications
                ):
                    needs_clarification = False
                    questions = []

            return {
                "needs_clarification": needs_clarification,
                "clarification_questions": questions,
            }
        except json.JSONDecodeError:
            # if parsing fails, proceed without clarification
            return {"needs_clarification": False, "clarification_questions": []}

    async def integrate_clarifications_llm(self, state: dict) -> dict:
        """Integrate clarification answers into the goal"""
        goal = state["goal"]
        session_id = state.get("session_id")

        if not session_id:
            return state

        session = session_manager.get_session(session_id)
        if not session or len(session.messages) < 2:
            return state

        # build context from q&a exchanges
        qa_context = "Original goal: " + goal + "\n\nClarifications:\n"
        for i in range(1, len(session.messages), 2):  # skip first message (init goal)
            if i < len(session.messages) - 1:
                question = session.messages[i].content
                answer = session.messages[i + 1].content
                qa_context += f"Q: {question}\nA: {answer}\n"

        prompt = (
            "You are Planner-Integrator. Synthesize the original goal with clarification answers "
            "into an enriched, detailed project description.\n\n"
            f"{qa_context}\n"
            "Create a comprehensive goal statement that incorporates all the clarified details."
        )

        content = await chat_model([{"role": "user", "content": prompt}])

        return {"goal": content, "original_goal": goal}

    async def plan_llm(self, state: dict) -> dict:
        """Transform goal into tasks with memory context."""
        goal = state.get("goal", state.get("original_goal", ""))
        decision_fatigue = state.get("decision_fatigue", "moderate")

        # get user preferences
        preferences = session_manager.get_user_preferences()
        pref_context = preferences.to_prompt_context()

        # get relevant past projects
        relevant_history = session_manager.get_relevant_history(goal, limit=3)
        history_context = ""
        if relevant_history:
            history_context = "\nLearn from these similar past projects:\n"
            for hist in relevant_history:
                if hist.get("plan"):
                    history_context += (
                        f"Past project '{hist['goal']}' included tasks like: "
                    )
                    sample_tasks = []
                    for sprint in hist["plan"][:1]:
                        for task in sprint.get("tasks", [])[:3]:
                            sample_tasks.append(task.get("title", ""))
                    history_context += ", ".join(sample_tasks) + "\n"

        # build decision fatigue context for the prompt
        fatigue_context = ""
        if decision_fatigue == "high":
            fatigue_context = (
                "The user has high decision fatigue. Generate fewer, "
                "more focused tasks. Pre-select priorities and include "
                "a clear recommended starting point.\n"
            )
        elif decision_fatigue == "moderate":
            fatigue_context = (
                "The user has moderate decision fatigue. "
                "Keep options manageable.\n"
            )

        prompt = (
            "You are Core-Planner, an expert project planning AI.\n\n"
            f"{pref_context}\n"
            f"{fatigue_context}"
            f"{history_context}\n"
            f"Transform this goal into detailed tasks:\n{goal}\n\n"
            "Consider the user's preferences and past similar projects. "
            "Return JSON list[Task] with fields (id, title, detail, priority, estimate_h)."
        )

        content = await chat_model([{"role": "user", "content": prompt}])
        tasks_data = json.loads(content)
        tasks = [Task.model_validate(task) for task in tasks_data]

        # persist initial plan in memory store
        await memory.store("planner", _json(tasks))

        return {"tasks": tasks}

    async def prioritize_llm(self, state: dict) -> dict:
        """Assign priority levels to tasks based on user preferences."""
        tasks = state["tasks"]
        preferences = session_manager.get_user_preferences()

        priority_instruction = "Assign priority levels P0-P3 (P0=critical, P3=low)."
        if preferences.priority_system != "P0-P3":
            priority_instruction = (
                f"User prefers '{preferences.priority_system}' priority system. "
                "Map to P0-P3 internally but consider their preference."
            )

        prompt = (
            f"{priority_instruction}\n\n"
            "Tasks JSON:\n"
            + _json(tasks)
            + "\nReturn updated list with appropriate priorities."
        )

        content = await chat_model([{"role": "user", "content": prompt}])
        tasks_data = json.loads(content)
        updated_tasks = [Task.model_validate(task) for task in tasks_data]
        return {"tasks": updated_tasks}

    async def estimate_llm(self, state: dict) -> dict:
        """Add time estimates considering user's available hours."""
        tasks = state["tasks"]
        preferences = session_manager.get_user_preferences()

        prompt = (
            f"User has {preferences.work_hours_per_week} hours/week available. "
            f"They prefer {preferences.preferred_task_size} task sizes.\n\n"
            "Insert realistic integer `estimate_h` for each task (1-100 hours).\n\n"
            "Tasks:\n" + _json(tasks)
        )

        content = await chat_model([{"role": "user", "content": prompt}])
        tasks_data = json.loads(content)
        updated_tasks = [Task.model_validate(task) for task in tasks_data]
        return {"tasks": updated_tasks}

    async def package_llm(self, state: dict) -> dict:
        """Group tasks into sprints based on user preferences."""
        tasks = state["tasks"]
        preferences = session_manager.get_user_preferences()

        prompt = (
            f"Group tasks into {preferences.sprint_length_weeks}-week sprints. "
            f"User has {preferences.work_hours_per_week} hours/week available.\n"
        )

        if preferences.include_breaks:
            prompt += "Include buffer time for breaks and unexpected issues.\n"

        prompt += "Each sprint needs name, start, end, tasks.\n\nTasks:\n" + _json(
            tasks
        )

        content = await chat_model([{"role": "user", "content": prompt}])
        sprints_data = json.loads(content)
        sprints = [Sprint.model_validate(sprint) for sprint in sprints_data]

        # persist final sprint plan
        await memory.store("packager", _json(sprints))

        # if in a session, complete it
        session_id = state.get("session_id")
        if session_id:
            session_manager.complete_session(
                session_id, [sprint.model_dump() for sprint in sprints]
            )

        return {"sprints": sprints}

    async def breakdown_task_llm(
        self, task: Task, breakdown_type: str = "subtasks"
    ) -> List[Dict]:
        """Break down a task into smaller pieces"""
        preferences = session_manager.get_user_preferences()

        if breakdown_type == "pomodoros":
            prompt = (
                f"Break down this task into 25-minute Pomodoro sessions:\n"
                f"Task: {task.title}\n"
                f"Details: {task.detail}\n"
                f"Estimated hours: {task.estimate_h}\n\n"
                "Return a JSON list of focused work sessions, each with:\n"
                "- session_number: int\n"
                "- focus: what to accomplish in this pomodoro\n"
                "- deliverable: tangible output expected\n"
            )
        else:
            prompt = (
                f"Break down this task into smaller, actionable subtasks:\n"
                f"Task: {task.title}\n"
                f"Details: {task.detail}\n"
                f"Estimated hours: {task.estimate_h}\n\n"
                f"User prefers {preferences.preferred_task_size} task sizes.\n"
                "Return a JSON list of subtasks, each with:\n"
                "- title: str\n"
                "- detail: str\n"
                "- estimate_h: int (should sum to approximately the parent task estimate)\n"
                "- order: int (execution order)\n"
            )

        content = await chat_model([{"role": "user", "content": prompt}])

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return []


# Standalone function wrappers for backward compatibility
_planner_instance = None


def _get_planner():
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = PlannerAgent()
    return _planner_instance


async def clarify_llm(state: dict) -> dict:
    return await _get_planner().clarify_llm(state)


async def integrate_clarifications_llm(state: dict) -> dict:
    return await _get_planner().integrate_clarifications_llm(state)


async def plan_llm(state: dict) -> dict:
    return await _get_planner().plan_llm(state)


async def prioritize_llm(state: dict) -> dict:
    return await _get_planner().prioritize_llm(state)


async def estimate_llm(state: dict) -> dict:
    return await _get_planner().estimate_llm(state)


async def package_llm(state: dict) -> dict:
    return await _get_planner().package_llm(state)


async def breakdown_task_llm(
    task: Task, breakdown_type: str = "subtasks"
) -> List[Dict]:
    return await _get_planner().breakdown_task_llm(task, breakdown_type)
