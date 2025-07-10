# Proximal 🌿

<!-- badges: start -->
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/emphexis/proximal/actions/workflows/test.yml/badge.svg)](https://github.com/emphexis/proximal/actions/workflows/test.yml)
[![Plugins](https://img.shields.io/badge/plugins-enabled-brightgreen.svg)](docs/plugins.md)
<!-- badges: end -->

**Proximal** is a multi‑agent framework that turns vague ideas into structured, sprint‑ready plans — with a special focus on supporting neurodiverse workflows.  
The public command‑line interface is called **`trellis`**, powered under the hood by a manager‑style **Orchestrator** that coordinates multiple specialist agents.

---

## ✨ Core Capabilities

| Capability | Description |
|------------|-------------|
| Natural‐language planning | Understands high‑level project goals and clarifies hidden requirements interactively |
| Sprint breakdown | Generates sprint / task hierarchies with effort estimates and priorities |
| Scheduling | Time‑boxes tasks into a daily or weekly calendar via the **Chronos** agent |
| Well‑being nudges | Injects breaks and self‑care checkpoints (Guardian agent — coming soon) |
| Memory & context | Stores plans and preferences in a vector DB for future sessions |
| Multi‑provider LLMs | Works with local **Ollama**, **OpenAI**, or **Anthropic** models out‑of‑the‑box |
| Plug‑in architecture | Extend agents or providers via entry points |

---

## 🤖 Agents

| Agent | Responsibility |
|-------|---------------|
| **Trellis** | Planner — task & sprint decomposition |
| **Chronos** | Scheduler — deterministic time‑blocking |
| **Guardian** | Well‑being nudges (coming) |
| **Mentor** | Goal‑coaching & motivation (coming) |
| **Scribe** | Memory & note capture (coming) |
| **Liaison** | Communication drafts (coming) |
| **FocusBuddy** | Focus / Pomodoro support (coming) |

All agents register automatically via a plugin decorator and are discoverable by the Orchestrator for easy extension.

---

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
git clone https://github.com/emphexis/proximal.git
cd proximal
pip install -e .

# copy and edit environment settings
cp .env.example .env
```

### First plan
```bash
# plan‑only flow
trellis plan "Redesign my personal website"

# full multi‑agent flow (plan + schedule)
trellis assist "Launch a marketing campaign next quarter"
```

---

## 🖥️ API Server

```bash
# start FastAPI server on http://localhost:7315
python -m apps.server.main
```

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan` | Return sprint/task plan (Planner only) |
| `POST` | `/assist` | End‑to‑end plan + schedule (Planner + Chronos) |

Example:
```python
from httpx import post
resp = post(
  "http://localhost:7315/assist",
  json={"message": "Build a habit‑tracking mobile app"}
)
print(resp.json())
```

---

## 🗂️ Project Layout
```
proximal/
├── apps/
│   ├── server/          # FastAPI app
│   └── cli.py           # trellis CLI (entry point)
├── packages/
│   └── proximal/
│       ├── agents/      # BaseAgent, Chronos, etc.
│       ├── orchestrator.py
│       └── ...
└── tests/               # pytest suite
```

---

## ⚙️ Configuration (`.env`)

```env
# choose your provider: ollama | openai | anthropic
TRELLIS_PROVIDER=ollama

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:70b-instruct

# OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini

# Anthropic
# ANTHROPIC_API_KEY=sk-...
# ANTHROPIC_MODEL=claude-3-haiku

# set to 1 when running tests without Weaviate
SKIP_WEAVIATE_CONNECTION=1
```

---

## 🛠️ Development

```bash
pip install -e ".[dev]"
pytest -q            # run entire suite
pytest --cov=proximal
black . && flake8
```

Atomic commits and green tests are required for PRs. See **docs/CONTRIBUTING.md** for code‑style, commit‑message, and DCO details.

---

## 📍 Road map (next milestones)

- [ ] Guardian, Mentor, Scribe, Liaison, FocusBuddy implementations  
- [ ] Calendar API integration (Google / Outlook)  
- [ ] Slack & Discord notification hooks  
- [ ] Voice input & speaker diarization  
- [ ] Mobile companion app  
- [ ] Advanced analytics dashboard  

---

## 📝 License
**AGPL‑3.0** — see [LICENSE](LICENSE) for details.

> *Proximal — Growing ideas into reality, one task at a time.* 🌱
