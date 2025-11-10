from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Literal
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .pipeline import DIRECT_PIPELINE, INTERACTIVE_PIPELINE
from packages.core.session import session_manager
from packages.core.models import (
    ConversationState,
    MessageRole,
    UserPreferences,
    Sprint,
    Task,
)
from packages.core.agents import (
    breakdown_task_llm,
    integrate_clarifications_llm,
    plan_llm,
    prioritize_llm,
    estimate_llm,
    package_llm,
)
from packages.core.settings import get_settings

# configure logging based on settings
_settings = get_settings()
logging.basicConfig(
    level=getattr(logging, _settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# configure rate limiting
limiter = Limiter(key_func=get_remote_address)
rate_limit = f"{_settings.rate_limit_per_minute}/minute" if _settings.rate_limit_enabled else None

# api key header for authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str | None = Security(api_key_header)) -> str | None:
    """verify api key if configured, otherwise allow all requests"""
    settings = get_settings()

    # if no api key is configured, allow all requests (development mode)
    if not settings.proximal_api_key:
        return None

    # if api key is configured, verify it matches
    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail="API Key Required - Set X-API-Key Header"
        )

    if api_key != settings.proximal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return api_key


class Goal(BaseModel):
    # goal/message input should be meaningful but not excessive, max 10000 chars
    message: str = Field(min_length=1, max_length=10000)


class ConversationStart(BaseModel):
    # initial message for conversation, max 10000 chars
    message: str = Field(min_length=1, max_length=10000)
    preferences: Optional[Dict] = None  # allow updating preferences


class ConversationContinue(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    answers: Union[str, Dict[str, str]]  # single answer / question->answer mapping


class TaskBreakdownRequest(BaseModel):
    task_id: Optional[str] = None
    task: Optional[Task] = None  # full task object if not fetching by ID
    breakdown_type: Literal["subtasks", "pomodoros"]  # "subtasks" or "pomodoros"


class ConversationResponse(BaseModel):
    session_id: str
    type: str  # "questions" or "plan"
    questions: Optional[List[str]] = None
    plan: Optional[List[Sprint]] = None
    message: Optional[str] = None


class PreferencesUpdate(BaseModel):
    sprint_length_weeks: Optional[int] = None
    priority_system: Optional[str] = None
    tone: Optional[str] = None
    work_hours_per_week: Optional[int] = None
    preferred_task_size: Optional[str] = None
    include_breaks: Optional[bool] = None
    timezone: Optional[str] = None


app = FastAPI(
    title="Proximal API",
    description="Agentic ecosystem helping to scaffold executing functioning",
    version="0.2.0",
)

# add rate limiting to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.post("/plan", response_model=List[Sprint])
@limiter.limit(rate_limit or "1000/minute")
async def plan(request: Request, goal: Goal, _: str | None = Depends(verify_api_key)):
    """One-shot planning endpoint (backward compatible)"""
    initial_state = {"goal": goal.message}
    result = await DIRECT_PIPELINE.ainvoke(initial_state)
    return result["sprints"]


@app.post("/conversation/start", response_model=ConversationResponse)
@limiter.limit(rate_limit or "1000/minute")
async def start_conversation(request: Request, conv_request: ConversationStart, _: str | None = Depends(verify_api_key)):
    """Start an interactive planning conversation or update preferences only."""
    # if only updating preferences, update and return
    if conv_request.preferences:
        current_prefs = session_manager.get_user_preferences()
        for key, value in conv_request.preferences.items():
            if hasattr(current_prefs, key):
                setattr(current_prefs, key, value)
        session_manager.save_user_preferences(current_prefs)
        return ConversationResponse(session_id="", type="")

    # else fall through to launching the pipeline
    session = await session_manager.create_session(conv_request.message)
    session.add_message(MessageRole.user, conv_request.message)
    initial_state = {"goal": conv_request.message, "session_id": session.session_id}
    result = await INTERACTIVE_PIPELINE.ainvoke(initial_state)

    # if clarifications needed, return questions
    if result.get("needs_clarification", False):
        questions = result.get("clarification_questions", [])
        if questions:
            text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
            session.add_message(MessageRole.assistant, text)
        return ConversationResponse(
            session_id=session.session_id,
            type="questions",
            questions=questions,
        )
    # else return the plan directly
    return ConversationResponse(
        session_id=session.session_id,
        type="plan",
        plan=result.get("sprints", []),
    )


@app.post("/conversation/continue", response_model=ConversationResponse)
@limiter.limit(rate_limit or "1000/minute")
async def continue_conversation(request: Request, conv_continue: ConversationContinue, _: str | None = Depends(verify_api_key)):
    """Continue an existing conversation"""
    session = await session_manager.get_session(conv_continue.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # record user's answers
    if isinstance(conv_continue.answers, str):
        answers_text = conv_continue.answers
    else:
        answers_text = "\n".join(f"{q}: {a}" for q, a in conv_continue.answers.items())
    session.add_message(MessageRole.user, answers_text)

    # proceed directly to planning (integration + pipeline)
    enriched = await integrate_clarifications_llm(
        {
            "goal": session.goal,
            "session_id": session.session_id,
        }
    )
    enriched["session_id"] = session.session_id

    state = await plan_llm(enriched)
    state = await prioritize_llm(state)
    state = await estimate_llm(state)
    state = await package_llm(state)

    return ConversationResponse(
        session_id=session.session_id,
        type="plan",
        plan=state.get("sprints", []),
    )


@app.get("/conversation/{session_id}")
@limiter.limit(rate_limit or "1000/minute")
async def get_conversation(request: Request, session_id: str, _: str | None = Depends(verify_api_key)):
    """Get current conversation state"""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {
        "session_id": session.session_id,
        "status": session.status,
        "messages": [m.model_dump() for m in session.messages],
        "clarification_count": session.clarification_count,
    }


@app.post("/task/breakdown")
@limiter.limit(rate_limit or "1000/minute")
async def breakdown_task(request: Request, task_request: TaskBreakdownRequest, _: str | None = Depends(verify_api_key)):
    """Break down a task into subtasks or pomodoros"""
    task = task_request.task
    if not task:
        raise HTTPException(status_code=400, detail="Task required")
    breakdown = await breakdown_task_llm(task, task_request.breakdown_type)
    return {
        "task_id": task.id,
        "task_title": task.title,
        "breakdown_type": task_request.breakdown_type,
        "breakdown": breakdown,
    }


@app.get("/preferences")
@limiter.limit(rate_limit or "1000/minute")
async def get_preferences(request: Request, _: str | None = Depends(verify_api_key)):
    """Get current user preferences"""
    prefs = session_manager.get_user_preferences()
    return prefs.model_dump()


@app.put("/preferences")
@limiter.limit(rate_limit or "1000/minute")
async def update_preferences(request: Request, update: PreferencesUpdate, _: str | None = Depends(verify_api_key)):
    """Update user preferences"""
    current = session_manager.get_user_preferences()
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(current, key, value)
    session_manager.save_user_preferences(current)
    return current.model_dump()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "0.2.0"}


def start():
    import uvicorn

    uvicorn.run(
        "apps.server.main:app",
        host="0.0.0.0",
        port=7315,
        reload=True,
    )
