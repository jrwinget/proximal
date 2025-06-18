# Contributing to Trellis

Thank you for considering contributing to Trellis! We're building this tool to
help everyone plan better, and your contributions make that possible. This guide
will help you get started.

## Code of Conduct

Please note that Trellis has a [Code of Conduct](CODE_OF_CONDUCT.md). By
contributing, you agree to abide by its terms. We're committed to creating a
welcoming and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues as you might find that
you don't need to create one. When you create a bug report, include as many
details as possible:

* Use a clear and descriptive title
* Describe the exact steps to reproduce the problem
* Provide specific examples to demonstrate the steps
* Describe the behavior you observed and what behavior you expected
* Include screenshots if relevant
* Note your Python version, OS, and any relevant dependencies

### Suggesting Features

We love hearing ideas for new features! When suggesting enhancements:

* Use a clear and descriptive title
* Provide a step-by-step description of the suggested enhancement
* Explain why this enhancement would be useful to most Trellis users
* Consider how it might help users with different planning styles and needs
* List any alternatives you've considered

### Your First Code Contribution

Unsure where to begin? Look for these tags in our issues:

* `good first issue` - Simple issues perfect for beginners
* `help wanted` - Issues where we'd particularly appreciate help
* `documentation` - Help improve our docs

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
git clone https://github.com/YOUR_USERNAME/trellis.git
cd trellis

# Add upstream remote
git remote add upstream https://github.com/jrwinget/trellis.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=packages --cov-report=html

# Run only fast tests (skip integration tests)
pytest -m "not integration"
```

### Writing Tests

* Write tests for all new functionality
* Use descriptive test names that explain what's being tested
* Include both positive and edge cases
* Mock external API calls
* Use fixtures for common test data

Example test structure:
```python
@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
async def test_agent_transforms_vague_input_into_structured_plan(mock_chat):
    """Test that vague project descriptions produce structured outputs."""
    # Setup mock
    mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P1", "estimate_h": 5, "done": false}]'
    
    # Call the function
    result = await plan_llm({"goal": "build a website"})
    
    # Verify the result
    assert "tasks" in result
    assert len(result["tasks"]) > 0
    assert all(task.priority in ["P0", "P1", "P2", "P3"] for task in result["tasks"])
```

## Project Structure

```
trellis/
├── apps/               # Application entry points
│   ├── server/         # FastAPI server
│   │   ├── main.py     # API endpoints
│   │   └── pipeline.py # LangGraph pipeline
│   └── cli.py          # Command-line interface
├── packages/           # Core packages
│   └── core/           # Core functionality
│       ├── providers/  # LLM providers
│       ├── agents.py   # Agent functions
│       ├── memory.py   # Vector storage
│       ├── models.py   # Data models
│       └── settings.py # Configuration
├── tests/              # Test suite
└── docs/               # Documentation
```

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

* Update docstrings when changing function signatures
* Add examples for new features
* Update README.md for significant changes
* Consider adding guides for complex features

## Commit Message Guidelines

We follow conventional commits format:

```
type(scope): subject

body

footer
```

Types:
* `feat`: New feature
* `fix`: Bug fix
* `docs`: Documentation changes
* `style`: Code style changes (formatting, etc.)
* `refactor`: Code refactoring
* `test`: Test additions or modifications
* `chore`: Maintenance tasks

Examples:
```
feat(providers): add support for Anthropic Claude

fix(cli): improve error handling for API connection failures

docs(readme): update installation instructions
```

## Release Process

We use semantic versioning (MAJOR.MINOR.PATCH):

* MAJOR: Incompatible API changes
* MINOR: New functionality, backwards compatible
* PATCH: Bug fixes, backwards compatible

Releases are automated via GitHub Actions when tags are pushed.

## Getting Help

* **Discussions**: Use GitHub Discussions for longer-form questions
* **Email**: [contact@jrwinget.com](mailto:contact@jrwinget.com) for sensitive
  matters

## Recognition

We value all contributions! Contributors are:

* Added to our AUTHORS file
* Mentioned in release notes
* Eligible for contributor badges

## Tips for Success

1. **Start small**: Your first PR doesn't need to be perfect
2. **Ask questions**: We're here to help
3. **Be patient with yourself**: Planning tools are complex
4. **Think inclusively**: Consider users with different needs and workflows
5. **Have fun**: We're building something helpful together!

## License

By contributing, you agree that your contributions will be licensed under the
same [AGPL License](../LICENSE) that covers the project.