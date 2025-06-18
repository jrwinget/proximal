# Trellis 🌿

An AI agent that transforms vague ideas into actionable project plans through
natural conversation.

## Overview

Trellis acts as a personal project manager, breaking down complex goals and
ambiguous thoughts into structured, sprint-based roadmaps. Through natural
language interaction (text and voice), it helps clarify task requirements,
identify dependencies, and create comprehensive action plans with priority
levels and time estimates.

## Features

### 🎯 Core Capabilities
- **Natural Language Processing**: Understands vague, high-level project
  descriptions
- **Interactive Clarification**: Asks smart questions to extract hidden
  requirements
- **Sprint Planning**: Automatically organizes tasks into manageable sprints
- **Smart Estimation**: Provides effort estimates based on task complexity
- **Dependency Mapping**: Identifies and visualizes task relationships
- **Priority Tagging**: Assigns priority levels based on context and deadlines

### 🔧 Technical Features
- **Multi-Modal Input**: Supports both text and voice interactions
- **Tool Integration**: Seamlessly connects with Jira, Asana, Linear, and other
  PM tools
- **Adaptive Communication**: Adjusts tone from casual brainstorming to formal
  documentation
- **Continuous Learning**: Improves planning accuracy based on user feedback
- **Context Awareness**: Remembers project history and user preferences

## Getting Started

### Prerequisites
```bash
# Required
- Python 3.9+
- OpenAI API key or compatible LLM endpoint
- Node.js 18+ (for voice interface)

# Optional (for integrations)
- Jira/Asana/Linear API credentials
```

### Installation
```bash
# Clone the repository
git clone https://github.com/jrwinget/trellis.git
cd trellis

# Install dependencies
pip install -r requirements.txt
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Quick Start
```python
from trellis import TrellisAgent

# Initialize the agent
agent = TrellisAgent(api_key="your-api-key")

# Transform an idea into a plan
plan = agent.plan("I want to build a mobile app for tracking habits")

# View the structured output
print(plan.sprints)
print(plan.tasks)
print(plan.timeline)
```

## Usage Examples

### Basic Planning
```python
# Simple project breakdown
agent.plan("Create a portfolio website")

# With context
agent.plan(
    "Redesign the user dashboard",
    context="SaaS product, 10k users, focus on performance"
)
```

### Voice Interface
```bash
# Start voice planning session
trellis voice

# Or use in Python
agent.voice_session()
```

### Integration with PM Tools
```python
# Export to Jira
agent.export_to_jira(plan, project_key="PROJ")

# Sync with Linear
agent.sync_with_linear(plan, team_id="team-123")
```

## Architecture

```
trellis/
├── core/
│   ├── agent.py          # Main agent logic
│   ├── planner.py        # Task breakdown engine
│   ├── estimator.py      # Effort estimation
│   └── prioritizer.py    # Priority assignment
├── interfaces/
│   ├── text.py           # Text interaction
│   ├── voice.py          # Voice processing
│   └── api.py            # REST API
├── integrations/
│   ├── jira.py
│   ├── asana.py
│   └── linear.py
└── utils/
    ├── nlp.py            # NLP utilities
    └── formatters.py     # Output formatting
```

## Configuration

Create a `.env` file with your configuration:

```env
# Required
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4

# Optional
JIRA_URL=https://company.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...

# Voice settings
VOICE_LANGUAGE=en-US
VOICE_ACTIVATION=push-to-talk
```

## API Reference

### TrellisAgent

```python
agent = TrellisAgent(
    api_key: str,
    model: str = "gpt-4",
    voice_enabled: bool = True,
    integrations: List[str] = []
)
```

### Methods

#### `plan(description: str, context: str = None) -> Plan`
Transforms a project description into a structured plan.

#### `refine(plan: Plan, feedback: str) -> Plan`
Refines an existing plan based on user feedback.

#### `estimate(tasks: List[Task]) -> List[Task]`
Adds time estimates to a list of tasks.

## Contributing

We welcome contributions! Please see our
[Contributing Guidelines](docs/CONTRIBUTING.md) for details.

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
flake8 .
black .
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

This project is licensed under the AGPL License License. See the
[LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with love for everyone who struggles with project/task planning
- Special focus on supporting neurodiverse workflows
- Inspired by the best human project managers

---

> **Trellis** - Growing ideas into reality, one task at a time. 🌱
