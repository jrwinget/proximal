# Trellis 🌿

<!-- badges: start -->
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/jrwinget/trellis/actions/workflows/test.yml/badge.svg)](https://github.com/jrwinget/trellis/actions/workflows/test.yml)
[![Code Size](https://img.shields.io/github/languages/code-size/jrwinget/trellis)](https://github.com/jrwinget/trellis)
<!-- badges: end -->

An AI agent that transforms vague ideas into actionable project plans through
natural conversation.

## Overview

Trellis acts as a personal project manager, breaking down complex goals and
ambiguous thoughts into structured, sprint-based road maps. Through natural
language interaction, it helps clarify task requirements, identify dependencies,
and create comprehensive action plans with priority levels and time estimates.

## Features

### 🎯 Core Capabilities
- **Natural Language Processing**: Understands vague, high-level project
  descriptions
- **Interactive Clarification**: Asks smart questions to extract hidden
  requirements
- **Sprint Planning**: Automatically organizes tasks into manageable sprints
- **Smart Estimation**: Provides effort estimates based on task complexity
- **Dependency Mapping**: Identifies and visualizes task relationships
- **Priority Tagging**: Assigns priority levels (P0-P3) based on context and
  deadlines
- **Task Breakdown**: Breaks large tasks into subtasks or Pomodoro sessions
- **Memory & Context**: Remembers past projects and user preferences

### 🔧 Technical Features
- **Multi-Provider Support**: Works with OpenAI, Anthropic, and Ollama LLMs
- **Tool Integration**: Seamlessly connects with project management tools
- **Adaptive Communication**: Adjusts tone from casual brainstorming to formal
  documentation
- **Continuous Learning**: Improves planning accuracy based on user feedback
- **Context Awareness**: Remembers project history and user preferences through
  vector storage

## Getting Started

### Prerequisites
- Python 3.12+
- LLM provider (at least one of):
  - Ollama running locally
  - OpenAI API key
  - Anthropic API key
- Weaviate for memory storage

### Installation
```bash
# clone repo
git clone https://github.com/jrwinget/trellis.git
cd trellis

# install dependencies
pip install -e .

# set up environment variables
cp .env.example .env
# edit .env with your provider choice and credentials
```

### Quick Start
```bash
# start the server
python -m apps.server.main

# in another terminal, use the CLI
trellis plan "I want to build a mobile app for tracking habits"
```

## Usage Examples

### CLI Interface
```bash
# basic planning
trellis plan "Create a portfolio website"

# save plan to a file
trellis plan "Redesign the user dashboard" --output plan.json

# show version
trellis version
```

### API Usage
```python
# using the API directly
import httpx

response = httpx.post(
    "http://localhost:7315/plan",
    json={"message": "Build a task management app"}
)

sprints = response.json()
```

## Architecture

```
trellis/
├── apps/
│   ├── server/          # FastAPI server
│   │   ├── main.py      # API endpoints
│   │   └── pipeline.py  # LangGraph pipeline
│   └── cli.py           # Command-line interface
├── packages/
│   ├── core/            # Core functionality
│   │   ├── providers/   # LLM providers
│   │   ├── agents.py    # Agent functions
│   │   ├── memory.py    # Vector storage
│   │   ├── models.py    # Data models
│   │   └── settings.py  # Configuration
│   └── voice/           # (Future) Voice interface
└── tests/               # Test suite
```

## Configuration

Create a `.env` file with your configuration:

```env
# required: choose a LLM provider
TRELLIS_PROVIDER=ollama  # or openai, anthropic

# For Ollama
OLLAMA_BASE_URL=http://localhost:8080
OLLAMA_MODEL=llama3:70b-instruct # ensure the model is available locally

# For OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1 # (optional to override)
# OPENAI_MODEL=gpt-4o-mini # (optional to override)

# For Anthropic
# ANTHROPIC_API_KEY=sk-...
# ANTHROPIC_BASE_URL=https://api.anthropic.com/v1 # (optional to override)
# ANTHROPIC_MODEL=claude-3-haiku # (optional to override)
```

## API Reference

### FastAPI Endpoints

#### `POST /plan`
Transforms a project description into a structured plan.

Request body:
```json
{
  "message": "Create a todo app"
}
```

Response:
```json
[
  {
    "name": "Sprint 1",
    "start": "2023-06-01",
    "end": "2023-06-15",
    "tasks": [
      {
        "id": "task1",
        "title": "Create login page",
        "detail": "Implement user authentication",
        "priority": "P1",
        "estimate_h": 8,
        "done": false
      }
    ]
  }
]
```

## Contributing

We welcome contributions! Please see our
[Contributing Guidelines](docs/CONTRIBUTING.md) for details.

### Development Setup
```bash
# install dev dependencies
pip install -e ".[dev]"

# run tests
pytest

# run with coverage
pytest --cov=packages
```

## Roadmap

- [ ] Enhanced voice recognition with speaker diarization
- [ ] Real-time collaboration features
- [ ] Mobile app (iOS/Android)
- [ ] Advanced analytics dashboard
- [ ] Custom workflow templates
- [ ] Slack/Discord integration
- [ ] Multi-language support

## License

This project is licensed under the AGPL License. See the
[LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with love for everyone who struggles with project/task planning
- Special focus on supporting neurodiverse workflows
- Inspired by the best human project managers

---

> **Trellis** - Growing ideas into reality, one task at a time. 🌱
