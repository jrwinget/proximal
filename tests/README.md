# Proximal Tests

## Running Tests

```bash
# all tests
pytest

# with coverage (matches CI)
pytest --cov=packages --cov-report=xml

# specific file
pytest tests/test_events.py

# specific test
pytest tests/test_agent_collaboration.py::TestOverwhelmFlow::test_guardian_sets_overwhelm_signal

# skip integration tests
pytest -m "not integration"
```

## Test Dependencies

```bash
pip install -e ".[dev]"
```

## Test Structure

### Core

| File                          | What it tests                                                                                |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| `test_agents.py`              | Agent registration, LLM pipeline functions                                                   |
| `test_agent_collaboration.py` | BaseAgent conformance, SharedContext signals, can_contribute filtering, multi-agent cascades |
| `test_capabilities.py`        | Capability registry and built-in capabilities                                                |
| `test_energy.py`              | Energy levels and EnergyConfig                                                               |
| `test_memory.py`              | SQLite storage, FTS search, preferences, conversations                                       |
| `test_profiles.py`            | Neurodiverse user profiles                                                                   |
| `test_structured.py`          | Pydantic model validation                                                                    |

### Agents (reactive)

| File                        | What it tests                                   |
| --------------------------- | ----------------------------------------------- |
| `test_guardian_reactive.py` | Guardian event subscriptions, wellness tracking |
| `test_chronos_reactive.py`  | Chronos event subscriptions, estimate learning  |
| `test_wellness_rules.py`    | Pure-function pattern detection (no DB)         |
| `test_wellness_memory.py`   | Wellness SQLite persistence                     |
| `test_estimate_learning.py` | Task timing records, estimate bias              |
| `test_calendar_provider.py` | Calendar provider ABC and stub                  |

### Agents (profile-aware)

| File                         | What it tests                                                             |
| ---------------------------- | ------------------------------------------------------------------------- |
| `test_focusbuddy_profile.py` | `preferred_session_minutes`, `focus_style` adaptation, energy blending    |
| `test_chronos_profile.py`    | `peak_hours` scheduling, `time_blindness` buffers and transitions         |
| `test_guardian_profile.py`   | `low_energy_days` proactive mode, reduced thresholds                      |
| `test_mentor_profile.py`     | `tone`, `celebration_style`, `verbosity` personalization                  |
| `test_planner_profile.py`    | `decision_fatigue` task capping, priority sorting                         |
| `test_signal_wiring.py`      | `low_energy_mode` and `deadline_at_risk` signal propagation across agents |

### Agents (execution layer)

| File                            | What it tests                                                                      |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| `test_focusbuddy_execution.py`  | Mid-session check-ins, transitions, momentum tracking, retrospectives, presence mode |

### Orchestration & workflows

| File                      | What it tests                               |
| ------------------------- | ------------------------------------------- |
| `test_orchestrator.py`    | V1 scatter-gather orchestrator              |
| `test_orchestrator_v2.py` | V2 phased execution, signal propagation     |
| `test_workflows.py`       | Workflow definitions, executor, checkpoints |
| `test_scheduler.py`       | Cron loops, event triggers, daily caps      |

### Infrastructure

| File                    | What it tests                                    |
| ----------------------- | ------------------------------------------------ |
| `test_events.py`        | Event bus pub/sub, wildcards, history, lifecycle |
| `test_notifications.py` | Slack/Discord/email notifiers                    |
| `test_analytics.py`     | Task completion, focus sessions, burnout risk    |
| `test_voice.py`         | Whisper transcription, goal extraction           |

### Entry points

| File                        | What it tests             |
| --------------------------- | ------------------------- |
| `test_mcp_server.py`        | MCP tool handlers         |
| `test_cli.py`               | CLI commands              |
| `test_cli_helpers.py`       | CLI utility functions     |
| `test_cli_interactive.py`   | Interactive planning flow |
| `test_pipeline.py`          | Server request pipeline   |
| `test_api_conversations.py` | Conversation API          |

### Integration

| File                             | What it tests                |
| -------------------------------- | ---------------------------- |
| `test_integration_multiagent.py` | Multi-agent end-to-end flows |
| `test_proximal.py`               | Full system smoke tests      |

## Conventions

- `pytest-asyncio` with `asyncio_mode = "auto"` for async tests
- `conftest.py` mocks all LLM calls via `litellm.acompletion` and sets `SKIP_WEAVIATE_CONNECTION=1`
- External services are never called -- use `AsyncMock` / `MagicMock`
- In-memory SQLite (via `tmp_path`) for storage tests
