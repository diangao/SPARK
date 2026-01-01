# Context Engineering Improvements

> Logged: 2024-12-31
> Status: Planning

## Background

Current prompts contain many "patch" rules to fix model behavior issues. These patches work but violate context engineering best practices:

1. **KV-Cache**: Dynamic content in system prompt breaks cache
2. **Prompt bloat**: Rules stack up, model ignores some
3. **Wrong layer**: Logic problems solved with prompts instead of code

## Guiding Principles (from Manus blog)

| Principle | Description |
|-----------|-------------|
| KV-Cache | Keep prefix stable, append-only, 10x cost difference |
| External Context | Use file system as storage, context holds pointers |
| Attention Control | Repeat goals at end of context (lost-in-middle) |
| Preserve Errors | Keep failure traces for learning |
| Avoid Overfitting | Vary examples, don't use fixed templates |

---

## Problems & Solutions

### Problem 1: Model doesn't respect user's time commitment

**Symptom**: User says "30 min", model asks "done yet?" 10 min later

**Current patch** (scheduler.py lines 46-65):
```
USER'S TIME COMMITMENT = SACRED (MOST CRITICAL)
When user says a DURATION like "30 min"...
```
~20 lines of rules + examples

**Better approach**: Pre-compute deadline in code
```python
# In _load_context() or state management
if state.working_until:
    deadline = datetime.fromisoformat(state.working_until)
    if now < deadline:
        minutes_left = (deadline - now).total_seconds() / 60
        # Give model a conclusion, not data to reason about
        sections.append(f"USER IS WORKING. Deadline: {deadline.strftime('%H:%M')} ({minutes_left:.0f} min left). DO NOT MESSAGE.")
```

**Implementation**:
- [ ] Add `working_until: str | None` to SessionState
- [ ] Parse "30 min", "1 hour" from user messages → set deadline
- [ ] In orchestrator context, show computed deadline status
- [ ] Can even skip orchestrator_tick entirely if before deadline

---

### Problem 2: Model sends message right after previous one

**Symptom**: Spark sends, then 2 min later sends again

**Current patch** (scheduler.py lines 38-44):
```
RECENT RESPONSE AWARENESS (CRITICAL)
If you (Spark) just responded < 3 min ago → should_message: false
```

**Better approach**: Code-level guard, don't even call model
```python
# At start of orchestrator_tick()
if state.last_spark_message:
    since = (now - datetime.fromisoformat(state.last_spark_message)).total_seconds() / 60
    if since < 5:
        logger.info(f"Orchestrator skipped: sent {since:.0f} min ago")
        return  # Don't call model at all
```

**Implementation**:
- [ ] Track `last_spark_message` timestamp in state
- [ ] Add early return in `orchestrator_tick()` if < 5 min since last message
- [ ] Remove the prompt patch once code guard is in place

---

### Problem 3: Model outputs [HH:MM] timestamps

**Symptom**: Model outputs `[23:31] done yet?` instead of just `done yet?`

**Current patch** (coach.py lines 26-31):
```
NEVER include [HH:MM] in your output. Just write your message normally.
- BAD: "[23:31] done yet"
- GOOD: "done yet?"
```

**Current mitigation** (coach.py line 341):
```python
final_text = re.sub(r'^\s*(\[\d{1,2}:\d{2}\]\s*)+', '', final_text)
```

**Better approach**: Strengthen post-processing
```python
# More aggressive stripping - remove [HH:MM] anywhere, not just start
final_text = re.sub(r'\[\d{1,2}:\d{2}\]\s*', '', final_text)
```

**Implementation**:
- [ ] Expand regex to catch mid-message timestamps
- [ ] Can reduce/remove prompt patch once post-process is robust

---

### Problem 4: Model says "updated" but doesn't call write_think_os

**Symptom**: Model responds "k updated" but never called the tool

**Current patch** (coach.py lines 39-65):
```
WARNING: If you say "updated" or "noted" WITHOUT calling write_think_os, YOU ARE LYING.
```

**Better approach**: Output validation
```python
# After getting final response, before returning
acknowledgment_words = ["updated", "noted", "saved", "recorded", "logged"]
if any(word in final_text.lower() for word in acknowledgment_words):
    # Check if write_think_os was called in this turn
    if not self._wrote_this_turn:
        logger.warning("Model claimed to write but didn't call tool")
        # Option 1: Retry with stronger prompt
        # Option 2: Auto-append a write call
        # Option 3: Modify response to remove false claim
```

**Implementation**:
- [ ] Track tool calls per turn
- [ ] Validate claims match actions
- [ ] Decide on remediation strategy (retry vs modify vs warn)

---

### Problem 5: Model copy-pastes file content

**Symptom**:
```
sf mission: build connections
contribution need = 0
self-worth tied to what u produce
```

**Current patch** (scheduler.py lines 101-121):
```
"Reference their context" means USE the info to CRAFT your message, NOT copy-paste
BAD (copying file content): ...
GOOD (using info to craft): ...
```

**Better approach**:
1. **Examples with variation** in protocol.md (not fixed BAD/GOOD)
2. **Post-process detection**:
```python
# Detect likely copy-paste patterns
def looks_like_file_content(text: str) -> bool:
    lines = text.strip().split('\n')
    # Multiple short lines with colons or equals
    suspicious = sum(1 for l in lines if ':' in l or '=' in l)
    return suspicious >= 2 and len(lines) >= 3

if looks_like_file_content(final_text):
    logger.warning("Output looks like copy-pasted file content")
    # Could retry or filter
```

**Implementation**:
- [ ] Add heuristic detection function
- [ ] Decide on action: log, retry, or filter
- [ ] Move examples to protocol.md with variation

---

### Problem 6: Model outputs chain-of-thought

**Symptom**:
```
[20:45] 19 min
[20:46] 18 min
[20:47] 17 min
deadline 21:04
```

**Current patch** (coach.py lines 99-121):
```
Your output should be SHORT, CONVERSATIONAL messages. NOT:
- Internal reasoning or chain-of-thought
- Countdown timers...
```

**Better approach**:
1. **Structured output** - Use JSON mode for orchestrator
2. **Post-process** - If output > N lines, truncate or extract last part

```python
# For coach responses
lines = final_text.strip().split('\n')
if len(lines) > 5:
    # Likely includes reasoning, take last few lines
    final_text = '\n'.join(lines[-3:])
    logger.info("Truncated verbose response")
```

**Implementation**:
- [ ] Add line count check
- [ ] Experiment with JSON mode for DeepSeek
- [ ] Consider system prompt structure changes

---

### Problem 7: Model doesn't celebrate wins

**Symptom**: User finishes all Top 3, model immediately asks "what's next"

**Current patch** (coach.py lines 123-147):
```
CELEBRATE WINS (LFG VIBE)
When user completes tasks, ESPECIALLY all top 3:
- CELEBRATE FIRST before asking what's next
```

**Better approach**: State-driven context
```python
# In state management, detect completion
if state.top_3_completed_count == 3 and not state.celebrated_today:
    # Add explicit instruction to context
    context += "\n\n🎉 USER JUST COMPLETED ALL TOP 3! CELEBRATE THIS WIN FIRST."
```

**Implementation**:
- [ ] Track task completion in state
- [ ] Add celebration flag to prevent repeat
- [ ] Inject celebration prompt only when relevant

---

## Architecture Improvements

### KV-Cache Optimization

**Current** (breaks cache):
```python
# coach.py line 280-281
time_context = f"\n\n---\nCurrent time: {now.strftime('%H:%M')}..."
system_prompt += time_context  # Dynamic content in system prompt
```

**Better**:
```python
# Keep system_prompt stable
# Put dynamic content in user message
user_message = f"""
Current time: {now.strftime('%H:%M')}
Today: {now.strftime('%Y-%m-%d')}

User message: {user_message}
"""
```

**Impact**: ~10x cost reduction on cached tokens

---

### Single Source of Truth for Style

**Current**: Style defined in 4 places
- protocol.md
- scheduler.py ORCHESTRATOR_PROMPT
- scheduler.py style_boost
- coach.py style_boost

**Better**:
- protocol.md = personality + style (single source)
- scheduler.py = decision logic only
- coach.py = tool usage only

Both read protocol.md, don't duplicate style rules.

---

### Goal Reminder (Attention Control)

Add Top 3 reminder at end of context to prevent lost-in-middle:

```python
# At end of _load_context()
if state.top_3:
    sections.append(f"""
---
REMEMBER - User's Top 3 today:
1. {state.top_3[0]}
2. {state.top_3[1]}
3. {state.top_3[2]}

Your job: help them finish these.
""")
```

---

## Priority Order

| # | Problem | Effort | Impact | Approach |
|---|---------|--------|--------|----------|
| 1 | Time commitment | Medium | High | Code pre-compute |
| 2 | Message frequency | Low | High | Code guard |
| 3 | Timestamp output | Low | Medium | Strengthen post-process |
| 4 | KV-Cache | Medium | High | Move time to user msg |
| 5 | Tool validation | Medium | Medium | Output validation |
| 6 | Copy-paste | Medium | Medium | Detection + examples |
| 7 | Chain-of-thought | Low | Medium | Line truncation |
| 8 | Celebrate wins | Low | Low | State-driven prompt |

---

## Notes

- Don't delete prompt patches until code solutions are validated
- Some prompts may still be needed for edge cases
- Test with both Anthropic and DeepSeek models
- Monitor logs to verify improvements
