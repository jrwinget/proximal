# `proximal` 🌿

<!-- badges: start -->
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/jrwinget/proximal/actions/workflows/test.yml/badge.svg)](https://github.com/jrwinget/proximal/actions/workflows/test.yml)
[![Plugins](https://img.shields.io/badge/plugins-enabled-brightgreen.svg)](docs/plugins.md)
<!-- badges: end -->

**Your AI planning partner that meets you where you are.**

`proximal` transforms fuzzy thoughts into actionable plans through conversation. Built specifically for neurodiverse minds, it helps bridge the gap between "I should do this" and actually getting it done — without the overwhelm.

> *"I know what I want to do, I just can't figure out where to start."*

`proximal` gets it. We work with how your brain actually works, not how productivity gurus think it should.

## 💡 Why `proximal`?

### Built for Neurodiverse Minds

**Executive Function Support**
- **Task Initiation**: Breaks down "I want to build X" into concrete first steps
- **Working Memory**: Remembers your preferences, past conversations, and context so you don't have to
- **Planning & Organization**: Transforms abstract goals into structured, bite-sized actions
- **Time Management**: Realistic estimates based on your actual capacity, not idealized productivity

**ADHD-Friendly Features**
- **Low Barrier to Entry**: Just describe what you want — no templates, no forms, no "correct" format
- **Interactive Clarification**: Asks questions when you're vague (because sometimes we don't know exactly what we mean yet)
- **Focus Support**: Pomodoro task breakdowns when you need hyper-focus sessions
- **Break Reminders**: The Guardian agent suggests breaks before burnout hits

**Autistic-Friendly Design**
- **Clear Communication**: Direct, unambiguous task descriptions and expectations
- **Predictable Structure**: Consistent task hierarchies and priority systems
- **Reduced Decision Fatigue**: Agents handle scheduling, prioritization, and planning overhead
- **Sensory Considerations**: Text-based interface with no unnecessary notifications or interruptions

**For Everyone Who Struggles With Executive Function**
- Depression, anxiety, chronic fatigue, or just... life
- `proximal` doesn't judge your energy levels or capacity
- Works with you on good days *and* difficult days

## 🤖 Your Support Team

`proximal` uses 7 specialized AI agents that work together like a personal support team:

| Agent | What They Do For You |
|-------|---------------------|
| **Planner** | Breaks down overwhelming projects into manageable pieces |
| **Chronos** | Helps you realistically schedule tasks around your life |
| **Guardian** | Reminds you to take breaks and prioritize self-care |
| **Mentor** | Provides encouragement and helps you stay motivated |
| **Scribe** | Remembers important details so your working memory doesn't have to |
| **Liaison** | Helps draft emails and messages when words are hard |
| **FocusBuddy** | Creates focused work sessions when you need deep work |

Each agent handles one thing well, so you're not overwhelmed by a single "do everything" AI.

## 🚀 Getting Started

### What You Need
* Python 3.12 or newer
* An AI provider (pick one):
  * **Ollama** (free, runs on your computer)
  * **OpenAI** (paid, API key needed)
  * **Anthropic** (paid, API key needed)

### Setup
```bash
# Download proximal
git clone https://github.com/jrwinget/proximal.git
cd proximal

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install
pip install -e .

# Configure your AI provider
cp .env.example .env
# Edit .env with your settings
```

### Try It Out
```bash
# Simple planning
proximal plan "Redesign my personal website"

# Interactive mode (asks clarifying questions)
proximal plan "Build a mobile app" --interactive

# Break tasks into smaller pieces
proximal breakdown "Implement user authentication" --hours 8

# Get the full team working for you
proximal assist "Launch a marketing campaign"
```

## 🌐 Use as a Web Service (Optional)

Want to integrate `proximal` into your own app? Run it as an API server:

```bash
proximal server
# Runs on http://localhost:7315
```

The API lets you build planning into web apps, mobile apps, or other tools. Optional API key authentication and rate limiting included for production use.

See the [API documentation](docs/API.md) for endpoints and examples.

## ⚙️ Configuration

Edit your `.env` file to set up your AI provider:

**For Ollama (free, local)**
```env
PROVIDER_NAME=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:70b-instruct
```

**For OpenAI**
```env
PROVIDER_NAME=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

**For Anthropic**
```env
PROVIDER_NAME=anthropic
ANTHROPIC_API_KEY=sk-your-key-here
ANTHROPIC_MODEL=claude-3-haiku
```

That's it for basic use! See `.env.example` for optional settings like API authentication, session management, and logging.

## 📍 Road map (next milestones)

- [ ] Full calendar API integration (Google / Outlook)
- [ ] Slack & Discord notification hooks
- [ ] Voice input & speaker diarization
- [ ] Mobile companion app
- [ ] Advanced analytics dashboard

## 📝 License
**AGPL‑3.0**, see [LICENSE](LICENSE) for details.

> *`proximal` — Growing ideas into reality, one task at a time.* 🌱
