# Plugin Architecture

Proximal supports extension through two mechanisms: the **capability system**
(recommended) and **agent registration** (advanced).

## Capability Registration (Recommended)

Capabilities are the primary extension point. A capability is a registered
callable that agents can discover and invoke at runtime.

### Registering a Custom Capability

```python
from packages.core.capabilities.registry import register_capability

@register_capability(
    name="research_topic",
    description="Look up background information on a topic",
    category="research",
)
async def research_topic(topic: str, depth: str = "summary") -> dict:
    """Look up background information on a topic."""
    # your implementation here
    return {"summary": "...", "sources": []}
```

### Using Entry Points

Package your capability as a pip-installable package and declare the entry
point in `pyproject.toml`:

```toml
[project.entry-points."proximal.plugins"]
researcher = "my_pkg.researcher"
```

Proximal loads all `proximal.plugins` entry points on startup, so your
capability is available without any code changes in the core project.

## Agent Registration (Advanced)

For a fully custom agent, extend `BaseAgent` and register it. Your agent
participates in the phased orchestration pipeline via `run(context)` and
optionally gates itself with `can_contribute(context)`:

```python
from packages.core.agents.base import BaseAgent
from packages.core.agents.registry import register_agent

@register_agent("researcher")
class ResearcherAgent(BaseAgent):
    """A custom agent that performs research."""

    name = "researcher"

    async def run(self, context):
        goal = context.goal
        # your agent logic using SharedContext signals, tasks, etc.
        return {"findings": "..."}

    def can_contribute(self, context) -> bool:
        # optionally gate: only contribute when a specific signal is set
        return context.get_signal("needs_research", False)
```

## Provider Plugins

Register a new LLM provider:

```python
from packages.core.providers.router import register_provider
from packages.core.providers.base import BaseProvider

@register_provider("myprov")
class MyProvider(BaseProvider):
    async def chat_complete(self, messages: list[dict], **kw) -> str:
        ...
```

Add the module path to your package's `pyproject.toml`:

```toml
[project.entry-points."proximal.plugins"]
myprov = "my_pkg.provider"
```

On import, Proximal will load entry points and register the classes.

> **Note**: With litellm backing the provider layer, you may not need a custom
> provider at all -- litellm already supports 100+ LLM backends. Use a custom
> provider only when litellm does not cover your use case.
