# Plugin Architecture

Proximal supports third‑party agents and providers via standard Python entry points.

Register a new provider:
```python
from packages.core.providers.router import register_provider
from packages.proximal.providers.base import BaseProvider

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
