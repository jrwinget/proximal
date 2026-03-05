# `proximal`

<!-- badges: start -->

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL
v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Code style:
ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Tests](https://github.com/jrwinget/proximal/actions/workflows/test.yml/badge.svg)](https://github.com/jrwinget/proximal/actions/workflows/test.yml)
[![Plugins](https://img.shields.io/badge/plugins-enabled-brightgreen.svg)](docs/plugins.md)

<!-- badges: end -->

**Your AI planning partner that meets you where you are.**

`proximal` transforms fuzzy thoughts into actionable plans through conversation.
Built specifically for neurodiverse minds, it helps bridge the gap between "I
should do this" and actually getting it done -- without the overwhelm.

> _"I know what I want to do, I just can't figure out where to start."_

`proximal` gets it. We work with how your brain actually works, not how
productivity gurus think it should.

## Why `proximal`?

### Built for Neurodiverse Minds

**Executive Function Support**

- **Task Initiation**: Breaks down "I want to build X" into concrete first steps
- **Working Memory**: Remembers your preferences, past conversations, and
  context so you don't have to
- **Planning & Organization**: Transforms abstract goals into structured,
  bite-sized actions
- **Time Management**: Realistic estimates based on your actual capacity, not
  idealized productivity

**ADHD-Friendly Features**

- **Low Barrier to Entry**: Just describe what you want -- no templates, no
  forms, no "correct" format
- **Interactive Clarification**: Asks questions when you're vague (because
  sometimes we don't know exactly what we mean yet)
- **Focus Support**: Pomodoro task breakdowns when you need hyper-focus sessions
- **Break Reminders**: The Guardian agent suggests breaks before burnout hits

**Autistic-Friendly Design**

- **Clear Communication**: Direct, unambiguous task descriptions and
  expectations
- **Predictable Structure**: Consistent task hierarchies and priority systems
- **Reduced Decision Fatigue**: Agents handle scheduling, prioritization, and
  planning overhead
- **Sensory Considerations**: Text-based interface with no unnecessary
  notifications or interruptions

**For Everyone Who Struggles With Executive Function**

- Depression, anxiety, chronic fatigue, or just... life
- `proximal` doesn't judge your energy levels or capacity
- Works with you on good days _and_ difficult days

## Your Support Team

`proximal` uses 7 specialized AI agents that collaborate through a phased
orchestration pipeline. Each agent handles one thing well, so you're not
overwhelmed by a single "do everything" AI:

| Agent          | What They Do For You                                                                                                                                          |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Planner**    | Breaks down overwhelming projects into manageable pieces. Limits choices when decision fatigue is high.                                                       |
| **Chronos**    | Schedules tasks during your peak hours, buffers time estimates for time blindness, checks calendar conflicts, and learns from your estimates.                 |
| **Guardian**   | Monitors your wellness proactively -- activates low-energy mode on your tough days, tracks breaks, detects burnout, and watches for overwork under deadlines. |
| **Mentor**     | Adapts encouragement to your preferred tone, celebration style, and verbosity. Gets gentler on hard days and supportive when deadlines press.                 |
| **Scribe**     | Remembers important details so your working memory doesn't have to.                                                                                           |
| **Liaison**    | Helps draft emails and messages when words are hard -- activates automatically when deadlines are at risk.                                                    |
| **FocusBuddy** | Creates focus sessions matched to your preferred duration and focus style (hyperfocus, variable, short-burst). Shortens sessions and adds breaks on low days. |

Every agent reads your `UserProfile` to personalize its behavior -- your peak
hours, focus style, time blindness, decision fatigue, low-energy days, tone,
celebration style, and verbosity all shape how the system works with you. Agents
communicate through shared signals (e.g. Guardian detects overwhelm → Mentor
softens its tone → FocusBuddy shortens sessions → Chronos trims the schedule).
Capabilities can be extended via the [plugin system](docs/plugins.md) without
modifying core code.

## Getting Started

### What You Need

- Python 3.12 or newer
- An AI provider -- `proximal` uses
  [litellm](https://docs.litellm.ai/docs/providers) under the hood, which
  supports 100+ providers including:
  - **Ollama** (free, runs on your computer)
  - **OpenAI** (paid, API key needed)
  - **Anthropic** (paid, API key needed)
  - AWS Bedrock, Azure OpenAI, Google Vertex AI, and many more

### Setup

```bash
# download proximal
git clone https://github.com/jrwinget/proximal.git
cd proximal

# create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# install core
pip install -e .

# (optional) extras
pip install -e ".[mcp]"        # MCP server support
pip install -e ".[server]"     # Web API server
pip install -e ".[voice]"      # Voice input (Whisper)
pip install -e ".[analytics]"  # Analytics (matplotlib)
pip install -e ".[calendar]"   # Google Calendar integration

# configure your AI provider
cp .env.example .env
# edit .env with your settings
```

### Try It Out

```bash
# simple planning
proximal plan "Redesign my personal website"

# interactive mode (asks clarifying questions)
proximal plan "Build a mobile app" --interactive

# plan with energy awareness
proximal plan "Redesign my personal website" --energy low

# break tasks into smaller pieces
proximal breakdown "Implement user authentication" --hours 8

# get the full team working for you
proximal assist "Launch a marketing campaign"

# check wellness patterns across sessions
proximal wellness

# view productivity analytics
proximal analytics
proximal analytics --report burnout

# manage autonomous workflows
proximal workflow list
```

## Use as a Web Service (Optional)

Want to integrate `proximal` into your own app? Run it as an API server:

```bash
pip install -e ".[server]"
python -c "from apps.server.main import start; start()"
# Runs on http://localhost:7315
```

The API lets you build planning into web apps, mobile apps, or other tools.
Optional API key authentication and rate limiting included for production use.

### MCP Server Mode

`proximal` can run as an [MCP (Model Context
Protocol)](https://modelcontextprotocol.io) server, exposing its planning tools
to any MCP client -- Claude Desktop, VS Code, Cursor, and more.

```bash
pip install -e ".[mcp]"
proximal mcp-serve
```

Or add it to your MCP client configuration (e.g. Claude Desktop
`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "proximal": {
      "command": "proximal",
      "args": ["mcp-serve"]
    }
  }
}
```

Exposed tools:

- **plan_goal** -- Break a goal into tasks with scheduling and breaks
- **break_down_task** -- Split a task into subtasks or pomodoro sessions
- **draft_message** -- Draft a professional message about a project/task
- **get_motivation** -- Get encouragement for your current work
- **check_wellness** -- Check wellness patterns and burnout risk
- **check_schedule_conflicts** -- Detect scheduling conflicts
- **plan_from_voice** -- Transcribe audio and create a plan (requires `[voice]`)

## Configuration

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

That's it for basic use! See `.env.example` for optional settings like API
authentication, session management, and logging.

## Road map

**v0.3 -- Reactive Agent Layer** (done)

- [x] Event bus for inter-agent communication
- [x] Reactive Guardian with cross-session wellness tracking
- [x] Reactive Chronos with estimate learning and calendar awareness
- [x] Slack, Discord, and email notification hooks

**v0.4 -- Multi-Agent Collaboration** (done)

- [x] SharedContext-based agent collaboration with signals
- [x] 5-phase orchestration (analysis, assessment, adaptation, execution,
      synthesis)
- [x] Autonomous workflows with checkpoint approval gates
- [x] Analytics dashboard (task completion, burnout risk, estimate accuracy)
- [x] Voice input and goal extraction (optional `[voice]` extra)

**v0.5 -- Wire Dormant Infrastructure** (done)

- [x] FocusBuddy uses `preferred_session_minutes` and `focus_style` from profile
- [x] Chronos schedules high-priority tasks during `peak_hours`, buffers for
      `time_blindness`
- [x] Guardian proactively activates `low_energy_mode` on `low_energy_days`,
      reduces overwhelm threshold
- [x] Mentor adapts to `tone`, `celebration_style`, and `verbosity`
- [x] Planner caps tasks and pre-selects priorities for high `decision_fatigue`
- [x] `low_energy_mode` signal wired to FocusBuddy, Chronos, and Mentor
- [x] `deadline_at_risk` signal wired to Guardian and Mentor

**Next**

- [x] Full calendar API integration (Google / Outlook) — `CalendarProvider`
      abstraction with conflict detection, Google (service account) and Outlook
      (Microsoft Graph) providers via optional `[calendar]` extra
- [ ] Deepen execution layer (mid-session check-ins, transition support,
      momentum tracking, body doubling)
- [ ] Emotional intelligence (mood-adaptive tone, frustration detection)
- [ ] Adaptive scaffolding (competence tracking, dynamic support levels)
- [ ] Mobile companion app
- [ ] Speaker diarization for multi-person planning sessions
- [ ] Frontend dashboard for analytics

## License

**AGPL-3.0**, see [LICENSE](LICENSE) for details.

> _`proximal` -- Growing ideas into reality, one task at a time._
