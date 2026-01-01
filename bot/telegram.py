import asyncio
import logging
import random
import re
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config.settings import TELEGRAM_BOT_TOKEN, USER_TELEGRAM_ID, ANTHROPIC_API_KEY
from agent.coach import get_coach
from agent.tools import get_access_summary
from agent.prompts import get_command, list_commands

logger = logging.getLogger(__name__)

# Global scheduler reference (set by main.py)
_scheduler = None

# Flag to prevent orchestrator from sending while coach is processing
_user_interacting = False

# Debounce settings
DEBOUNCE_SECONDS = 4.0  # Wait this long after last message before processing


@dataclass
class MessageBuffer:
    """Buffer for collecting rapid-fire messages."""
    messages: list = field(default_factory=list)
    task: asyncio.Task | None = None
    chat: any = None  # Store chat for sending responses


# Per-user message buffers
_message_buffers: dict[int, MessageBuffer] = {}


def is_user_interacting() -> bool:
    """Check if user is currently interacting (coach processing)."""
    return _user_interacting


def set_scheduler(scheduler) -> None:
    """Set the global scheduler instance."""
    global _scheduler
    _scheduler = scheduler


def get_scheduler():
    """Get the global scheduler instance."""
    return _scheduler


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot."""
    if not USER_TELEGRAM_ID:
        # No restriction if USER_TELEGRAM_ID not set
        return True
    return str(user_id) == str(USER_TELEGRAM_ID)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"User started bot: id={user.id}, username={user.username}")

    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    await update.message.reply_text(
        "heyy i'm spark\n\n"
        "here to help u get stuff done without the stress\n\n"
        "things i can do:\n"
        "/schedule - plan ur day\n"
        "/checkin - quick check in\n"
        "/startup - morning kickoff\n"
        "/wrapup - end of day reflection\n"
        "/focus - pick one thing\n"
        "/clear - fresh start\n\n"
        "or just msg me"
    )


async def access_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /access command - show what files the agent can access."""
    user = update.effective_user

    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    summary = get_access_summary()
    await update.message.reply_text(f"```\n{summary}\n```", parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command - clear conversation history."""
    user = update.effective_user

    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    coach = get_coach()
    history_len = len(coach.history)
    coach.clear_history()
    await update.message.reply_text(f"cleared {history_len} msgs, fresh start")


async def think_os_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Think OS commands (/startup, /midcheck, /wrapup, /focus)."""
    user = update.effective_user

    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    if not ANTHROPIC_API_KEY:
        await update.message.reply_text("Agent not configured.")
        return

    # Extract command name from /command
    command_name = update.message.text.split()[0][1:]  # Remove leading /
    prompt = get_command(command_name)

    if not prompt:
        await update.message.reply_text(f"Unknown command: {command_name}")
        return

    logger.info(f"Think OS command: /{command_name}")

    # Send typing indicator
    await update.message.chat.send_action("typing")

    try:
        coach = get_coach()
        response = await coach.chat(prompt)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Command error: {e}", exc_info=True)
        await update.message.reply_text(f"Error: {e}")


async def _process_buffered_messages(user_id: int) -> None:
    """Process all buffered messages for a user after debounce delay."""
    global _user_interacting

    buffer = _message_buffers.get(user_id)
    if not buffer or not buffer.messages:
        return

    # Combine all messages into one
    combined_text = "\n".join(buffer.messages)
    chat = buffer.chat
    message_count = len(buffer.messages)

    # Clear the buffer
    buffer.messages = []
    buffer.task = None

    logger.info(f"Processing {message_count} buffered messages for user_id={user_id}")

    # Check for duration in user message and set working deadline
    if _scheduler:
        await _scheduler.check_and_set_working_deadline(combined_text)

    # Set flag to prevent orchestrator from sending
    _user_interacting = True

    # Send typing indicator
    await chat.send_action("typing")

    try:
        coach = get_coach()
        response = await coach.chat(combined_text)
        if not response or not response.strip():
            response = "?"  # fallback if empty

        # Post-process for texting style (Code > Prompt principle):
        # 1. Split on sentence boundaries to create separate messages
        # 2. Strip trailing . and , (casual style doesn't need them)
        # 3. Keep ? and ! (expressive punctuation)
        parts = []
        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Split on sentence boundaries (. ! ?)
            sentences = re.split(r'(?<=[.!?])\s+', line)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                # Strip trailing . and , for casual texting style
                s = s.rstrip('.,')
                if s:
                    parts.append(s)

        for i, part in enumerate(parts):
            await chat.send_message(part)
            if i < len(parts) - 1:
                await chat.send_action("typing")
                await asyncio.sleep(random.uniform(0.8, 2.0))

        # Record interaction for scheduler
        if _scheduler:
            await _scheduler.record_interaction()
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await chat.send_message(f"Error: {e}")
    finally:
        _user_interacting = False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages with debouncing."""
    global _user_interacting
    user = update.effective_user
    text = update.message.text

    logger.info(f"Message from user_id={user.id}: {text[:50]}...")

    if not is_authorized(user.id):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    # Check if agent is configured
    if not ANTHROPIC_API_KEY:
        await update.message.reply_text(
            "Agent not configured. Please set ANTHROPIC_API_KEY in config/.env"
        )
        return

    # Set flag IMMEDIATELY to prevent orchestrator from sending
    _user_interacting = True

    # Get or create buffer for this user
    if user.id not in _message_buffers:
        _message_buffers[user.id] = MessageBuffer()

    buffer = _message_buffers[user.id]
    buffer.messages.append(text)
    buffer.chat = update.message.chat

    # Cancel existing debounce task if any
    if buffer.task and not buffer.task.done():
        buffer.task.cancel()

    # Show typing indicator while waiting
    try:
        await update.message.chat.send_action("typing")
    except Exception:
        pass  # Ignore typing indicator errors (topics/permissions)

    # Schedule processing after debounce delay
    async def debounced_process():
        await asyncio.sleep(DEBOUNCE_SECONDS)
        await _process_buffered_messages(user.id)

    buffer.task = asyncio.create_task(debounced_process())


def create_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("access", access_command))
    application.add_handler(CommandHandler("clear", clear_command))

    # Think OS commands
    for cmd in list_commands():
        application.add_handler(CommandHandler(cmd, think_os_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application
