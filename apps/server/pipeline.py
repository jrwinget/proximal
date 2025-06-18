from typing import List, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from packages.core.models import Sprint, Task
from packages.core.agents import (
    plan_llm,
    prioritize_llm,
    estimate_llm,
    package_llm,
)


class PipelineState(TypedDict):
    goal: str
    tasks: Annotated[List[Task], "Tasks to be processed"]
    sprints: Annotated[List[Sprint], "Final sprint output"]


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

PIPELINE = g.compile()
