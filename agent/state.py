"""Session state management - persists to Think OS."""

import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from agent.storage import get_storage
from config.settings import THINK_OS_PATH

logger = logging.getLogger(__name__)

# Relative path within Think OS
STATE_FILE_REL = "memory/spark/state.json"


def _get_state_path() -> str:
    """Get absolute path to state file in Think OS."""
    if not THINK_OS_PATH:
        raise ValueError("THINK_OS_PATH not configured")
    return str(Path(THINK_OS_PATH) / STATE_FILE_REL)


@dataclass
class SessionState:
    """Spark's session state - persisted between restarts."""
    last_interaction: str | None = None  # ISO datetime
    unanswered_count: int = 0
    stuck_on: str | None = None  # Task user said they're stuck on
    current_focus: str | None = None  # Today's main focus
    last_checkin_summary: str | None = None  # Brief summary of last check-in
    # Context engineering improvements
    working_until: str | None = None  # ISO datetime - user's stated deadline (e.g., "30 min" from now)
    last_spark_message: str | None = None  # ISO datetime - when Spark last sent a message

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


async def load_state() -> SessionState:
    """Load state from Think OS. Returns default state if not found."""
    storage = get_storage()
    state_path = _get_state_path()
    try:
        if await storage.exists(state_path):
            content = await storage.read(state_path)
            data = json.loads(content)
            logger.info(f"Loaded state: {data}")
            return SessionState.from_dict(data)
    except Exception as e:
        logger.warning(f"Could not load state: {e}")

    return SessionState()


async def save_state(state: SessionState) -> None:
    """Save state to Think OS."""
    storage = get_storage()
    state_path = _get_state_path()
    try:
        content = json.dumps(state.to_dict(), indent=2, ensure_ascii=False)
        await storage.write(state_path, content)
        logger.debug(f"Saved state to {state_path}")
    except Exception as e:
        logger.error(f"Could not save state: {e}")


async def update_state(**updates) -> SessionState:
    """Load, update, and save state in one operation."""
    state = await load_state()
    for key, value in updates.items():
        if hasattr(state, key):
            setattr(state, key, value)
    await save_state(state)
    return state
