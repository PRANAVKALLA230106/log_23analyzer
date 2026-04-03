"""
parser.py - Log file parsing module.
Handles regex-based extraction of structured data from raw log lines.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

# Regex pattern for standard log format:
# 2024-01-15 10:23:45 ERROR Some message here
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"
    r"\s+(?P<level>INFO|WARNING|ERROR|DEBUG|CRITICAL)"
    r"\s+(?P<message>.+)$"
)

VALID_LEVELS = {"INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL"}


@dataclass
class LogEntry:
    """Represents a single parsed log entry."""
    timestamp: datetime
    level: str
    message: str
    raw_line: str
    line_number: int


def parse_line(line: str, line_number: int) -> Optional[LogEntry]:
    """
    Parse a single log line using regex.
    Returns None for malformed lines.
    """
    line = line.rstrip("\n").strip()
    if not line:
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    try:
        timestamp = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return LogEntry(
        timestamp=timestamp,
        level=match.group("level"),
        message=match.group("message").strip(),
        raw_line=line,
        line_number=line_number,
    )


def stream_log_file(
    filepath: str,
    level_filter: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Iterator[LogEntry]:
    """
    Generator that streams log entries from a file one line at a time.
    Applies optional filters for log level and time range.
    Never loads the entire file into memory.
    """
    level_filter_upper = level_filter.upper() if level_filter else None

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        for line_number, line in enumerate(fh, start=1):
            entry = parse_line(line, line_number)
            if entry is None:
                continue

            # Apply log level filter
            if level_filter_upper and entry.level != level_filter_upper:
                continue

            # Apply time range filters
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue

            yield entry
