# Contributing to Proximal

Thank you for considering contributing to Proximal! We're building this tool to
help everyone plan better, and your contributions make that possible. This guide
will help you get started.

## Code of Conduct

Please note that Proximal has a [Code of Conduct](CODE_OF_CONDUCT.md). By
contributing, you agree to abide by its terms. We're committed to creating a
welcoming and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues as you might find that
you don't need to create one. When you create a bug report, include as many
details as possible:

- Use a clear and descriptive title
- Describe the exact steps to reproduce the problem
- Provide specific examples to demonstrate the steps
- Describe the behavior you observed and what behavior you expected
- Include screenshots if relevant
- Note your Python version, OS, and any relevant dependencies

### Suggesting Features

We love hearing ideas for new features! When suggesting enhancements:

- Use a clear and descriptive title
- Provide a step-by-step description of the suggested enhancement
- Explain why this enhancement would be useful to most Proximal users
- Consider how it might help users with different planning styles and needs
- List any alternatives you've considered

### Your First Code Contribution

Unsure where to begin? Look for these tags in our issues:

- `good first issue` - Simple issues perfect for beginners
- `help wanted` - Issues where we'd particularly appreciate help
- `documentation` - Help improve our docs

### Pull Request Process

1. **Fork and clone** the repository
2. **Create a branch** for your changes:
   `git checkout -b feature/your-feature-name`
3. **Make your changes** following our style guide (see below)
4. **Add tests** for any new functionality
5. **Run the test suite** and ensure all tests pass
6. **Update documentation** as needed
7. **Commit your changes** using clear, descriptive messages
8. **Push to your fork** and submit a pull request
9. **Wait for review** - we aim to review PRs within 3-5 days

## Development Workflow

### Setting Up Your Environment

```bash
# Clone your fork
git clone https://github.com/jrwinget/proximal.git
cd proximal

# Add upstream remote
git remote add upstream https://github.com/jrwinget/proximal.git

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# (optional) install MCP and server extras for full testing
pip install -e ".[dev,mcp,server]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_mcp_server.py

# Run with coverage
pytest --cov=packages --cov-report=html

# Run only fast tests (skip integration tests)
pytest -m "not integration"
```

### Linting

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .          # check for issues
ruff check . --fix    # auto-fix what can be fixed
```

### Writing Tests

- Write tests for all new functionality
- Use descriptive test names that explain what's being tested
- Include both positive and edge cases
- Mock external API calls
- Use fixtures for common test data

Example test structure:

```python
@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
async def test_agent_transforms_vague_input_into_structured_plan(mock_chat):
    """Test that vague project descriptions produce structured outputs."""
    # setup mock
    mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P1", "estimate_h": 5, "done": false}]'

    # call the function
    result = await plan_llm({"goal": "build a website"})

    # verify the result
    assert "tasks" in result
    assert len(result["tasks"]) > 0
    assert all(task.priority in ["P0", "P1", "P2", "P3"] for task in result["tasks"])
```

## Project Structure

```
proximal/
├── apps/                # Application entry points
│   ├── server/          # FastAPI server (requires `.[server]`)
│   │   ├── main.py      # API endpoints
│   │   └── pipeline.py  # Request pipeline
│   ├── cli.py           # Command-line interface
│   └── mcp_server.py    # MCP server (requires `.[mcp]`)
├── packages/            # Core packages
│   └── core/            # Core functionality
│       ├── agents/      # Agent implementations
│       │   ├── registry.py
│       │   ├── planner.py
│       │   ├── chronos.py
│       │   ├── guardian.py
│       │   ├── mentor.py
│       │   ├── liaison.py
│       │   ├── scribe.py
│       │   └── focusbuddy.py
│       ├── providers/   # LLM providers (litellm-backed)
│       ├── integrations/ # External integrations
│       ├── models.py    # Pydantic data models
│       ├── memory.py    # Storage layer (aiosqlite)
│       ├── session.py   # Session management
│       ├── settings.py  # Configuration via pydantic-settings
│       ├── orchestrator.py  # Multi-agent orchestrator
│       ├── observability.py # Logging and tracing
│       └── fault_tolerance.py # Retry and timeout utilities
├── tests/               # Test suite
└── docs/                # Documentation
```

### Extending Proximal: The Capability System

The primary way to extend proximal is through the **capability system**.
Capabilities are registered functions that agents can invoke. To add a new
capability:

1. Create a function in the appropriate module (or a new module under
   `packages/core/`).
2. Register it using the capability registry so agents can discover and call it.
3. Write tests covering the new capability.

For advanced use cases (e.g. a completely new agent archetype), see
[docs/plugins.md](plugins.md) for agent registration via entry points.

## Documentation

### Docstring Format

We use NumPy-style docstrings:

```python
def plan_llm(state: dict) -> dict:
    """
    Transform goal into tasks.

    Parameters
    ----------
    state : dict
        Dictionary containing the goal

    Returns
    -------
    dict
        Dictionary containing the tasks

    Examples
    --------
    >>> result = await plan_llm({"goal": "Create a mobile app"})
    >>> print(len(result["tasks"]))
    5
    """
```

### Updating Documentation

- Update docstrings when changing function signatures
- Add examples for new features
- Update README.md for significant changes
- Consider adding guides for complex features

## Commit Message Guidelines

We follow conventional commits format:

```
type(scope): subject

body

footer
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

Examples:

```
feat(mcp): add MCP server with planning tools

fix(cli): improve error handling for API connection failures

docs(readme): update installation instructions
```

## Release Process

We use semantic versioning (MAJOR.MINOR.PATCH):

- MAJOR: Incompatible API changes
- MINOR: New functionality, backwards compatible
- PATCH: Bug fixes, backwards compatible

Releases are automated via GitHub Actions when tags are pushed.

## Getting Help

- **Discussions**: Use GitHub Discussions for longer-form questions
- **Email**: [contact@jrwinget.com](mailto:contact@jrwinget.com) for sensitive
  matters

## Recognition

We value all contributions! Contributors are:

- Added to our AUTHORS file
- Mentioned in release notes
- Eligible for contributor badges

## Tips for Success

1. **Start small**: Your first PR doesn't need to be perfect
2. **Ask questions**: We're here to help
3. **Be patient with yourself**: Planning tools are complex
4. **Think inclusively**: Consider users with different needs and workflows
5. **Have fun**: We're building something helpful together!

## License

By contributing, you agree that your contributions will be licensed under the
same [AGPL License](../LICENSE) that covers the project.
