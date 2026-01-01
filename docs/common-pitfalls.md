# Common Pitfalls

> Problems that have occurred repeatedly. Check here before debugging.

## 1. KV-Cache Invalidation

**Symptom**: High API costs, slow responses

**Cause**: Dynamic content in system prompt
```python
# BAD - breaks cache every request
time_context = f"Current time: {now.strftime('%H:%M')}"
system_prompt += time_context
```

**Fix**: Put dynamic content in user message, not system prompt
```python
# GOOD - system prompt stays stable
user_message = f"[Time: {now.strftime('%H:%M')}]\n{user_input}"
```

**Files**: `agent/coach.py:280-281`

---

## 2. Model Calculates Time Wrong

**Symptom**: User says "30 min", model asks "done?" after 10 min

**Cause**: Expecting model to:
1. Find when user said duration
2. Parse the duration
3. Calculate deadline
4. Compare to current time

Models are bad at multi-step math.

**Fix**: Pre-compute in code, give model the conclusion
```python
# Code calculates
if state.working_until and now < state.working_until:
    context += "USER IS WORKING. DO NOT MESSAGE."
```

**Files**: `bot/scheduler.py` (needs implementation)

---

## 3. Model Outputs Timestamps

**Symptom**: Response includes `[23:31] done yet?` instead of just `done yet?`

**Cause**: History messages have `[HH:MM]` prefix, model mimics format

**Current mitigation**:
```python
final_text = re.sub(r'^\s*(\[\d{1,2}:\d{2}\]\s*)+', '', final_text)
```

**Gap**: Only strips from start, not mid-message

**Files**: `agent/coach.py:341`, `agent/coach.py:400`

---

## 4. Model Says "updated" Without Tool Call

**Symptom**: Model says "k updated" but data not saved

**Cause**: Model generates acknowledgment without actually calling `write_think_os`

**Fix needed**: Validate tool calls against response claims
```python
if "updated" in response and not wrote_this_turn:
    logger.warning("Model lied about updating")
    # retry or modify response
```

**Files**: `agent/coach.py` (needs implementation)

---

## 5. Message Bombing

**Symptom**: User receives 8 separate Telegram messages in rapid succession

**Cause**:
1. Model outputs many short lines
2. Code splits on `\n` and sends each as message
3. `protocol.md` says "Each thought on its own line"

**Fix options**:
- Post-process to merge short lines
- Change protocol.md guidance
- Limit max messages per response

**Files**: `bot/telegram.py:176-186`, `main.py:46-56`

---

## 6. Orchestrator Sends While User Typing

**Symptom**: User typing, Spark sends nudge mid-typing

**Current mitigation**:
- `_user_interacting` flag set on message receive
- Orchestrator checks flag before sending

**Gap**: Flag only set when message received, not when user starts typing

**Files**: `bot/telegram.py:38-40`, `bot/scheduler.py:429-431`

---

## 7. Prompt Rules Ignored

**Symptom**: Added rule to prompt, model still does the thing

**Cause**:
- Prompt too long, model ignores parts
- Rule conflicts with another rule
- Model follows examples over rules

**Fix**:
- Examples > rules
- Keep prompts short
- Code-level enforcement for critical behaviors

---

## 8. Style Definitions Scattered

**Symptom**: Inconsistent behavior, hard to change personality

**Cause**: Style defined in 4 places:
1. `protocol.md`
2. `scheduler.py` ORCHESTRATOR_PROMPT
3. `scheduler.py` style_boost
4. `coach.py` style_boost

**Fix**: Single source of truth in `protocol.md`, others only reference

**Files**: All prompt-containing files

---

## 9. DeepSeek-Specific Quirks

**Symptom**: Works with Anthropic, breaks with DeepSeek

**Known issues**:
- More likely to output timestamps
- More verbose responses
- Needs explicit "don't do X" rules
- May output chain-of-thought

**Current mitigation**: `style_boost` per provider

**Files**: `bot/scheduler.py:37-122`, `agent/coach.py:21-148`

---

## 10. State Not Persisted

**Symptom**: Bot forgets context after restart

**Cause**: Some state only in memory:
- `coach.history` - resets on restart
- `_user_interacting` - resets on restart

**Persisted state**: `memory/spark/state.json`

**Files**: `agent/state.py`, `agent/coach.py:198-199`

---

## Checklist When Adding Features

- [ ] Does it add dynamic content to system prompt? → Move to user message
- [ ] Does it require model to calculate? → Pre-compute in code
- [ ] Does it add a new rule? → Consider example instead
- [ ] Does it affect message format? → Test with \n splitting
- [ ] Does it need to persist? → Add to SessionState
- [ ] Does it work with both providers? → Test DeepSeek too
