from fastapi import FastAPI
from pydantic import BaseModel
from .pipeline import PIPELINE


class Goal(BaseModel):
    message: str


app = FastAPI()


@app.post("/plan")
async def plan(goal: Goal):
    initial_state = {"goal": goal.message}
    result = await PIPELINE.ainvoke(initial_state)
    return result["sprints"]


def start():
    import uvicorn

    uvicorn.run(
        "apps.server.main:app",
        host="0.0.0.0",
        port=7315,
        reload=True,
    )
