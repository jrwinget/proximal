# Proximal 🌿

<!-- badges: start -->
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/jrwinget/proximal/actions/workflows/test.yml/badge.svg)](https://github.com/jrwinget/proximal/actions/workflows/test.yml)
[![Plugins](https://img.shields.io/badge/plugins-enabled-brightgreen.svg)](docs/plugins.md)
<!-- badges: end -->

**Proximal** is a multi‑agent framework that turns vague ideas into structured, sprint‑ready plans — with a special focus on supporting neurodiverse workflows.
The public command‑line interface is called **`proximal`**, powered under the hood by a manager‑style **Orchestrator** that coordinates multiple specialist agents.

## ✨ Core Capabilities

| Capability | Description |
|------------|-------------|
| Natural‐language planning | Understands high‑level project goals and clarifies hidden requirements interactively |
| Sprint breakdown | Generates sprint / task hierarchies with effort estimates and priorities |
| Scheduling | Time‑boxes tasks into a daily or weekly calendar via the **Chronos** agent |
| Well‑being nudges | Injects breaks and self‑care checkpoints via the **Guardian** agent |
| Memory & context | Stores plans and preferences in a vector DB for future sessions |
| Multi‑provider LLMs | Works with local **Ollama**, **OpenAI**, or **Anthropic** models out‑of‑the‑box |
| Plug‑in architecture | Extend agents or providers via entry points |
| Production‑ready | Rate limiting, API authentication, Redis sessions, retry logic, structured logging |

## 🤖 Agents

| Agent | Responsibility |
|-------|---------------|
| **Planner** | Task & sprint decomposition |
| **Chronos** | Scheduling & calendar management |
| **Guardian** | Well‑being nudges & break reminders |
| **Mentor** | Goal‑coaching & motivation |
| **Scribe** | Memory & note capture |
| **Liaison** | Communication drafts |
| **FocusBuddy** | Focus / Pomodoro support |

All agents register automatically via a plugin decorator and are discoverable by the Orchestrator for easy extension.

## 🚀 Quick Start

### Prerequisites
* Python **3.12+**
* At least one LLM backend
  * **Ollama** running locally **or**
  * **OpenAI** API key **or**
  * **Anthropic** API key
* (Optional) **Weaviate** instance for long‑term memory

### Installation
```bash
git clone https://github.com/jrwinget/proximal.git
cd proximal

# recommended: use a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

pip install -e .

# copy and edit environment settings
cp .env.example .env
```

### First plan
```bash
# plan‑only flow
proximal plan "Redesign my personal website"

# interactive planning with clarification questions
proximal plan "Build a mobile app" --interactive

# break down tasks into subtasks or pomodoro tasks
proximal breakdown "Implement user authentication" --hours 8 --type subtasks

# full multi‑agent flow (plan + schedule)
proximal assist "Launch a marketing campaign next quarter"
```

## 🖥️ API Server

```bash
# start FastAPI server on http://localhost:7315
python -m apps.server.main

# or use the CLI shortcut
proximal server
```

### Security Features
- **API Authentication**: Optional API key protection (set `PROXIMAL_API_KEY` in `.env`)
- **Rate Limiting**: Configurable per-minute limits (default: 10 requests/minute)
- **Input Validation**: Pydantic models with field constraints
- **Session Management**: Redis-backed sessions for production (with in-memory fallback)
- **Structured Logging**: Comprehensive logging with configurable levels

### Endpoints
| Method | Path | Description | Authentication |
|--------|------|-------------|----------------|
| `POST` | `/plan` | Return sprint/task plan (Planner only) | Optional |
| `POST` | `/conversation/start` | Start interactive planning session | Optional |
| `POST` | `/conversation/continue` | Continue conversation with answers | Optional |
| `GET` | `/conversation/{session_id}` | Get conversation state | Optional |
| `POST` | `/task/breakdown` | Break down task into subtasks/pomodoro tasks | Optional |
| `GET/PUT` | `/preferences` | View/update user preferences | Optional |
| `GET` | `/health` | Health check endpoint | None |

Example:
```python
from httpx import post

# Headers for authenticated requests
headers = {"X-API-Key": "your-secret-api-key"}

# One-shot planning
resp = post(
  "http://localhost:7315/plan",
  json={"message": "Build a habit‑tracking mobile app"},
  headers=headers
)
print(resp.json())

# Interactive planning
resp = post(
  "http://localhost:7315/conversation/start",
  json={"message": "Build a habit‑tracking mobile app"},
  headers=headers
)
print(resp.json())
```

## 🗂️ Project Layout
```
proximal/
├── apps/
│   ├── server/              # FastAPI app
│   └── cli.py               # proximal CLI (entry point)
├── packages/
│   └── core/
│       ├── agents/          # All 7 agents implemented
│       ├── integrations/    # Calendar, email, automation
│       ├── providers/       # LLM provider abstractions
│       ├── orchestrator.py
│       └── ...
└── tests/                   # pytest suite
```

## ⚙️ Configuration (`.env`)

```env
# === LLM Provider (required) ===
# choose your provider: ollama | openai | anthropic
PROVIDER_NAME=ollama

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:70b-instruct

# OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4o-mini

# Anthropic
# ANTHROPIC_API_KEY=sk-...
# ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
# ANTHROPIC_MODEL=claude-3-haiku

# === API Server Configuration (optional) ===
# PROXIMAL_API_KEY=your-secret-api-key-here  # if not set, API is open
# API_HOST=0.0.0.0
# API_PORT=7315
# API_WORKERS=1

# === Session Management (optional) ===
# SESSION_TIMEOUT_HOURS=1
# MAX_CLARIFICATIONS=2
# REDIS_URL=redis://localhost:6379  # recommended for production

# === LLM Configuration (optional) ===
# LLM_TIMEOUT_SECONDS=120
# LLM_MAX_RETRIES=3
# LLM_RETRY_MIN_WAIT=4
# LLM_RETRY_MAX_WAIT=10

# === Rate Limiting (optional) ===
# RATE_LIMIT_ENABLED=true
# RATE_LIMIT_PER_MINUTE=10

# === Logging (optional) ===
# LOG_LEVEL=INFO

# === Weaviate (optional) ===
# WEAVIATE_URL=http://localhost:8080
# WEAVIATE_API_KEY=  # if authentication is enabled
# SKIP_WEAVIATE_CONNECTION=1  # set to 1 when running tests without Weaviate
```

## 🛠️ Development

```bash
pip install -e ".[dev]"
pytest -q            # run entire suite
```

Atomic commits and green tests are required for PRs. See **docs/CONTRIBUTING.md** for code‑style, commit‑message, and DCO details.

## 📍 Road map (next milestones)

- [ ] Full calendar API integration (Google / Outlook)
- [ ] Slack & Discord notification hooks
- [ ] Voice input & speaker diarization
- [ ] Mobile companion app
- [ ] Advanced analytics dashboard

## 📝 License
**AGPL‑3.0** — see [LICENSE](LICENSE) for details.

> *Proximal — Growing ideas into reality, one task at a time.* 🌱
