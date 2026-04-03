"""
utils.py - Utility functions for log normalization and formatting.
"""

import re
from datetime import datetime
from typing import Optional


# Patterns to normalize dynamic parts of log messages
_NUMBER_RE = re.compile(r"\b\d+\b")
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PATH_RE = re.compile(r"(/[\w./-]+)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_URL_RE = re.compile(r"https?://\S+")

# Keywords that indicate a critical/high-severity message
CRITICAL_KEYWORDS = {
    "failed", "failure", "critical", "fatal", "crash", "panic",
    "exception", "abort", "killed", "segfault", "oom", "out of memory",
    "timeout", "deadlock", "corrupt",
}


def normalize_message(message: str) -> str:
    """
    Replace dynamic tokens in a log message with placeholders so that
    semantically identical messages can be grouped together.

    Example:
        "Connection to 192.168.1.5 failed after 3 retries"
        -> "Connection to <IP> failed after <N> retries"
    """
    msg = _URL_RE.sub("<URL>", message)
    msg = _EMAIL_RE.sub("<EMAIL>", msg)
    msg = _UUID_RE.sub("<UUID>", msg)
    msg = _IP_RE.sub("<IP>", msg)
    msg = _PATH_RE.sub("<PATH>", msg)
    msg = _HEX_RE.sub("<HEX>", msg)
    msg = _NUMBER_RE.sub("<N>", msg)
    return msg


def is_critical(message: str) -> bool:
    """Return True if the message contains any critical-severity keyword."""
    lower = message.lower()
    return any(kw in lower for kw in CRITICAL_KEYWORDS)


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse a datetime string in YYYY-MM-DD HH:MM:SS format."""
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def format_duration(seconds: float) -> str:
    """Convert seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def truncate(text: str, max_len: int = 80) -> str:
    """Truncate a string and append ellipsis if it exceeds max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
