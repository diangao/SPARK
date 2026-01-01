"""Scheduler for proactive messages and orchestrator checks."""

import json
import logging
import random
import re
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from anthropic import Anthropic
from openai import OpenAI

from config.settings import (
    ANTHROPIC_API_KEY, TEST_MODE,
    USER_NAME, USER_PRONOUNS, GUILT_LEVEL, SPARK_STYLE,
    TICK_MIN_MINUTES, TICK_MAX_MINUTES,
    ORCHESTRATOR_PROVIDER, DEEPSEEK_API_KEY,
    QUIET_START, QUIET_END,
)
from agent.tools import read_think_os, get_current_time, TOOL_DEFINITIONS, execute_tool
from agent.state import load_state, update_state, SessionState

logger = logging.getLogger(__name__)


def parse_duration_minutes(text: str) -> int | None:
    """Parse duration from user message. Returns minutes or None.

    Examples:
    - "30 min" -> 30
    - "1 hour" -> 60
    - "2 hours" -> 120
    - "15 minutes" -> 15
    - "1.5 hours" -> 90
    """
    text = text.lower()

    # Pattern: N hour(s)
    hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hr)s?', text)
    if hour_match:
        hours = float(hour_match.group(1))
        return int(hours * 60)

    # Pattern: N min(ute)(s)
    min_match = re.search(r'(\d+)\s*(?:min(?:ute)?s?)', text)
    if min_match:
        return int(min_match.group(1))

    return None

# Model configs per provider
PROVIDER_CONFIGS = {
    "anthropic": {
        "model": "claude-3-5-haiku-20241022",
        "format_hint": "CRITICAL: message must be a STRING with \\n for line breaks, NOT an array.",
        "style_boost": "",
    },
    "deepseek": {
        "model": "deepseek-chat",  # DeepSeek V3
        "format_hint": "",  # DeepSeek follows format well
        # Minimal model-specific patches. Style is in protocol.md.
        # Code handles: message frequency, time commitment, timestamp stripping
        "style_boost": """
## DeepSeek-specific

NEVER CHALLENGE THEIR TOP 3. Help them complete, don't judge their choices.

SAVAGE = intensity when you guilt trip, NOT frequency of interruption.

USE their context to craft messages. Don't copy-paste from files.
""",
    },
}

def get_orchestrator_config() -> dict:
    """Get config for current provider."""
    return PROVIDER_CONFIGS.get(ORCHESTRATOR_PROVIDER, PROVIDER_CONFIGS["anthropic"])

def get_format_hint() -> str:
    """Get format hint based on provider."""
    return get_orchestrator_config().get("format_hint", "")

def get_style_boost() -> str:
    """Get style boost based on provider."""
    return get_orchestrator_config().get("style_boost", "")


def convert_tools_to_openai(anthropic_tools: list) -> list:
    """Convert Anthropic tool definitions to OpenAI format."""
    openai_tools = []
    for tool in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
        })
    return openai_tools


# TEST_MODE uses same prompt as production now
ORCHESTRATOR_PROMPT_TEST = None  # Will fall back to ORCHESTRATOR_PROMPT

ORCHESTRATOR_PROMPT = """You're Spark - the accountability friend who actually knows this person.

## YOUR TOOLS

You have access to `read_think_os` to read files. USE IT. Don't guess - actually read.

**Files you MUST read before deciding:**
- `memory/{{user_name}}.md` - WHO THEY ARE. Their patterns, values, guilt triggers. READ THIS CAREFULLY.
- `memory/spark/protocol.md` - Your personality
- `memory/spark/learned.md` - What you've learned about them

**Files you SHOULD read:**
- `memory/timeline/daily/{{today}}.md` - What they planned today
- `memory/timeline/daily/{{yesterday}}.md` - What happened yesterday
- `memory/timeline/perspective.md` - Their goals/values

**IMPORTANT: Conversation > Files**
If they mentioned changing plans in the recent conversation, TRUST THE CONVERSATION over what's in the files. Files may be outdated. What they JUST SAID takes priority.

## STEP 1: Theory of Mind - INFER before you act

Before deciding anything, put yourself in their shoes. You have context about:
- Who they are (profile, patterns, what they care about)
- What time it is right now
- What they were working on / said before going silent
- How long they've been silent
- Their goals and what they're trying to accomplish

Use ALL of this to form a hypothesis about what's happening:

**Ask yourself:**
- Given everything I know about this person, what are they probably doing right now?
- Why might they not be responding?
- What would a friend who actually knows them think?

**Possible states** (not exhaustive, use your judgment):
- sleeping / winding down
- in flow / deep work (don't interrupt!)
- busy with something (meetings, life, etc.)
- probably slacking / distracted
- stuck and maybe needs help
- unclear - need more info

The key is: don't just react to "X minutes of silence". Think about WHY.

**Time reasoning**: Raw silence time ≠ meaningful silence time. Factor in sleep, normal life patterns. Your message should reflect reality, not raw numbers.

## STEP 2: Check what you've already said

Read "Recent conversation (today)" CAREFULLY.
- What exact messages did you already send?
- What topics/angles did you already try?
- NEVER repeat the same message or same angle twice

If you said "bruhh" → don't say "bruhh" again
If you asked about task X → don't ask about X again
If you guilt tripped about time → try a different angle

## STEP 3: Decide based on your inference

Your action should match your hypothesis:
- If they're doing something important → don't interrupt
- If they're probably slacking → hold them accountable (that's your job)
- If they might be stuck → check in helpfully, not guilt-trippy
- If you're not sure → gentle check is better than aggressive assumption

Trust your read of the situation. You know this person.

## When it's guilt trip time - BE MEAN

If your read is "slacking" → don't hold back. You're the friend who says what others won't.

You have ammunition:
- Their goals and what they said they wanted (perspective.md)
- What they were supposed to do today (daily file)
- Who they are and their patterns (profile) ← this has the BEST stuff. personality, values, what they care about, their patterns. use it.
- What they literally just told you (recent conversation)

Use ALL of it. Get creative. Get personal. Make it hurt. Don't just repeat the same few angles - dig into the profile for details that will actually hit.

The vibe is: disappointed friend who knows you too well, not generic bot.
Each guilt trip should be unique and hit different.
The longer they ghost, the more savage you can get.

You're not being mean to be mean. You're being mean because this is what works on them.

## Style
Follow the style in protocol.md. Key points:
- {style_instruction}
- Text like a real friend, not a bot
- Reference their specific context

## Output format

Think out loud using this framework, then give JSON:

```
1. SITUATION: [time, what they were doing, how long silent, what's your read]

2. DEADLINE CHECK: [scan conversation for any agreed deadline like "check in at X" or "done by X". If found: what time? Is current time BEFORE or AFTER? If BEFORE deadline → should_message: false]

3. PROFILE SCAN: [scan their profile - what patterns reveal what they care about? what drives them? what makes them feel guilty? what are their stated values vs current behavior?]

4. ANGLES ALREADY USED: [list the specific angles/themes from my recent messages above. be specific about what you already said.]

5. FRESH ANGLE: [pick something I HAVEN'T hit yet from the profile. find patterns, values, guilt triggers in their profile and use them. what's a NEW angle that would hit hard?]

6. DECISION: [should I message? what's my approach?]

{{"should_message": true/false, "hypothesis": "your read on their state", "message": "your message or null"}}
```

{format_hint}
"""


class Scheduler:
    """Manages scheduled tasks and proactive messaging."""

    def __init__(self, send_message_callback, get_conversation_history=None, add_to_history=None):
        """
        Args:
            send_message_callback: Async function to send Telegram message.
            get_conversation_history: Function to get recent conversation history.
            add_to_history: Function to add a message to conversation history.
        """
        self.send_message = send_message_callback
        self.get_history = get_conversation_history
        self.add_to_history = add_to_history
        self.scheduler = AsyncIOScheduler()
        self.state: SessionState | None = None  # Loaded on first use

        # Initialize clients based on provider
        self.anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        ) if DEEPSEEK_API_KEY else None

        self.provider = ORCHESTRATOR_PROVIDER
        logger.info(f"Orchestrator provider: {self.provider}")

    async def _ensure_state(self, force_reload: bool = False) -> SessionState:
        """Load state, optionally forcing a reload from disk."""
        if self.state is None or force_reload:
            self.state = await load_state()
            logger.info(f"Loaded session state: unanswered={self.state.unanswered_count}")
        return self.state

    async def record_interaction(self, summary: str | None = None) -> None:
        """Record that a user interaction just happened."""
        await self._ensure_state()
        self.state = await update_state(
            last_interaction=datetime.now().isoformat(),
            unanswered_count=0,
            last_checkin_summary=summary,
        )

    async def record_proactive_message(self) -> None:
        """Record that we sent a proactive message.

        Note: Does NOT update last_interaction - that only tracks user replies.
        This way Spark can keep nudging if user doesn't reply.
        """
        await self._ensure_state()
        self.state = await update_state(
            unanswered_count=self.state.unanswered_count + 1,
            last_spark_message=datetime.now().isoformat(),
        )

    async def record_stuck(self, task: str) -> None:
        """Record that user is stuck on a task."""
        await self._ensure_state()
        self.state = await update_state(stuck_on=task)

    async def clear_stuck(self) -> None:
        """Clear stuck status."""
        await self._ensure_state()
        self.state = await update_state(stuck_on=None)

    async def set_working_deadline(self, minutes: int) -> None:
        """Set a working deadline X minutes from now.

        While deadline is active, orchestrator won't send proactive messages.
        """
        deadline = datetime.now() + timedelta(minutes=minutes)
        await self._ensure_state()
        self.state = await update_state(working_until=deadline.isoformat())
        logger.info(f"Working deadline set: {deadline.strftime('%H:%M')} ({minutes} min from now)")

    async def check_and_set_working_deadline(self, user_message: str) -> None:
        """Check user message for duration and set deadline if found."""
        minutes = parse_duration_minutes(user_message)
        if minutes and minutes >= 5:  # Only set for meaningful durations
            await self.set_working_deadline(minutes)

    async def _load_context(self, recent_messages: list[dict] | None = None) -> str:
        """Load MINIMAL context for orchestrator. It will read files itself via tools."""
        sections = []
        now = datetime.now()
        time_info = get_current_time()
        # Always reload state from disk to get latest unanswered_count
        state = await self._ensure_state(force_reload=True)

        # 0. User info
        user_info = []
        if USER_NAME:
            user_info.append(f"Name: {USER_NAME}")
        if USER_PRONOUNS:
            user_info.append(f"Pronouns: {USER_PRONOUNS}")
        if GUILT_LEVEL:
            guilt_note = {"chill": "go easy on them", "medium": "normal guilt trips", "savage": "be SAVAGE. max guilt. no mercy."}.get(GUILT_LEVEL, GUILT_LEVEL)
            user_info.append(f"Guilt level: {guilt_note}")
        if user_info:
            sections.append(f"User: {', '.join(user_info)}")

        # 1. Recent conversation (CRITICAL for avoiding repetition)
        if recent_messages:
            def format_msg(m):
                if m['role'] == 'assistant':
                    return f"- Spark: {m['content']}"
                else:
                    name = USER_NAME or "User"
                    return f"- {name}: {m['content']}"
            convo = "\n".join([format_msg(m) for m in recent_messages])
            sections.append(f"Recent conversation (today) - CHECK THIS TO AVOID REPEATING YOURSELF:\n{convo}")
        else:
            sections.append("Recent conversation: None yet today")

        # 2. Essential metadata
        sections.append(f"Current time: {time_info['datetime']} ({time_info['weekday']})")
        sections.append(f"Today's date: {time_info['date']}")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        sections.append(f"Yesterday's date: {yesterday}")

        if state.last_interaction:
            last = datetime.fromisoformat(state.last_interaction)
            delta = now - last
            minutes = delta.total_seconds() / 60
            sections.append(f"Last user reply: {minutes:.0f} min ago")
        else:
            sections.append("Last user reply: None (never replied)")

        sections.append(f"Unanswered proactive messages: {state.unanswered_count}")

        if state.stuck_on:
            sections.append(f"User previously stuck on: {state.stuck_on}")

        if state.current_focus:
            sections.append(f"Today's focus: {state.current_focus}")

        # 3. Tell it what files to read
        sections.append(f"""
FILES TO READ (use read_think_os tool):
- memory/{USER_NAME}.md ← MUST READ. Their profile, patterns, guilt triggers.
- memory/spark/protocol.md ← Your personality
- memory/spark/learned.md ← What you've learned
- memory/timeline/daily/{time_info['date']}.md ← Today's plan
- memory/timeline/daily/{yesterday}.md ← Yesterday
- memory/timeline/perspective.md ← Their goals
""")

        return "\n\n".join(sections)

    async def orchestrator_tick(self) -> None:
        """Called periodically to decide if we should send a proactive message."""
        # Check which client to use
        if self.provider == "deepseek":
            if not self.deepseek_client:
                logger.warning("Orchestrator: No DeepSeek API key configured")
                return
        else:
            if not self.anthropic_client:
                logger.warning("Orchestrator: No Anthropic API key configured")
                return

        # Check quiet hours
        current_hour = datetime.now().hour
        if QUIET_START > QUIET_END:  # e.g., 23 to 8 (overnight)
            in_quiet = current_hour >= QUIET_START or current_hour < QUIET_END
        else:  # e.g., 1 to 6
            in_quiet = QUIET_START <= current_hour < QUIET_END
        if in_quiet:
            logger.info(f"Orchestrator tick skipped: quiet hours ({QUIET_START}:00-{QUIET_END}:00)")
            return

        # Check EARLY if user is interacting - skip entire tick if so
        from bot.telegram import is_user_interacting
        if is_user_interacting():
            logger.info("Orchestrator tick skipped: user is interacting")
            return

        # Message frequency guard - don't call LLM if we just sent a message
        # (disabled in TEST_MODE for faster iteration)
        state = await self._ensure_state(force_reload=True)
        if not TEST_MODE and state.last_spark_message:
            since = (datetime.now() - datetime.fromisoformat(state.last_spark_message)).total_seconds() / 60
            if since < 5:
                logger.info(f"Orchestrator tick skipped: sent message {since:.0f} min ago (< 5 min)")
                return

        # Working deadline guard - user said "30 min" etc, respect their time
        now = datetime.now()
        if state.working_until:
            deadline = datetime.fromisoformat(state.working_until)
            if now < deadline:
                minutes_left = (deadline - now).total_seconds() / 60
                logger.info(f"Orchestrator tick skipped: user working until {deadline.strftime('%H:%M')} ({minutes_left:.0f} min left)")
                return
            else:
                # Deadline passed, clear it
                logger.info(f"Working deadline {deadline.strftime('%H:%M')} has passed, clearing")
                self.state = await update_state(working_until=None)

        logger.info(f"Orchestrator tick ({self.provider})...")

        try:
            # Get recent conversation if available
            recent = self.get_history() if self.get_history else None
            logger.info(f"Orchestrator history ({len(recent) if recent else 0} messages):")
            if recent:
                for i, msg in enumerate(recent[-10:]):  # Last 10 messages
                    content_preview = msg['content'][:100].replace('\n', '\\n')
                    logger.info(f"  [{i}] {msg['role']}: {content_preview}...")
            context = await self._load_context(recent)

            # Format prompt with style instruction and model-specific hints
            style_instruction = SPARK_STYLE if SPARK_STYLE else "Text like a friend who roasts. Mean, direct, no filter."
            format_hint = get_format_hint()
            style_boost = get_style_boost()
            prompt = ORCHESTRATOR_PROMPT.format(style_instruction=style_instruction, format_hint=format_hint)
            # Add style boost for providers that need it (e.g., DeepSeek savage mode)
            if style_boost:
                prompt = prompt + "\n" + style_boost

            user_message = f"Context:\n\n{context}\n\nFirst, use read_think_os to read the profile and other relevant files. Then decide if you should send a message."

            # Route to appropriate provider
            if self.provider == "deepseek":
                await self._orchestrator_tick_deepseek(prompt, user_message)
            else:
                await self._orchestrator_tick_anthropic(prompt, user_message)

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)

    async def _orchestrator_tick_anthropic(self, system_prompt: str, user_message: str) -> None:
        """Run orchestrator tick using Anthropic API."""
        config = get_orchestrator_config()
        messages = [{"role": "user", "content": user_message}]

        max_turns = 10
        for turn in range(max_turns):
            response = self.anthropic_client.messages.create(
                model=config["model"],
                max_tokens=2048,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages
            )

            logger.info(f"Anthropic turn {turn + 1}, stop_reason: {response.stop_reason}")

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        logger.info(f"Tool: {tool_name}({json.dumps(tool_input)})")
                        result = await execute_tool(tool_name, tool_input)
                        logger.info(f"Tool result: {len(json.dumps(result))} chars")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
            else:
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                text = text.strip()

                logger.info(f"Orchestrator decision:\n{text}")
                await self._handle_orchestrator_decision(text)
                break

    async def _orchestrator_tick_deepseek(self, system_prompt: str, user_message: str) -> None:
        """Run orchestrator tick using DeepSeek API (OpenAI-compatible)."""
        config = get_orchestrator_config()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        openai_tools = convert_tools_to_openai(TOOL_DEFINITIONS)

        max_turns = 10
        for turn in range(max_turns):
            response = self.deepseek_client.chat.completions.create(
                model=config["model"],
                max_tokens=2048,
                messages=messages,
                tools=openai_tools,
            )

            choice = response.choices[0]
            logger.info(f"DeepSeek turn {turn + 1}, finish_reason: {choice.finish_reason}")

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                # Execute tool calls
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_input = json.loads(tool_call.function.arguments)

                    logger.info(f"Tool: {tool_name}({json.dumps(tool_input)})")
                    result = await execute_tool(tool_name, tool_input)
                    logger.info(f"Tool result: {len(json.dumps(result))} chars")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    })
            else:
                text = choice.message.content or ""
                text = text.strip()

                logger.info(f"Orchestrator decision:\n{text}")
                await self._handle_orchestrator_decision(text)
                break

    async def _handle_orchestrator_decision(self, text: str) -> None:
        """Parse and act on orchestrator's final decision."""
        try:
            # Find JSON block - look for ```json or just find balanced braces containing should_message
            json_text = None

            # Try to find ```json block first
            json_block_start = text.find('```json')
            if json_block_start != -1:
                # Find the { after ```json
                brace_start = text.find('{', json_block_start)
                if brace_start != -1:
                    # Find matching closing brace
                    brace_count = 0
                    for i, char in enumerate(text[brace_start:]):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_text = text[brace_start:brace_start + i + 1]
                                break

            if not json_text:
                # Find any { that's followed by should_message (with possible whitespace)
                match = re.search(r'\{[^{}]*"should_message"', text)
                if match:
                    json_start = match.start()
                    # Find matching closing brace
                    brace_count = 0
                    json_end = json_start
                    for i, char in enumerate(text[json_start:]):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = json_start + i + 1
                                break
                    json_text = text[json_start:json_end]

            if not json_text:
                logger.warning(f"No JSON found in orchestrator response")
                return

            decision = json.loads(json_text)

            if decision.get("should_message") and decision.get("message"):
                # Check if user started interacting while we were thinking
                from bot.telegram import is_user_interacting
                if is_user_interacting():
                    logger.info("Orchestrator: user is interacting, skipping send")
                    return

                hypothesis = decision.get("hypothesis", "unknown")
                msg = decision["message"]
                # Handle Haiku returning message as array instead of string
                if isinstance(msg, list):
                    msg = "\n".join(msg)
                logger.info(f"Orchestrator sending ({hypothesis}): {msg[:100]}...")

                await self._send_and_record(msg)
            else:
                logger.info(f"Orchestrator silent: {decision.get('hypothesis', 'no hypothesis')}")

        except json.JSONDecodeError:
            logger.warning(f"Orchestrator returned non-JSON: {text[:100]}")

    async def _send_and_record(self, msg: str) -> None:
        """Send message and record it."""
        await self.send_message(msg)
        if self.add_to_history:
            timestamp = datetime.now().strftime("%H:%M")
            self.add_to_history({"role": "assistant", "content": f"[{timestamp}] {msg}"})
        await self.record_proactive_message()

    async def morning_startup(self) -> None:
        """Send morning startup message."""
        logger.info("Morning startup triggered")
        await self.send_message(
            "gm, what's on the agenda today?"
        )
        await self.record_proactive_message()

    async def evening_wrapup(self) -> None:
        """Send evening wrapup reminder."""
        logger.info("Evening wrapup triggered")
        await self.send_message(
            "how'd today go?"
        )
        await self.record_proactive_message()

    def _get_random_tick_seconds(self) -> int:
        """Get a random tick interval in seconds."""
        min_sec = int(TICK_MIN_MINUTES * 60)
        max_sec = int(TICK_MAX_MINUTES * 60)
        return random.randint(min_sec, max_sec)

    def _schedule_next_tick(self) -> None:
        """Schedule the next orchestrator tick with a random delay."""
        delay_seconds = self._get_random_tick_seconds()
        next_run = datetime.now() + timedelta(seconds=delay_seconds)

        self.scheduler.add_job(
            self._tick_and_reschedule,
            DateTrigger(run_date=next_run),
            id="orchestrator_tick",
            replace_existing=True,
            misfire_grace_time=None  # Always run, even if late
        )

        if TEST_MODE:
            logger.info(f"Next tick in {delay_seconds}sec")
        else:
            logger.info(f"Next tick in {delay_seconds // 60}min")

    async def _tick_and_reschedule(self) -> None:
        """Run orchestrator tick and schedule the next one."""
        await self.orchestrator_tick()
        self._schedule_next_tick()

    def start(self) -> None:
        """Start the scheduler."""
        # Fixed schedules
        self.scheduler.add_job(
            self.morning_startup,
            CronTrigger(hour=8, minute=0),
            id="morning_startup",
            replace_existing=True
        )

        self.scheduler.add_job(
            self.evening_wrapup,
            CronTrigger(hour=21, minute=0),
            id="evening_wrapup",
            replace_existing=True
        )

        self.scheduler.start()

        # Schedule first random tick
        self._schedule_next_tick()

        mode = "TEST MODE" if TEST_MODE else "production"
        tick_range = f"{TICK_MIN_MINUTES}-{TICK_MAX_MINUTES}min"
        logger.info(f"Scheduler started ({mode}): morning@8am, wrapup@9pm, tick@random({tick_range})")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
