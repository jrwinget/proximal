# Plugin Architecture

Proximal supports extension through two mechanisms: the **capability system**
(recommended) and **agent registration** (advanced).

## Capability Registration (Recommended)

Capabilities are the primary extension point in proximal v0.2. A capability is
a callable that an agent can discover and invoke at runtime.

### Registering a Custom Capability

Create a module with your capability function and register it so the agent
layer can find it:

```python
from packages.core.agents.registry import register_agent

# example: a custom "research" capability that agents can delegate to
async def research_topic(topic: str, depth: str = "summary") -> dict:
    """Look up background information on a topic.

    Parameters
    ----------
    topic : str
        Subject to research.
    depth : str
        One of "summary", "detailed", or "deep-dive".

    Returns
    -------
    dict
        Research findings with keys ``summary`` and ``sources``.
    """
    # your implementation here — call an API, search a database, etc.
    return {"summary": "...", "sources": []}
```

Then wire it into an existing agent or create a thin wrapper agent:

```python
@register_agent("researcher")
class ResearcherAgent:
    async def research(self, topic: str) -> dict:
        return await research_topic(topic)
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

## Agent Registration (Advanced / Legacy)

For cases where you need a fully custom agent class (e.g. with its own state
or lifecycle), you can register an agent directly:

```python
from packages.core.agents.registry import register_agent

@register_agent("myprov")
class MyCustomAgent:
    """A fully custom agent with its own lifecycle."""

    def __init__(self) -> None:
        # custom initialization
        pass

    async def run(self, goal: str) -> dict:
        # your agent logic
        return {"result": "..."}
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

> **Note**: With litellm backing the provider layer in v0.2, you may not need a
> custom provider at all -- litellm already supports 100+ LLM backends. Use a
> custom provider only when litellm does not cover your use case.
