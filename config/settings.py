import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from config directory
config_dir = Path(__file__).parent
load_dotenv(config_dir / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
USER_TELEGRAM_ID = os.getenv("USER_TELEGRAM_ID")
THINK_OS_PATH = os.getenv("THINK_OS_PATH")

# User personalization
USER_NAME = os.getenv("USER_NAME", "")  # What to call you
USER_PRONOUNS = os.getenv("USER_PRONOUNS", "")  # they/them, she/her, he/him
GUILT_LEVEL = os.getenv("GUILT_LEVEL", "medium")  # chill, medium, savage
SPARK_STYLE = os.getenv("SPARK_STYLE", "")  # e.g. "ABC bro who roasts you", "supportive coach", etc.

# Storage backend: "local" (default) or "github"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

# Orchestrator provider: "anthropic" (default) or "deepseek"
ORCHESTRATOR_PROVIDER = os.getenv("ORCHESTRATOR_PROVIDER", "anthropic")
# Coach provider: "anthropic" (default) or "deepseek"
COACH_PROVIDER = os.getenv("COACH_PROVIDER", "anthropic")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Test mode: more aggressive nudging, shorter intervals
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Quiet hours - orchestrator won't tick during these hours (24h format, local time)
# Example: QUIET_START=23, QUIET_END=8 means no ticks from 11pm to 8am
QUIET_START = int(os.getenv("QUIET_START", "23"))  # 11pm
QUIET_END = int(os.getenv("QUIET_END", "8"))  # 8am

# Orchestrator tick interval (minutes) - random between min and max
# Test mode: 10-20 seconds, Production: 1-20 minutes (default)
TICK_MIN_MINUTES = float(os.getenv("TICK_MIN_MINUTES", "0.17" if TEST_MODE else "1"))
TICK_MAX_MINUTES = float(os.getenv("TICK_MAX_MINUTES", "0.33" if TEST_MODE else "20"))

# GitHub storage settings (only needed when STORAGE_BACKEND=github)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")


def validate_settings(require_all: bool = False) -> list[str]:
    """Return list of missing required settings.

    Args:
        require_all: If True, require Agent settings too.
                     If False, only require Telegram token.
    """
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if require_all:
        if not ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        if not THINK_OS_PATH:
            missing.append("THINK_OS_PATH")
    return missing
