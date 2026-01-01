import json
import logging
import re

from anthropic import Anthropic
from openai import OpenAI

from config.settings import (
    ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, COACH_PROVIDER,
    USER_NAME, USER_PRONOUNS, GUILT_LEVEL
)
from agent.tools import TOOL_DEFINITIONS, execute_tool, read_think_os

logger = logging.getLogger(__name__)

# Model configs per provider
COACH_CONFIGS = {
    "anthropic": {"model": "claude-3-5-haiku-20241022", "style_boost": ""},
    "deepseek": {
        "model": "deepseek-chat",
        # Minimal model-specific patches. Style is in protocol.md.
        # Code handles: timestamp stripping, CoT truncation, write validation
        "style_boost": """
---

## DeepSeek-specific

STYLE: SHORT. Each thought = own line. 1-5 words when possible. No essays.

READ YOUR HISTORY before responding. Never repeat yourself.

YOU MUST USE write_think_os when user sets tasks or gives feedback.
If you say "updated" without calling the tool, the data is LOST.
Prefer mode="append" for check-ins and new entries.

When user says a duration ("30 min"), respect it. Don't ask "done yet?" before deadline.

When user says "ok" / "on it" → ask "how long?" or "lmk when done", don't immediately check.
""",
    },
}


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

# System prompt is loaded from Think OS: memory/spark-protocol.md
# Fallback prompt if protocol file not found
FALLBACK_SYSTEM_PROMPT = """You are Spark, a proactive coach.
Read memory/spark/protocol.md to understand how to behave.
If that file doesn't exist, be helpful and concise."""


class Coach:
    """Claude-powered coach agent. Loads behavior from Think OS files."""

    def __init__(self):
        self.provider = COACH_PROVIDER
        self.config = COACH_CONFIGS.get(self.provider, COACH_CONFIGS["anthropic"])
        self.max_tokens = 1024

        # Initialize clients based on provider
        self.anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        ) if DEEPSEEK_API_KEY else None

        # Validate we have the right client
        if self.provider == "deepseek" and not self.deepseek_client:
            raise ValueError("DEEPSEEK_API_KEY not set")
        elif self.provider == "anthropic" and not self.anthropic_client:
            raise ValueError("ANTHROPIC_API_KEY not set")

        logger.info(f"Coach provider: {self.provider}, model: {self.config['model']}")

        self._system_prompt: str | None = None
        self.history: list[dict] = []
        self._history_date: str | None = None  # Track which day's history this is

    async def _load_system_prompt(self) -> str:
        """Load system prompt from Think OS files.

        Protocol and profile are cached. Learned preferences reload every time.
        """
        # Load static parts once
        if self._system_prompt is None:
            parts = []

            # 0. User config (from .env)
            user_info = []
            if USER_NAME:
                user_info.append(f"Name: {USER_NAME}")
            if USER_PRONOUNS:
                user_info.append(f"Pronouns: {USER_PRONOUNS}")
            if GUILT_LEVEL:
                guilt_note = {"chill": "go easy on them", "medium": "normal guilt trips", "savage": "be ruthless"}.get(GUILT_LEVEL, GUILT_LEVEL)
                user_info.append(f"Guilt level: {guilt_note}")
            if user_info:
                parts.append(f"# User\n{', '.join(user_info)}")

            # 1. Protocol (defines behavior) - static
            result = await read_think_os("memory/spark/protocol.md")
            if result["success"]:
                parts.append(result["content"])
            else:
                parts.append(FALLBACK_SYSTEM_PROMPT)
                logger.warning("spark-protocol.md not found, using fallback")

            # 2. User profile (relationship context) - static
            result = await read_think_os("memory/profile.md")
            if result["success"]:
                parts.append(f"\n---\n\n# User Profile\n\n{result['content']}")

            self._system_prompt = "\n".join(parts)
            logger.info(f"Loaded base system prompt: {len(self._system_prompt)} chars")

        # 3. Learned preferences - reload every time so learning takes effect immediately
        full_prompt = self._system_prompt
        result = await read_think_os("memory/spark/learned.md")
        if result["success"]:
            full_prompt += f"\n---\n\n# Learned Preferences\n\n{result['content']}"

        return full_prompt

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history = []
        self._history_date = None
        logger.info("Conversation history cleared")

    def _check_daily_reset(self) -> None:
        """Reset history if it's a new day."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        if self._history_date != today:
            if self._history_date is not None:
                logger.info(f"New day detected ({self._history_date} → {today}), clearing history")
            self.history = []
            self._history_date = today

    async def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        from datetime import datetime

        # Reset history if new day
        self._check_daily_reset()

        # Load system prompt from Think OS (cached after first load)
        system_prompt = await self._load_system_prompt()

        # Add style_boost for this provider (e.g., DeepSeek-specific rules)
        style_boost = self.config.get("style_boost", "")
        if style_boost:
            system_prompt += style_boost

        # KV-cache optimization: time context goes in user message, not system prompt
        # This keeps system_prompt stable for caching (~10x cost reduction)
        now = datetime.now()
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        time_context = f"[{now.strftime('%H:%M')} {weekdays[now.weekday()]} {now.strftime('%Y-%m-%d')}]"

        # Add user message to history with timestamp
        self.history.append({"role": "user", "content": f"{time_context} {user_message}"})

        # Route to appropriate provider
        if self.provider == "deepseek":
            return await self._chat_deepseek(system_prompt)
        else:
            return await self._chat_anthropic(system_prompt)

    async def _chat_anthropic(self, system_prompt: str) -> str:
        """Chat using Anthropic API."""
        messages = list(self.history)
        wrote_this_turn = False  # Track if write_think_os was called

        while True:
            logger.info(f"Calling Anthropic API... (history: {len(self.history)} messages)")

            response = self.anthropic_client.messages.create(
                model=self.config["model"],
                max_tokens=self.max_tokens,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            logger.info(f"Response stop_reason: {response.stop_reason}")

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)})")

                        # Track write calls
                        if tool_name == "write_think_os":
                            wrote_this_turn = True

                        result = await execute_tool(tool_name, tool_input)
                        logger.info(f"Tool result: {json.dumps(result)[:200]}...")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            else:
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                # Strip any [HH:MM] timestamps the model might output (anywhere in text)
                final_text = re.sub(r'\[\d{1,2}:\d{2}\]\s*', '', final_text)

                # Validate: if model claims to have written but didn't call tool
                acknowledgment_words = ["updated", "noted", "saved", "recorded", "logged"]
                if any(word in final_text.lower() for word in acknowledgment_words) and not wrote_this_turn:
                    logger.warning(f"Model claimed to write but didn't call write_think_os: {final_text[:100]}")

                # Truncate chain-of-thought: if too many lines, keep last few
                lines = [l for l in final_text.strip().split('\n') if l.strip()]
                if len(lines) > 6:
                    logger.info(f"Truncating verbose response: {len(lines)} lines -> 4 lines")
                    final_text = '\n'.join(lines[-4:])

                if final_text.strip():
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%H:%M")
                    self.history.append({"role": "assistant", "content": f"[{timestamp}] {final_text}"})
                else:
                    logger.warning("Empty response, not saving to history")

                return final_text if final_text.strip() else "hold on"

    async def _chat_deepseek(self, system_prompt: str) -> str:
        """Chat using DeepSeek API (OpenAI-compatible)."""
        # Build messages with system prompt for OpenAI format
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history)

        openai_tools = convert_tools_to_openai(TOOL_DEFINITIONS)
        wrote_this_turn = False  # Track if write_think_os was called

        while True:
            logger.info(f"Calling DeepSeek API... (history: {len(self.history)} messages)")

            response = self.deepseek_client.chat.completions.create(
                model=self.config["model"],
                max_tokens=self.max_tokens,
                messages=messages,
                tools=openai_tools,
            )

            choice = response.choices[0]
            logger.info(f"Response finish_reason: {choice.finish_reason}")

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_input = json.loads(tool_call.function.arguments)

                    logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)})")

                    # Track write calls
                    if tool_name == "write_think_os":
                        wrote_this_turn = True

                    result = await execute_tool(tool_name, tool_input)
                    logger.info(f"Tool result: {json.dumps(result)[:200]}...")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    })

            else:
                final_text = choice.message.content or ""

                # Log raw response for debugging
                logger.info(f"RAW COACH RESPONSE ({len(final_text)} chars):\n{final_text[:2000]}")
                if len(final_text) > 2000:
                    logger.info(f"... (truncated, total {len(final_text)} chars)")

                # Strip any [HH:MM] timestamps the model might output (anywhere in text)
                final_text = re.sub(r'\[\d{1,2}:\d{2}\]\s*', '', final_text)

                # Validate: if model claims to have written but didn't call tool
                acknowledgment_words = ["updated", "noted", "saved", "recorded", "logged"]
                if any(word in final_text.lower() for word in acknowledgment_words) and not wrote_this_turn:
                    logger.warning(f"Model claimed to write but didn't call write_think_os: {final_text[:100]}")

                # Truncate chain-of-thought: if too many lines, keep last few
                lines = [l for l in final_text.strip().split('\n') if l.strip()]
                if len(lines) > 6:
                    logger.info(f"Truncating verbose response: {len(lines)} lines -> 4 lines")
                    final_text = '\n'.join(lines[-4:])

                if final_text.strip():
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%H:%M")
                    self.history.append({"role": "assistant", "content": f"[{timestamp}] {final_text}"})
                else:
                    logger.warning("Empty response, not saving to history")

                return final_text if final_text.strip() else "hold on"


_coach = None


def get_coach() -> Coach:
    """Get or create the coach instance."""
    global _coach
    if _coach is None:
        _coach = Coach()
    return _coach
