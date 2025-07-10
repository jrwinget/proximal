# Proximal Tests

This directory contains unit tests for the Proximal project.

## Running Tests

To run all tests:

```bash
# From the project root
pytest

# With verbose output
pytest -v

# Run specific test file
pytest tests/test_providers.py

# Run specific test function
pytest tests/test_agents.py::test_plan_llm

# Run with coverage
pytest --cov=packages --cov-report=html
```

## Test Dependencies

Make sure you have the required testing dependencies installed:

```bash
# Install testing dependencies
pip install -e ".[dev]"
```

## Test Structure

- `test_agents.py`: Tests for the agent functions (plan_llm, prioritize_llm, estimate_llm, package_llm)
- `test_providers.py`: Tests for the LLM providers (OpenAI, Anthropic, Ollama)
- `test_pipeline.py`: Tests for the LangGraph pipeline flow
- `test_cli.py`: Tests for the command-line interface

## Mocking

All tests use mocks to avoid making actual API calls to LLM providers. This makes the tests faster and more reliable:

- `AsyncMock` for async functions
- `MagicMock` for synchronous functions
- `patch` for replacing functions during testing

## Test Fixtures

Common test fixtures include:

- `sample_tasks`: Creates sample Task objects for testing
- `sample_sprints`: Creates sample Sprint objects for testing
- `runner`: Creates a CLI runner for testing the command-line interface

## Troubleshooting

If you encounter issues with the tests:

1. Make sure all dependencies are installed
2. Check that the mock environment variables in conftest.py match your expected configuration
3. Ensure that the imports in the test files are correct
4. If you're getting import errors, make sure you're running pytest from the project root directory
5. For CLI tests, ensure you have typer and its dependencies installed