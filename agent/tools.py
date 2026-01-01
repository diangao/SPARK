import logging
from datetime import datetime
from pathlib import Path, PurePath

from config.settings import THINK_OS_PATH
from agent.storage import get_storage

logger = logging.getLogger(__name__)

# =============================================================================
# ACCESS CONTROL CONFIGURATION
# =============================================================================

# Paths the agent CAN READ (glob patterns, relative to Think OS root)
READABLE_PATHS = [
    "now.md",                           # Active topics
    "memory/*.md",                      # User profile (e.g., memory/{USER_NAME}.md)
    "memory/spark/*.md",                # Spark-specific files (protocol, learned)
    "memory/spark/*.json",              # Spark state
    "memory/timeline/perspective.md",   # Goals and values
    "memory/timeline/daily/*.md",       # Daily records
    "memory/timeline/todo/*.md",        # Todo files
    "memory/people/*.md",               # Credible sources
    "tinker",                           # Tinker directory (list contents)
    "tinker/*",                         # Tinker subdirectories
    "tinker/**/*.md",                   # Project notes and research
]

# Paths the agent CAN WRITE (glob patterns, relative to Think OS root)
WRITABLE_PATHS = [
    "memory/timeline/daily/*.md",       # Daily records
    "memory/timeline/todo/*.md",        # Todo files
    "memory/spark/*.md",                # Spark learned preferences
    "memory/spark/*.json",              # Spark state
]

# Paths the agent can NEVER access
BLOCKED_PATHS = [
    "*.secret.md",
    "private/*",
    ".git/*",
]


# =============================================================================
# ACCESS CONTROL FUNCTIONS
# =============================================================================

def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check if path matches any of the glob patterns.

    Uses PurePath.match() which supports ** for recursive directory matching.
    """
    p = PurePath(path)
    for pattern in patterns:
        if p.match(pattern):
            return True
    return False


def _validate_path(path: str, for_write: bool = False) -> tuple[bool, str, str]:
    """Validate path access."""
    if not THINK_OS_PATH:
        return False, "THINK_OS_PATH not configured", ""

    think_os_root = Path(THINK_OS_PATH).resolve()

    if Path(path).is_absolute():
        try:
            rel_path = str(Path(path).resolve().relative_to(think_os_root))
        except ValueError:
            return False, f"Path outside Think OS: {path}", ""
    else:
        rel_path = path

    full_path = (think_os_root / rel_path).resolve()

    try:
        full_path.relative_to(think_os_root)
    except ValueError:
        return False, f"Path traversal detected: {path}", ""

    if _matches_any_pattern(rel_path, BLOCKED_PATHS):
        logger.warning(f"ACCESS DENIED (blocked): {rel_path}")
        return False, f"Access denied: {rel_path}", ""

    allowed_patterns = WRITABLE_PATHS if for_write else READABLE_PATHS
    if not _matches_any_pattern(rel_path, allowed_patterns):
        action = "write" if for_write else "read"
        logger.warning(f"ACCESS DENIED (not in {action} allowlist): {rel_path}")
        return False, f"Not allowed to {action}: {rel_path}", ""

    return True, str(full_path), rel_path


# =============================================================================
# TOOLS
# =============================================================================

async def read_think_os(path: str) -> dict:
    """Read a file or list a directory from Think OS."""
    is_valid, result, rel_path = _validate_path(path, for_write=False)
    if not is_valid:
        return {"success": False, "error": result}

    full_path = Path(result)
    storage = get_storage()

    try:
        # If it's a directory, list its contents
        if full_path.is_dir():
            files = []
            for item in sorted(full_path.iterdir()):
                rel_item = str(item.relative_to(Path(THINK_OS_PATH)))
                if item.is_dir():
                    files.append(f"{rel_item}/")
                else:
                    files.append(rel_item)
            logger.info(f"LIST: {rel_path} ({len(files)} items)")
            return {"success": True, "type": "directory", "files": files}

        if not await storage.exists(str(full_path)):
            return {"success": False, "error": f"File not found: {path}"}

        content = await storage.read(str(full_path))
        logger.info(f"READ: {rel_path} ({len(content)} chars)")
        return {"success": True, "type": "file", "content": content}
    except Exception as e:
        return {"success": False, "error": f"Read error: {e}"}


async def write_think_os(path: str, content: str, mode: str = "overwrite") -> dict:
    """Write content to a file in Think OS.

    Args:
        path: Relative path to file
        content: Content to write
        mode: "overwrite" (default) or "append"
    """
    is_valid, result, rel_path = _validate_path(path, for_write=True)
    if not is_valid:
        return {"success": False, "error": result}

    full_path = result
    storage = get_storage()

    try:
        if mode == "append" and await storage.exists(full_path):
            existing = await storage.read(full_path)
            content = existing + "\n" + content

        await storage.write(full_path, content)
        logger.info(f"WRITE ({mode}): {rel_path} ({len(content)} chars)")
        return {"success": True}
    except Exception as e:
        logger.error(f"WRITE FAILED: {rel_path} - {e}")
        return {"success": False, "error": f"Write error: {e}"}


def get_current_time() -> dict:
    """Get current date and time."""
    now = datetime.now()
    return {
        "success": True,
        "datetime": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
    }


# =============================================================================
# TOOL DEFINITIONS FOR CLAUDE API
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "name": "read_think_os",
        "description": (
            "Read a file or list a directory from Think OS. "
            "If path is a directory, returns list of files. "
            "Allowed: now.md, memory/profile.md, memory/spark/*.md, memory/timeline/perspective.md, "
            "memory/timeline/daily/*.md, memory/timeline/todo/*.md, memory/people/*.md, "
            "tinker/ (can list and read project notes)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path, e.g., 'now.md' or 'memory/timeline/daily/2025-12-20.md'"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_think_os",
        "description": (
            "Write content to a file in Think OS. "
            "Allowed: memory/timeline/daily/*.md, memory/timeline/todo/*.md, memory/spark/*.md."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path, e.g., 'memory/timeline/daily/2025-12-20.md'"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (full file for overwrite, or just new content for append)"
                },
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append"],
                    "description": "overwrite (default) replaces file, append adds to end"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "get_current_time",
        "description": "Get current date and time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


async def execute_tool(name: str, input_data: dict) -> dict:
    """Execute a tool by name."""
    if name == "read_think_os":
        return await read_think_os(input_data.get("path", ""))
    elif name == "write_think_os":
        return await write_think_os(
            input_data.get("path", ""),
            input_data.get("content", ""),
            input_data.get("mode", "overwrite")
        )
    elif name == "get_current_time":
        return get_current_time()
    else:
        return {"success": False, "error": f"Unknown tool: {name}"}


def get_access_summary() -> str:
    """Return a human-readable summary of access controls."""
    return f"""
Think OS Access Controls:
-------------------------
READABLE: {', '.join(READABLE_PATHS)}
WRITABLE: {', '.join(WRITABLE_PATHS)}
BLOCKED:  {', '.join(BLOCKED_PATHS)}
"""
