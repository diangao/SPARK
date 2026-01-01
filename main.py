#!/usr/bin/env python3
"""S.P.A.R.K. - System for Proactive Accountability, Rhythm & Knowledge"""

import asyncio
import logging
import sys

from config.settings import validate_settings, USER_TELEGRAM_ID
from bot.telegram import create_application, set_scheduler
from bot.scheduler import Scheduler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the bot."""
    # Check required settings
    missing = validate_settings(require_all=True)
    if missing:
        logger.error(f"Missing required settings: {', '.join(missing)}")
        logger.error("Please create config/.env with required variables")
        sys.exit(1)

    logger.info("Starting Spark bot...")

    # Create the bot application
    application = create_application()

    # Create send_message callback for scheduler
    async def send_proactive_message(text: str) -> None:
        """Send a proactive message to the user (split on newlines)."""
        import asyncio
        import random

        if not USER_TELEGRAM_ID:
            logger.warning("Cannot send proactive message: USER_TELEGRAM_ID not set")
            return

        chat_id = int(USER_TELEGRAM_ID)

        # Split on newlines - each line is a separate message
        parts = [p.strip() for p in text.split("\n") if p.strip()]

        try:
            for i, part in enumerate(parts):
                if part:
                    await application.bot.send_message(chat_id=chat_id, text=part)
                    if i < len(parts) - 1:
                        # Natural delay: show typing, wait 1-3 seconds
                        await application.bot.send_chat_action(chat_id=chat_id, action="typing")
                        await asyncio.sleep(random.uniform(1.0, 3.0))
            logger.info(f"Proactive message sent: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send proactive message: {e}")

    # Create and start scheduler (with access to conversation history)
    from agent.coach import get_coach
    scheduler = Scheduler(
        send_proactive_message,
        get_conversation_history=lambda: get_coach().history,
        add_to_history=lambda msg: get_coach().history.append(msg)
    )
    set_scheduler(scheduler)

    # Start scheduler when bot starts
    async def on_startup(app):
        scheduler.start()

    async def on_shutdown(app):
        scheduler.stop()

    application.post_init = on_startup
    application.post_shutdown = on_shutdown

    # Run the bot
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
