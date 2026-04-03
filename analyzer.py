"""
analyzer.py - Core analysis engine.
Consumes a stream of LogEntry objects and builds statistical summaries.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple

from parser import LogEntry
from utils import is_critical, normalize_message


@dataclass
class ErrorGroup:
    """Aggregated information about a recurring error pattern."""
    normalized_message: str
    count: int
    is_critical: bool
    first_seen: datetime
    last_seen: datetime
    sample_raw: str  # one real example for display


@dataclass
class AnalysisResult:
    """Complete analysis output produced by LogAnalyzer."""
    total_lines_processed: int = 0
    malformed_lines: int = 0
    level_counts: Counter = field(default_factory=Counter)
    error_groups: List[ErrorGroup] = field(default_factory=list)
    # Errors per hour bucket  ->  {"2024-01-15 10": count}
    errors_per_hour: Counter = field(default_factory=Counter)
    # Errors per minute bucket -> {"2024-01-15 10:23": count}
    errors_per_minute: Counter = field(default_factory=Counter)
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None
    critical_count: int = 0


class LogAnalyzer:
    """
    Streams log entries from a generator and accumulates statistics.
    Memory usage is O(unique_patterns) rather than O(total_lines).
    """

    ERROR_LEVELS = {"ERROR", "CRITICAL"}

    def __init__(self, top_n: int = 10):
        self.top_n = top_n
        self._level_counts: Counter = Counter()
        # normalized_message -> {count, first_seen, last_seen, is_critical, sample_raw}
        self._error_map: Dict[str, dict] = {}
        self._errors_per_hour: Counter = Counter()
        self._errors_per_minute: Counter = Counter()
        self._total = 0
        self._malformed = 0
        self._earliest: Optional[datetime] = None
        self._latest: Optional[datetime] = None
        self._critical_count = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self, entries: Iterator[LogEntry]) -> AnalysisResult:
        """Feed the analyzer with a stream of LogEntry objects."""
        for entry in entries:
            self._ingest(entry)

        return self._build_result()

    def process_with_malformed(
        self, entries: Iterator[LogEntry], total_raw_lines: int
    ) -> AnalysisResult:
        """
        Same as process() but also records the count of unparseable lines
        when the caller provides the raw line total.
        """
        result = self.process(entries)
        result.malformed_lines = total_raw_lines - result.total_lines_processed
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest(self, entry: LogEntry) -> None:
        self._total += 1
        self._level_counts[entry.level] += 1

        # Track time boundaries
        if self._earliest is None or entry.timestamp < self._earliest:
            self._earliest = entry.timestamp
        if self._latest is None or entry.timestamp > self._latest:
            self._latest = entry.timestamp

        if entry.level in self.ERROR_LEVELS:
            self._record_error(entry)

    def _record_error(self, entry: LogEntry) -> None:
        norm = normalize_message(entry.message)
        critical = is_critical(entry.message)

        if critical:
            self._critical_count += 1

        # Bucket keys for time-based analysis
        hour_key = entry.timestamp.strftime("%Y-%m-%d %H:00")
        minute_key = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        self._errors_per_hour[hour_key] += 1
        self._errors_per_minute[minute_key] += 1

        if norm not in self._error_map:
            self._error_map[norm] = {
                "count": 0,
                "is_critical": critical,
                "first_seen": entry.timestamp,
                "last_seen": entry.timestamp,
                "sample_raw": entry.message,
            }

        rec = self._error_map[norm]
        rec["count"] += 1
        rec["is_critical"] = rec["is_critical"] or critical
        if entry.timestamp < rec["first_seen"]:
            rec["first_seen"] = entry.timestamp
        if entry.timestamp > rec["last_seen"]:
            rec["last_seen"] = entry.timestamp

    def _build_result(self) -> AnalysisResult:
        # Sort error groups by frequency descending, take top N
        sorted_errors = sorted(
            self._error_map.items(), key=lambda kv: kv[1]["count"], reverse=True
        )
        top_errors: List[ErrorGroup] = []
        for norm_msg, rec in sorted_errors[: self.top_n]:
            top_errors.append(
                ErrorGroup(
                    normalized_message=norm_msg,
                    count=rec["count"],
                    is_critical=rec["is_critical"],
                    first_seen=rec["first_seen"],
                    last_seen=rec["last_seen"],
                    sample_raw=rec["sample_raw"],
                )
            )

        return AnalysisResult(
            total_lines_processed=self._total,
            level_counts=self._level_counts,
            error_groups=top_errors,
            errors_per_hour=self._errors_per_hour,
            errors_per_minute=self._errors_per_minute,
            earliest=self._earliest,
            latest=self._latest,
            critical_count=self._critical_count,
        )
