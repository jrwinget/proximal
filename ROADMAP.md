# Proximal Development Roadmap

> From planning support to execution companionship — closing the gap where
> executive function challenges are most acute.

## Motivation

Proximal's agent system is strong at **planning** (Planner, Chronos, Scribe) but
thin during **execution** — the exact phase where ADHD and executive function
difficulties hit hardest. The system captures rich user profile data
(`UserProfile` has 13 fields) but most agents ignore it. Signals flow one
direction (Guardian sets them) but almost nothing reads them. This roadmap
connects dormant infrastructure to the agents that need it, then builds the
execution-phase support that's currently missing.

### What the audit found

| Problem                                                   | Evidence                                                                                                                                                                                                                                           |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 8 UserProfile fields captured but never read by any agent | `time_blindness`, `decision_fatigue`, `transition_difficulty`, `peak_hours`, `low_energy_days`, `preferred_session_minutes`, `celebration_style`, `verbosity`                                                                                      |
| FocusBuddyAgent is 43 lines, ignores profile entirely     | Uses only `energy_config.session_duration_minutes` — never reads `preferred_session_minutes`, `focus_style`, or `transition_difficulty`                                                                                                            |
| MentorAgent reads only one signal                         | Checks `overwhelm_detected` (line 24), ignores `tone`, `celebration_style`, `verbosity`, `low_energy_mode`                                                                                                                                         |
| Signals are dead-ends                                     | Guardian sets `overwhelm_detected` and `low_energy_mode` (line 47-48); Chronos sets `deadline_at_risk` (line 52). Only Mentor reads `overwhelm_detected`. No agent reads `low_energy_mode` or `deadline_at_risk` except Liaison's `can_contribute` |
| No execution-phase support                                | System helps plan but disappears once work begins                                                                                                                                                                                                  |
| Static energy model                                       | Energy level is set once at context creation and never changes                                                                                                                                                                                     |

---

## Phase 1: Wire Dormant Infrastructure

_Connect existing UserProfile fields to agents that should already be using
them. Pure wiring — no new models, no new agents._

**Clinical rationale:** These fields exist because they matter clinically.
`time_blindness` affects how time estimates should be presented.
`decision_fatigue` affects how many choices to surface. `transition_difficulty`
affects how task switches are handled. Leaving them unread means the system
collects sensitive personal data without delivering the personalization it
implies.

### 1.1 FocusBuddy: Use `preferred_session_minutes` and `focus_style`

**Files:** `packages/core/agents/focusbuddy.py` (line 31),
`packages/core/capabilities/productivity.py` (line 86)

Currently `FocusBuddyAgent.run()` uses `energy_config.session_duration_minutes`
for all sessions. The user's `preferred_session_minutes` (default 25) is never
consulted, and `focus_style` ("hyperfocus", "variable", "short-burst") has no
effect.

**Changes:**

- Read `context.user_profile.preferred_session_minutes` and use it as the base
  duration instead of (or blended with) `energy_config.session_duration_minutes`
- Adapt session structure based on `focus_style`:
  - `"hyperfocus"`: Longer uninterrupted blocks, fewer transitions
  - `"variable"`: Mix of lengths, more check-in points
  - `"short-burst"`: Shorter sessions (cap at `preferred_session_minutes`),
    mandatory breaks between each

**Acceptance criteria:**

- [x] Focus sessions reflect `preferred_session_minutes` when it differs from
      `energy_config.session_duration_minutes`
- [x] `focus_style` produces measurably different session structures
- [x] Existing tests pass; new tests cover all three focus styles

### 1.2 Chronos: Use `peak_hours` and `time_blindness` for scheduling

**Files:** `packages/core/agents/chronos.py` (line 44-54),
`packages/core/capabilities/productivity.py` (lines 18-64)

`create_schedule()` assigns tasks into hourly blocks starting at 09:00
regardless of user preferences. `peak_hours` (e.g., `[10, 11, 14, 15]`) should
influence when high-priority tasks are placed. `time_blindness` should affect
how estimates are communicated and buffered.

**Changes:**

- In `ChronosAgent.run()`, read `context.user_profile.peak_hours` and
  `context.user_profile.time_blindness`
- Schedule high-priority/complex tasks during peak hours
- Add time buffers proportional to `time_blindness` severity:
  - `"low"`: No buffer
  - `"moderate"`: +15% buffer on estimates
  - `"high"`: +30% buffer, add explicit "transition time" entries between tasks
- Surface time remaining in concrete terms ("about 2 pomodoros left") rather
  than abstract hours when `time_blindness` is moderate or high

**Acceptance criteria:**

- [x] High-priority tasks land in `peak_hours` slots when possible
- [x] Time estimates include buffers scaled to `time_blindness`
- [x] Tests verify schedule differs by `time_blindness` level

### 1.3 Guardian: Use `low_energy_days` for proactive wellness

**Files:** `packages/core/agents/guardian.py` (line 40-51)

Guardian checks `overwhelm_threshold` but ignores `low_energy_days`. On days the
user has flagged as low-energy, Guardian should proactively reduce load
recommendations before overwhelm is detected.

**Changes:**

- In `GuardianAgent.run()`, check if the current day of week is in
  `context.user_profile.low_energy_days`
- If so, set `low_energy_mode` signal preemptively (currently only set when
  overwhelm is detected)
- Reduce effective `overwhelm_threshold` by ~30% on low-energy days
- Consider emitting a `GUARDIAN_NUDGE` event with a gentle "it's a low-energy
  day" message

**Acceptance criteria:**

- [x] `low_energy_mode` signal is set on days matching `low_energy_days`
- [x] Overwhelm threshold is reduced on low-energy days
- [x] Tests cover both low-energy and normal days

### 1.4 Mentor: Use `tone`, `celebration_style`, and `verbosity`

**Files:** `packages/core/agents/mentor.py` (lines 21-31)

MentorAgent produces the same encouragement regardless of user personality. A
user who set `tone: "direct"` and `celebration_style: "data-driven"` gets the
same warm fuzzy message as everyone else.

**Changes:**

- Read `context.user_profile.tone`, `context.user_profile.celebration_style`,
  and `context.user_profile.verbosity`
- Adapt encouragement style:
  - `celebration_style: "quiet"` → understated acknowledgment
  - `celebration_style: "enthusiastic"` → energetic celebration
  - `celebration_style: "data-driven"` → progress metrics and streaks
- Respect `verbosity`:
  - `"minimal"` → one-liner
  - `"medium"` → 2-3 sentences (current default)
  - `"detailed"` → include context, rationale, next steps
- Match `tone` to message framing

**Acceptance criteria:**

- [x] Mentor output varies by `celebration_style`, `verbosity`, and `tone`
- [x] Tests verify distinct outputs for each combination
- [x] Overwhelm message also adapts to user's preferred tone

### 1.5 Planner: Use `decision_fatigue` to limit choices

**Files:** `packages/core/agents/planner.py` (lines 152-192)

`plan_llm()` generates tasks without considering `decision_fatigue`. Users with
high decision fatigue get the same number of options and choices as everyone
else.

**Changes:**

- Read `context.user_profile.decision_fatigue` (available via
  `session_manager.get_user_preferences()` or passed through context)
- When `decision_fatigue` is `"high"`:
  - Generate fewer tasks (cap at `overwhelm_threshold`)
  - Pre-select priorities rather than presenting options
  - Include a "recommended next step" to reduce choice paralysis
- Include `decision_fatigue` level in the LLM prompt context

**Acceptance criteria:**

- [x] High decision-fatigue users get fewer, more opinionated task lists
- [x] LLM prompt includes decision fatigue context
- [x] Tests verify task count is bounded by overwhelm threshold when decision
      fatigue is high

### 1.6 Wire `low_energy_mode` signal to all consuming agents

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/agents/chronos.py`, `packages/core/agents/mentor.py`

Guardian sets `low_energy_mode` (line 48) but nobody reads it except indirectly
through `energy_config`.

**Changes:**

- FocusBuddy: When `low_energy_mode` is true, shorten sessions and add more
  breaks
- Chronos: When `low_energy_mode` is true, schedule only simple tasks and reduce
  daily hours
- Mentor: When `low_energy_mode` is true, switch to gentler encouragement
  regardless of default tone

**Acceptance criteria:**

- [x] All three agents check and respond to `low_energy_mode` signal
- [x] Behavior changes are meaningful (not just cosmetic)
- [x] Tests verify signal propagation from Guardian through each agent

### 1.7 Wire `deadline_at_risk` signal beyond Liaison

**Files:** `packages/core/agents/chronos.py` (line 52),
`packages/core/agents/mentor.py`, `packages/core/agents/guardian.py`

Chronos sets `deadline_at_risk` but only Liaison reads it (to trigger a
help-request draft). This signal should also affect Guardian (wellness check —
is the user pushing too hard?) and Mentor (adjust encouragement to be supportive
rather than cheerful).

**Changes:**

- Guardian: When `deadline_at_risk` is true, increase wellness monitoring
  frequency and watch for overwork patterns
- Mentor: When `deadline_at_risk` is true, provide grounding encouragement
  ("you're making progress, focus on the next step") rather than generic
  motivation

**Acceptance criteria:**

- [x] Guardian and Mentor both read and respond to `deadline_at_risk`
- [x] Guardian emits appropriate wellness nudges under deadline pressure
- [x] Mentor tone shifts to supportive-under-pressure mode

---

## Phase 2: Deepen Execution Layer

_Make FocusBuddy a real execution companion. Currently 43 lines of session
creation — expand it into the agent that stays with the user during work._

**Clinical rationale:** Executive function challenges peak during task
execution, not planning. "Body doubling" (working alongside someone) is one of
the most effective ADHD strategies. Digital body doubling — periodic check-ins,
progress acknowledgment, gentle redirection — can provide similar benefits. This
phase transforms FocusBuddy from a session generator into an execution
companion.

### 2.1 Mid-session check-ins

**Files:** `packages/core/agents/focusbuddy.py`, `packages/core/events.py`

Add the ability for FocusBuddy to emit check-in events at intervals during a
focus session. These aren't interruptions — they're brief "still here" signals.

**Changes:**

- Subscribe FocusBuddy to `SESSION_TASK_STARTED` events
- Emit periodic `focusbuddy.checkin` events (new topic) at configurable
  intervals
- Check-in content adapts to `focus_style`:
  - `"hyperfocus"`: Very rare, minimal ("still going strong")
  - `"variable"`: Moderate frequency, progress-oriented
  - `"short-burst"`: At each session boundary, transition support
- Read `transition_difficulty` to adjust check-in timing around task switches

**Acceptance criteria:**

- [ ] FocusBuddy emits check-in events during active sessions
- [ ] Check-in frequency and content vary by `focus_style` and
      `transition_difficulty`
- [ ] New `FOCUSBUDDY_CHECKIN` topic added to `Topics` class
- [ ] Tests verify event emission at expected intervals

### 2.2 Transition support

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/collaboration/context.py`

Task transitions are a known difficulty point for ADHD. FocusBuddy should
provide explicit transition scaffolding between tasks.

**Changes:**

- When a task completes and a new one begins, generate a transition message
  based on `transition_difficulty`:
  - `"low"`: Brief summary of next task
  - `"moderate"`: Summary + mental preparation prompt ("the next task involves
    X, you'll need Y")
  - `"high"`: Full transition ritual — close current context, brief break
    prompt, preview of next task, explicit "ready?" checkpoint
- Set a `transition_in_progress` signal that other agents can read

**Acceptance criteria:**

- [ ] Transition messages are generated between tasks
- [ ] Content depth scales with `transition_difficulty`
- [ ] `transition_in_progress` signal is set and cleared appropriately
- [ ] Tests cover all three difficulty levels

### 2.3 Progress momentum tracking

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/collaboration/context.py`

Track task completion momentum within a session to detect when the user is in
flow vs. stalling.

**Changes:**

- Track timestamps of task completions within a session
- Calculate a simple momentum score (tasks completed per hour, trend direction)
- Set signals: `momentum_high`, `momentum_stalling`, `momentum_recovering`
- Other agents can read these signals (Mentor adjusts encouragement, Guardian
  adjusts break frequency)

**Acceptance criteria:**

- [ ] Momentum is calculated from task completion timestamps
- [ ] Signals are set based on momentum trends
- [ ] At least one other agent responds to momentum signals
- [ ] Tests verify momentum calculation and signal setting

### 2.4 Session retrospective

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/agents/scribe.py`

At session end, generate a brief retrospective: what was accomplished, what's
left, and a "restart point" for next session.

**Changes:**

- Subscribe to `SESSION_ENDED` events
- Generate a structured retrospective:
  - Tasks completed vs. planned
  - Actual duration vs. estimated
  - Restart point: "Next time, start with X"
  - Emotional note: adapted to `celebration_style`
- Persist via Scribe for cross-session continuity

**Acceptance criteria:**

- [ ] Retrospective is generated on session end
- [ ] Content includes completion ratio, timing accuracy, and restart point
- [ ] Celebration adapts to `celebration_style`
- [ ] Retrospective is persisted for future sessions

### 2.5 "Body doubling" presence mode

**Files:** `packages/core/agents/focusbuddy.py`

A minimal-interaction mode where FocusBuddy simply indicates presence — like a
study buddy sitting across the table. Especially effective for users with
`focus_style: "variable"` who need external structure.

**Changes:**

- Add a `presence_mode` option to focus sessions
- In presence mode, FocusBuddy emits quiet periodic signals ("still here",
  progress ticks) without requiring user interaction
- Adapt presence frequency to `focus_style` and current energy level
- Can be triggered via CLI (`proximal focus --body-double`) or MCP tool

**Acceptance criteria:**

- [ ] Presence mode emits periodic low-intrusion signals
- [ ] Signal frequency adapts to focus style and energy
- [ ] CLI and MCP entry points support the mode
- [ ] Tests verify signal emission without requiring user interaction

---

## Phase 3: Emotional Intelligence

_Add emotional state awareness so the system can adapt to how the user is
feeling, not just what they're doing._

**Clinical rationale:** Emotional dysregulation is a core feature of ADHD
(Barkley's model), not a side effect. Frustration tolerance is lower, emotional
responses are more intense, and recovery takes longer. A system that ignores
emotional state will keep pushing when the user needs gentleness and stay gentle
when the user has momentum to leverage.

### 3.1 Emotional state model

**Files:** `packages/core/models.py`, `packages/core/collaboration/context.py`

Currently `energy_level` is the only affective signal and it's static (set at
context creation). Add a richer emotional state model.

**Changes:**

- Add an `EmotionalState` model to `models.py`:
  - `mood`: "frustrated", "neutral", "engaged", "energized" (inferred from
    behavior patterns)
  - `frustration_level`: 0.0-1.0 (rises on repeated failures, falls on
    completions)
  - `momentum`: "building", "steady", "declining" (from Phase 2.3)
  - `last_updated`: timestamp
- Add `emotional_state` field to `SharedContext`
- Emotional state updates based on signals: task completions lower frustration,
  repeated estimate overruns raise it

**Acceptance criteria:**

- [ ] `EmotionalState` model exists with documented fields
- [ ] `SharedContext` carries emotional state
- [ ] State updates in response to task events
- [ ] Tests verify state transitions

### 3.2 Frustration detection and response

**Files:** `packages/core/agents/guardian.py`, `packages/core/agents/mentor.py`,
`packages/core/agents/focusbuddy.py`

Detect rising frustration (from task failures, overrun estimates, long stalls)
and adapt system behavior.

**Changes:**

- Guardian: Monitor for frustration indicators (repeated
  `TASK_ESTIMATE_EXCEEDED` events, long gaps between completions)
- Guardian: When frustration threshold exceeded, set `frustration_high` signal
  and emit `GUARDIAN_NUDGE` with a de-escalation message
- Mentor: When `frustration_high`, switch from motivational to validating ("this
  is genuinely hard, and you're still here")
- FocusBuddy: When `frustration_high`, suggest a micro-break or task switch

**Acceptance criteria:**

- [ ] Frustration is tracked and thresholded
- [ ] All three agents respond to `frustration_high` signal
- [ ] Responses are validating, not dismissive
- [ ] Tests simulate frustration-inducing event sequences

### 3.3 Celebration responses

**Files:** `packages/core/agents/mentor.py`,
`packages/core/capabilities/wellness.py`

When tasks are completed, respond according to the user's `celebration_style` —
currently `motivate()` returns the same generic string for everyone.

**Changes:**

- Replace generic `motivate()` with style-aware celebration:
  - `"quiet"`: Brief acknowledgment ("Done. Next up: X")
  - `"enthusiastic"`: Energetic celebration ("Yes! You crushed that!")
  - `"data-driven"`: Stats and progress ("3/5 tasks done, 60% complete, 2h ahead
    of estimate")
- Track completion streaks for `data-driven` style
- Optionally emit a `mentor.celebration` event that other systems can consume

**Acceptance criteria:**

- [ ] Celebration style matches `UserProfile.celebration_style`
- [ ] Each style produces distinct, appropriate output
- [ ] Completion streaks are tracked for data-driven style
- [ ] Tests verify all three styles

### 3.4 Mood-adaptive tone across all agents

**Files:** All agent files, `packages/core/collaboration/context.py`

Make emotional state a first-class input to all agent prompts, not just a
Guardian concern.

**Changes:**

- Add a `get_tone_context()` method to `SharedContext` that combines
  `user_profile.tone`, current emotional state, and active signals into a tone
  directive string
- All agents that produce user-facing text call `get_tone_context()` and include
  it in their output generation
- Tone shifts smoothly: frustrated user gets gentler language, energized user
  gets more direct/ambitious framing

**Acceptance criteria:**

- [ ] `get_tone_context()` synthesizes profile + emotional state + signals
- [ ] At least 4 agents use it in their output generation
- [ ] Tone demonstrably changes with emotional state
- [ ] Tests verify tone adaptation across states

---

## Phase 4: Adaptive Scaffolding

_Gradually reduce support as competence grows, with automatic re-scaffolding
when struggles are detected._

**Clinical rationale:** Vygotsky's Zone of Proximal Development (ZPD) applies
directly — provide support at the edge of current capability, not below it
(patronizing) or above it (overwhelming). People with ADHD often have variable
performance, so scaffolding must be dynamic, not a one-way ramp-down.

### 4.1 Competence tracking

**Files:** `packages/core/models.py`, `packages/core/memory.py`

Track user competence over time to know when to reduce scaffolding.

**Changes:**

- Add a `CompetenceMetrics` model:
  - `tasks_completed`: total count
  - `estimate_accuracy`: ratio of estimated vs. actual time (from
    `estimate_learning.py`)
  - `session_consistency`: how often the user completes planned sessions
  - `break_compliance`: from wellness data
  - `scaffolding_level`: 0.0-1.0 (1.0 = full scaffolding, 0.0 = minimal)
- Persist metrics in SQLite via existing memory infrastructure
- Recalculate after each session

**Acceptance criteria:**

- [ ] Competence metrics are tracked and persisted
- [ ] Scaffolding level adjusts based on metrics
- [ ] Tests verify level calculation from sample data

### 4.2 Dynamic scaffolding in agents

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/agents/planner.py`, `packages/core/agents/mentor.py`

Use scaffolding level to adapt agent behavior depth.

**Changes:**

- FocusBuddy: High scaffolding → frequent check-ins, explicit transitions. Low
  scaffolding → rare check-ins, trust user to self-regulate
- Planner: High scaffolding → more granular task breakdown, explicit next steps.
  Low scaffolding → higher-level tasks, more autonomy
- Mentor: High scaffolding → proactive encouragement. Low scaffolding →
  on-demand only

**Acceptance criteria:**

- [ ] Each agent reads scaffolding level and adapts behavior
- [ ] Behavior change is gradual, not binary
- [ ] Tests verify different behaviors at different scaffolding levels

### 4.3 Re-scaffolding on struggle detection

**Files:** `packages/core/agents/guardian.py`,
`packages/core/collaboration/context.py`

When the system detects the user is struggling (missed sessions, overrun
estimates, declining momentum), automatically increase scaffolding level back
up.

**Changes:**

- Guardian monitors for struggle indicators:
  - 3+ consecutive estimate overruns
  - Declining session completion rate
  - Rising frustration level (from Phase 3.1)
- When struggle detected, increase scaffolding level (up to a cap)
- Set `scaffolding_increased` signal so agents can acknowledge the change ("I
  noticed things are harder right now — I'll give you more structure")
- Scaffolding increase is temporary and decays as metrics improve

**Acceptance criteria:**

- [ ] Struggle detection triggers scaffolding increase
- [ ] Increase is communicated to user via Mentor
- [ ] Scaffolding decays back to earned level when metrics improve
- [ ] Tests simulate struggle → re-scaffold → recovery cycle

---

## Phase 5: Strengths-Based Reframe

_Shift from deficit framing ("managing challenges") to strengths framing
("leveraging abilities"). ADHD brains have genuine cognitive advantages that the
system can recognize and amplify._

**Clinical rationale:** The strengths-based model (Climie & Mastoras, 2015)
shows that reframing ADHD traits as abilities rather than deficits improves
self-efficacy, motivation, and outcomes. Hyperfocus is a genuine productivity
superpower when channeled. Divergent thinking produces novel solutions. Pattern
recognition across domains is often exceptional. A system that only manages
weaknesses misses half the picture.

### 5.1 Hyperfocus detection and protection

**Files:** `packages/core/agents/focusbuddy.py`,
`packages/core/agents/guardian.py`

Detect when a user enters hyperfocus and protect the state rather than
interrupting it.

**Changes:**

- FocusBuddy: Detect hyperfocus indicators (sustained work on a single task, no
  breaks requested, task completion accelerating)
- When hyperfocus detected, set `hyperfocus_active` signal
- Guardian: When `hyperfocus_active`, suppress break nudges but set a ceiling
  (configurable max duration before a gentle check-in)
- FocusBuddy: When hyperfocus ends (task switch, stall), provide a decompression
  transition ("you were in deep focus for 90 minutes — take a moment before
  switching")

**Acceptance criteria:**

- [ ] Hyperfocus is detected from behavioral signals
- [ ] Guardian suppresses non-urgent nudges during hyperfocus
- [ ] Maximum duration ceiling prevents burnout
- [ ] Decompression support provided on exit
- [ ] Tests verify detection, protection, and ceiling behavior

### 5.2 Divergent thinking capture

**Files:** `packages/core/agents/scribe.py`, `packages/core/agents/planner.py`

During planning, capture tangential ideas that arise rather than discarding
them. ADHD minds often generate valuable connections across domains.

**Changes:**

- Add an "idea parking lot" concept to SharedContext (a list of captured
  tangential ideas)
- Planner: When generating tasks, if the LLM produces ideas that don't fit the
  current goal, capture them rather than discarding
- Scribe: Persist the parking lot alongside the plan
- Surface parking lot items at session start ("You had these ideas last time —
  any worth exploring?")

**Acceptance criteria:**

- [ ] Tangential ideas are captured during planning
- [ ] Ideas persist across sessions via Scribe
- [ ] Parking lot is surfaced at relevant moments
- [ ] Tests verify capture and persistence

### 5.3 Pattern recognition celebration

**Files:** `packages/core/agents/mentor.py`

Recognize and celebrate when the user's work shows patterns of strength — not
just task completion, but quality indicators.

**Changes:**

- Track positive patterns:
  - Consistent session completion streaks
  - Improving estimate accuracy over time
  - Cross-domain idea connections (from parking lot)
  - Effective use of peak hours
- Mentor surfaces these patterns as strengths:
  - "You've completed 5 sessions in a row — your consistency is building"
  - "Your time estimates were within 10% this week — you're developing strong
    time awareness"
  - "You keep connecting ideas across projects — that cross-pollination is
    valuable"

**Acceptance criteria:**

- [ ] Positive patterns are detected from historical data
- [ ] Patterns are surfaced as strengths, not metrics
- [ ] Language frames traits as abilities, not compensations
- [ ] Tests verify pattern detection and messaging

---

## Cross-cutting concerns

These apply across all phases:

### Testing strategy

- Each task should include unit tests for new behavior
- Integration tests should verify signal propagation chains (Guardian → signal →
  Mentor response)
- Existing tests must continue to pass — profile-aware behavior should be
  additive, not breaking

### Migration safety

- All new `UserProfile` consumption should handle missing/default values
  gracefully
- New signals should be optional — agents that don't check them should continue
  to work
- New `SharedContext` fields should have sensible defaults

### Privacy

- Emotional state data is sensitive — ensure it follows the same storage/access
  patterns as existing profile data
- Competence metrics should be user-visible and user-controllable
- No emotional data should be included in Liaison-drafted messages without
  explicit opt-in

---

## Dependency graph

```
Phase 1 (Wire Infrastructure)
  ├── 1.1-1.5 can be done in parallel
  ├── 1.6 depends on Guardian signal changes (1.3)
  └── 1.7 depends on Chronos signal being set (existing)

Phase 2 (Execution Layer) depends on Phase 1
  ├── 2.1-2.2 can be done in parallel
  ├── 2.3 independent
  ├── 2.4 depends on 2.3 (uses momentum data)
  └── 2.5 depends on 2.1 (uses check-in infrastructure)

Phase 3 (Emotional Intelligence) depends on Phase 2.3
  ├── 3.1 independent (model only)
  ├── 3.2 depends on 3.1
  ├── 3.3 independent (can start with Phase 1.4)
  └── 3.4 depends on 3.1

Phase 4 (Adaptive Scaffolding) depends on Phases 2 + 3
  ├── 4.1 independent (model + storage)
  ├── 4.2 depends on 4.1
  └── 4.3 depends on 4.1 + 3.2

Phase 5 (Strengths-Based) depends on Phase 2
  ├── 5.1 depends on 2.1 (check-in infrastructure)
  ├── 5.2 independent
  └── 5.3 depends on 4.1 (competence metrics)
```

---

## File reference index

| File                                         | What it contains                                                      | Phases that modify it              |
| -------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------- |
| `packages/core/models.py`                    | UserProfile (lines 204-252), EnergyConfig (lines 25-91), Task, Sprint | 3.1, 4.1                           |
| `packages/core/agents/focusbuddy.py`         | FocusBuddyAgent (81 lines) — profile-aware focus sessions             | ~~1.1~~, ~~1.6~~, 2.1-2.5, 3.2, 4.2, 5.1   |
| `packages/core/agents/mentor.py`             | MentorAgent (251 lines) — tone/style-aware coaching                   | ~~1.4~~, ~~1.6~~, ~~1.7~~, 3.2-3.4, 4.2, 5.3   |
| `packages/core/agents/guardian.py`           | GuardianAgent (240 lines) — proactive wellness monitor                | ~~1.3~~, ~~1.7~~, 3.2, 4.3, 5.1            |
| `packages/core/agents/chronos.py`            | ChronosAgent (457 lines) — peak-hours-aware scheduler                 | ~~1.2~~, ~~1.6~~                           |
| `packages/core/agents/planner.py`            | PlannerAgent (386 lines) — decision-fatigue-aware planning            | ~~1.5~~, 4.2, 5.2                      |
| `packages/core/agents/scribe.py`             | ScribeAgent (48 lines) — persistence                                  | 2.4, 5.2                           |
| `packages/core/agents/liaison.py`            | LiaisonAgent (1003 lines) — communication                             | (reads `deadline_at_risk` already) |
| `packages/core/collaboration/context.py`     | SharedContext (97 lines) — signals dict                               | 2.2, 3.1, 3.4                      |
| `packages/core/events.py`                    | EventBus, Topics                                                      | 2.1                                |
| `packages/core/capabilities/productivity.py` | `create_schedule()`, `create_focus_sessions()`                        | 1.1, 1.2                           |
| `packages/core/capabilities/wellness.py`     | `motivate()`, `add_wellness_nudges()`                                 | 3.3                                |
| `packages/core/wellness_rules.py`            | Deterministic wellness detection rules (214 lines)                    | 3.2                                |
