from typing import List, TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, START, END
from packages.core.models import Sprint, Task
from packages.core.agents import (
    plan_llm,
    prioritize_llm,
    estimate_llm,
    package_llm,
    clarify_llm,
    integrate_clarifications_llm,
)


class PipelineState(TypedDict):
    goal: str
    original_goal: Optional[str]
    tasks: Annotated[List[Task], "Tasks to be processed"]
    sprints: Annotated[List[Sprint], "Final sprint output"]
    session_id: Optional[str]
    needs_clarification: Optional[bool]
    clarification_questions: Optional[List[str]]


# one-shot pipeline (no clarification)
def create_direct_pipeline():
    g = StateGraph(PipelineState)

    g.add_node("plan", plan_llm)
    g.add_node("prioritize", prioritize_llm)
    g.add_node("estimate", estimate_llm)
    g.add_node("sprint", package_llm)

    g.add_edge(START, "plan")
    g.add_edge("plan", "prioritize")
    g.add_edge("prioritize", "estimate")
    g.add_edge("estimate", "sprint")
    g.add_edge("sprint", END)

    return g.compile()


# clarification pipeline
def create_interactive_pipeline():
    g = StateGraph(PipelineState)

    # Nodes
    g.add_node("clarify", clarify_llm)
    g.add_node("integrate", integrate_clarifications_llm)
    g.add_node("plan", plan_llm)
    g.add_node("prioritize", prioritize_llm)
    g.add_node("estimate", estimate_llm)
    g.add_node("sprint", package_llm)

    # conditional routing
    def route_after_clarify(state):
        if state.get("needs_clarification", False):
            return "needs_clarification"
        return "proceed"

    # clarification check
    g.add_edge(START, "clarify")

    # conditional edge after clarify
    g.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {
            "needs_clarification": END,  # return to user for answers
            "proceed": "plan",  # continue to planning
        },
    )

    # if clarifications provided, integrate them
    g.add_edge("integrate", "plan")

    # rest of pipeline
    g.add_edge("plan", "prioritize")
    g.add_edge("prioritize", "estimate")
    g.add_edge("estimate", "sprint")
    g.add_edge("sprint", END)

    return g.compile()


DIRECT_PIPELINE = create_direct_pipeline()
INTERACTIVE_PIPELINE = create_interactive_pipeline()
PIPELINE = DIRECT_PIPELINE
