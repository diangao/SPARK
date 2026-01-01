# Codebase Context Summary

> Generated: 2024-12-31
> Purpose: Understanding for context engineering improvements

## File Map

```
S.P.A.R.K./
├── main.py                 # Entry point, wires everything together
├── config/
│   └── settings.py         # All env vars and config
├── bot/
│   ├── telegram.py         # User interaction, message handling
│   └── scheduler.py        # Proactive nudging (Orchestrator)
├── agent/
│   ├── coach.py            # Interactive conversation (Coach)
│   ├── state.py            # Session state persistence
│   ├── tools.py            # Think OS read/write tools
│   └── prompts.py          # Command prompts (not analyzed)
└── memory/spark/
    └── state.json          # Persisted state
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│  - Creates Telegram Application                                 │
│  - Creates Scheduler with callbacks                             │
│  - Wires Coach history ↔ Scheduler                              │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────────┐
│      telegram.py        │     │         scheduler.py            │
│  (Reactive - User msg)  │     │    (Proactive - Orchestrator)   │
├─────────────────────────┤     ├─────────────────────────────────┤
│ • Message debouncing    │     │ • Random tick (1-20 min)        │
│ • _user_interacting     │◄───►│ • Checks _user_interacting      │
│ • Calls Coach.chat()    │     │ • Calls LLM to decide nudge     │
│ • Records interaction   │     │ • Uses ORCHESTRATOR_PROMPT      │
└─────────────────────────┘     └─────────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
              ┌─────────────────────────────────┐
              │           coach.py              │
              │     (Conversation Agent)        │
              ├─────────────────────────────────┤
              │ • Loads system prompt           │
              │ • Manages conversation history  │
              │ • Tool loop (read/write)        │
              │ • Provider: Anthropic/DeepSeek  │
              └─────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────────┐
│        tools.py         │     │          state.py               │
│  (Think OS Access)      │     │     (Session Persistence)       │
├─────────────────────────┤     ├─────────────────────────────────┤
│ • read_think_os()       │     │ • SessionState dataclass        │
│ • write_think_os()      │     │ • load_state() / save_state()   │
│ • get_current_time()    │     │ • Stored in Think OS            │
│ • Access control lists  │     │                                 │
└─────────────────────────┘     └─────────────────────────────────┘
```

## Data Flow

### Flow 1: User Message → Coach Response

```
User sends message
    ↓
telegram.handle_message()
    ├── Sets _user_interacting = True (prevents orchestrator)
    ├── Buffers message (4s debounce)
    └── After debounce:
            ↓
        _process_buffered_messages()
            ↓
        coach.chat(combined_text)
            ├── _load_system_prompt()
            │       ├── Reads protocol.md (cached)
            │       ├── Reads profile.md (cached)
            │       └── Reads learned.md (every time)
            ├── Adds time_context to system prompt ← BREAKS KV-CACHE
            ├── Appends user msg to history with [HH:MM]
            └── Tool loop until final response
                    ↓
        Split response on \n, send each as message
            ↓
        scheduler.record_interaction()
            └── Updates state: last_interaction=now, unanswered_count=0
```

### Flow 2: Orchestrator Tick → Proactive Nudge

```
APScheduler triggers orchestrator_tick()
    ↓
Check guards:
    ├── Quiet hours? → skip
    ├── _user_interacting? → skip
    └── Continue
        ↓
_load_context()
    ├── Get conversation history from coach
    ├── Load state (unanswered_count, last_interaction)
    ├── Format context string with:
    │       ├── User info (name, pronouns, guilt level)
    │       ├── Recent conversation ← CRITICAL for avoiding repetition
    │       ├── Time info
    │       ├── Last user reply (X min ago)
    │       └── Files to read list
    └── Return context string
        ↓
Format ORCHESTRATOR_PROMPT + style_boost
    ↓
Call LLM (Anthropic or DeepSeek)
    ├── Tool loop: model reads files via read_think_os
    └── Final output: JSON {should_message, hypothesis, message}
        ↓
_handle_orchestrator_decision()
    ├── Parse JSON
    ├── Check _user_interacting again
    └── If should_message:
            ↓
        _send_and_record()
            ├── Send message to Telegram
            ├── Add to coach.history
            └── record_proactive_message()
                    └── unanswered_count += 1
```

## Key State Variables

### SessionState (state.py → state.json)

| Field | Type | Purpose | Updated When |
|-------|------|---------|--------------|
| `last_interaction` | datetime | Last user reply | User sends message |
| `unanswered_count` | int | Proactive msgs without reply | Orchestrator sends |
| `stuck_on` | str? | Task user is stuck on | User says "stuck" |
| `current_focus` | str? | Today's main focus | User sets focus |
| `last_checkin_summary` | str? | Brief summary | After check-in |

**Missing fields (needed for improvements):**
- `working_until: datetime?` - User's stated deadline
- `last_spark_message: datetime?` - When Spark last sent
- `top_3: list[str]?` - Today's top 3 tasks
- `celebrated_today: bool` - Whether we celebrated completion

### Coach State (coach.py)

| Field | Purpose |
|-------|---------|
| `history: list[dict]` | Conversation history (role, content) |
| `_history_date: str` | Tracks which day, resets on new day |
| `_system_prompt: str` | Cached base prompt (protocol + profile) |

### Telegram State (telegram.py)

| Field | Purpose |
|-------|---------|
| `_user_interacting: bool` | Prevents orchestrator during coach processing |
| `_message_buffers: dict` | Per-user message debounce buffers |

## Two Prompt Systems

### 1. Coach System Prompt (coach.py)

```
Base (cached):
├── User info from .env
├── protocol.md content
└── profile.md content

Per-request (breaks cache):
├── learned.md content
├── time_context ← SHOULD MOVE TO USER MESSAGE
└── style_boost (DeepSeek-specific)
```

### 2. Orchestrator Prompt (scheduler.py)

```
Static:
├── ORCHESTRATOR_PROMPT template
└── style_boost (DeepSeek-specific)

Per-request (in user message):
├── Context string from _load_context()
└── File read instructions
```

## Shared Resources

### Conversation History

```
coach.history ←──shared──→ scheduler
                   ↑
         main.py wires this via:
         get_conversation_history=lambda: get_coach().history
         add_to_history=lambda msg: get_coach().history.append(msg)
```

Both coach and orchestrator see the same history.
Orchestrator adds its messages to history so it knows what it already said.

### Think OS Files

| File | Read By | Write By |
|------|---------|----------|
| protocol.md | Coach | - |
| learned.md | Coach | Coach |
| profile.md | Coach, Orchestrator | - |
| daily/*.md | Coach, Orchestrator | Coach |
| state.json | Scheduler | Scheduler |

## Providers & Models

| Component | Provider Setting | Default | Model |
|-----------|------------------|---------|-------|
| Orchestrator | ORCHESTRATOR_PROVIDER | anthropic | claude-3-5-haiku |
| Orchestrator | - | deepseek | deepseek-chat (V3) |
| Coach | COACH_PROVIDER | anthropic | claude-3-5-haiku |
| Coach | - | deepseek | deepseek-chat |

Each provider has different `style_boost` to handle model quirks.

## Boundary Conditions & Edge Cases

### 1. Race Condition: Orchestrator vs User

```
Orchestrator decides to send
    ↓
User starts typing (sets _user_interacting = True)
    ↓
Orchestrator checks _user_interacting again before send
    ↓
If True → cancels send
```

Current mitigation: Double-check `_user_interacting` before sending.
Gap: No check between decision and tool reads.

### 2. Message Format Variance

Coach splits on `\n` and sends each line as separate Telegram message.
This amplifies any formatting issues (e.g., model outputs 10 short lines = 10 messages).

### 3. History Accumulation

History grows throughout the day, only resets on new day.
Long history = more tokens = higher cost + slower response.
No summarization or truncation currently.

### 4. Timestamp Handling

Messages in history have `[HH:MM]` prefix.
Model sometimes outputs `[HH:MM]` in response (mimicking input format).
Current fix: regex strip `^\s*(\[\d{1,2}:\d{2}\]\s*)+`
Gap: Doesn't catch mid-message timestamps.

### 5. State File Location

State lives in Think OS (`memory/spark/state.json`), not local.
If Think OS path changes or file is deleted, state resets.

### 6. Quiet Hours Calculation

```python
if QUIET_START > QUIET_END:  # e.g., 23 to 8 (overnight)
    in_quiet = current_hour >= QUIET_START or current_hour < QUIET_END
else:  # e.g., 1 to 6
    in_quiet = QUIET_START <= current_hour < QUIET_END
```

Handles overnight quiet periods correctly.

### 7. DeepSeek vs Anthropic Differences

| Behavior | DeepSeek | Anthropic |
|----------|----------|-----------|
| Timestamp output | Common problem | Rare |
| Tool call format | OpenAI style | Anthropic style |
| Following instructions | Needs more explicit rules | Better at inference |
| Message format | Tends to be verbose | More concise |

This is why `style_boost` exists per provider.

## Files Needing Modification

For context engineering improvements:

| File | Changes Needed |
|------|----------------|
| `agent/state.py` | Add `working_until`, `last_spark_message`, `top_3`, `celebrated_today` |
| `bot/scheduler.py` | Pre-compute deadline status, add frequency guard |
| `agent/coach.py` | Move time_context to user message, tool call validation |
| `config/settings.py` | (none expected) |
| `bot/telegram.py` | Parse duration from user message, update state |

## Common Pitfalls

> To be extracted to `docs/common-pitfalls.md`

1. **Adding dynamic content to system prompt** → Breaks KV-cache
2. **Relying on model to calculate time** → Models bad at math
3. **Rules instead of examples** → Overfitting or ignoring
4. **No output validation** → Model lies about tool calls
5. **Splitting on \n for messages** → Amplifies formatting bugs
