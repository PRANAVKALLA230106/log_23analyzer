#!/usr/bin/env python3
"""
main.py - CLI entry point for the Log Analyzer tool.

Usage:
    python main.py --file sample_logs/app.log
    python main.py --file sample_logs/app.log --level ERROR --top 5
    python main.py --file sample_logs/app.log --output report.txt
    python main.py --file sample_logs/app.log --start "2024-01-15 10:00:00" --end "2024-01-15 12:00:00"
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Optional

from analyzer import AnalysisResult, LogAnalyzer
from parser import stream_log_file
from utils import parse_datetime, truncate


# ANSI color codes (disabled automatically on non-TTY outputs)
class Color:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    MAGENTA= "\033[95m"
    DIM    = "\033[2m"

    @classmethod
    def disable(cls):
        for attr in ["RESET","BOLD","RED","YELLOW","GREEN","CYAN","MAGENTA","DIM"]:
            setattr(cls, attr, "")


LEVEL_COLORS = {
    "ERROR":    Color.RED,
    "CRITICAL": Color.MAGENTA,
    "WARNING":  Color.YELLOW,
    "INFO":     Color.GREEN,
    "DEBUG":    Color.DIM,
}


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _sep(char: str = "─", width: int = 70) -> str:
    return char * width


def _header(title: str) -> str:
    pad = (68 - len(title)) // 2
    return (
        f"\n{Color.BOLD}{_sep('═')}{Color.RESET}\n"
        f"{Color.BOLD}{' ' * pad}{title}{Color.RESET}\n"
        f"{Color.BOLD}{_sep('═')}{Color.RESET}"
    )


def render_report(result: AnalysisResult, top_n: int, filepath: str) -> str:
    """Build the full report as a string."""
    lines = []

    lines.append(_header("LOG ANALYSIS REPORT"))

    # ── Overview ────────────────────────────────────────────────────────────
    lines.append(f"\n{Color.BOLD}  FILE   {Color.RESET}{filepath}")
    if result.earliest and result.latest:
        lines.append(f"{Color.BOLD}  FROM   {Color.RESET}{result.earliest}")
        lines.append(f"{Color.BOLD}  TO     {Color.RESET}{result.latest}")
        duration = (result.latest - result.earliest).total_seconds()
        hours = duration / 3600
        lines.append(f"{Color.BOLD}  SPAN   {Color.RESET}{hours:.2f} hours")

    lines.append(f"\n{_sep()}")
    lines.append(f"{Color.BOLD}  SUMMARY{Color.RESET}")
    lines.append(_sep())
    lines.append(f"  Total entries processed : {result.total_lines_processed:,}")
    lines.append(f"  Malformed / skipped     : {result.malformed_lines:,}")
    lines.append(f"  Critical alerts         : {Color.RED}{result.critical_count:,}{Color.RESET}")

    # ── Level breakdown ──────────────────────────────────────────────────────
    lines.append(f"\n{_sep()}")
    lines.append(f"{Color.BOLD}  LOG LEVEL BREAKDOWN{Color.RESET}")
    lines.append(_sep())

    total = result.total_lines_processed or 1  # avoid div-by-zero
    for level in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
        count = result.level_counts.get(level, 0)
        pct = count / total * 100
        bar_len = int(pct / 2)  # scale to 50 chars max
        bar = "█" * bar_len
        color = LEVEL_COLORS.get(level, "")
        lines.append(
            f"  {color}{level:<9}{Color.RESET} {count:>8,}  ({pct:5.1f}%)  {color}{bar}{Color.RESET}"
        )

    # ── Top recurring errors ─────────────────────────────────────────────────
    lines.append(f"\n{_sep()}")
    lines.append(f"{Color.BOLD}  TOP {top_n} RECURRING ERRORS{Color.RESET}")
    lines.append(_sep())

    if not result.error_groups:
        lines.append("  No errors found.")
    else:
        for rank, eg in enumerate(result.error_groups, start=1):
            crit_tag = f" {Color.RED}[CRITICAL]{Color.RESET}" if eg.is_critical else ""
            lines.append(
                f"\n  {Color.BOLD}#{rank}{Color.RESET}{crit_tag}  "
                f"Count: {Color.CYAN}{eg.count:,}{Color.RESET}"
            )
            lines.append(f"  Pattern : {truncate(eg.normalized_message, 65)}")
            lines.append(f"  Example : {Color.DIM}{truncate(eg.sample_raw, 65)}{Color.RESET}")
            lines.append(
                f"  Window  : {eg.first_seen}  →  {eg.last_seen}"
            )

    # ── Time-based analysis ──────────────────────────────────────────────────
    if result.errors_per_hour:
        lines.append(f"\n{_sep()}")
        lines.append(f"{Color.BOLD}  ERRORS PER HOUR  (top 10){Color.RESET}")
        lines.append(_sep())
        top_hours = result.errors_per_hour.most_common(10)
        max_count = top_hours[0][1] if top_hours else 1
        for hour, count in top_hours:
            bar_len = int(count / max_count * 30)
            bar = "▓" * bar_len
            lines.append(f"  {hour}  {count:>6,}  {Color.YELLOW}{bar}{Color.RESET}")

    if result.errors_per_minute:
        lines.append(f"\n{_sep()}")
        lines.append(f"{Color.BOLD}  BUSIEST MINUTES  (top 5){Color.RESET}")
        lines.append(_sep())
        for minute, count in result.errors_per_minute.most_common(5):
            lines.append(f"  {minute}  →  {count:,} errors")

    lines.append(f"\n{_sep('═')}\n")
    return "\n".join(lines)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes for plain-text file output."""
    import re
    ansi_escape = re.compile(r"\033\[[0-9;]*m")
    return ansi_escape.sub("", text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="log_analyzer",
        description="Production-grade CLI log analyzer — parses, groups, and summarizes system logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --file sample_logs/app.log
  python main.py --file sample_logs/app.log --level ERROR --top 5
  python main.py --file sample_logs/app.log --output report.txt
  python main.py --file sample_logs/app.log --start "2024-01-15 09:00:00" --end "2024-01-15 12:00:00"
        """,
    )
    p.add_argument(
        "--file", "-f",
        required=True,
        metavar="PATH",
        help="Path to the log file to analyze.",
    )
    p.add_argument(
        "--level", "-l",
        metavar="LEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Filter entries to a specific log level.",
    )
    p.add_argument(
        "--top", "-n",
        type=int,
        default=10,
        metavar="N",
        help="Number of top recurring errors to display (default: 10).",
    )
    p.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Save the plain-text report to this file path.",
    )
    p.add_argument(
        "--start",
        metavar="DATETIME",
        help='Filter entries from this timestamp, e.g. "2024-01-15 09:00:00".',
    )
    p.add_argument(
        "--end",
        metavar="DATETIME",
        help='Filter entries up to this timestamp, e.g. "2024-01-15 18:00:00".',
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output.",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Disable colors when redirecting output or flag set
    if args.no_color or not sys.stdout.isatty():
        Color.disable()

    # Validate file
    if not os.path.isfile(args.file):
        print(f"[ERROR] File not found: {args.file}", file=sys.stderr)
        return 1

    # Parse optional time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    if args.start:
        start_time = parse_datetime(args.start)
        if start_time is None:
            print(f"[ERROR] Invalid --start format. Use 'YYYY-MM-DD HH:MM:SS'.", file=sys.stderr)
            return 1
    if args.end:
        end_time = parse_datetime(args.end)
        if end_time is None:
            print(f"[ERROR] Invalid --end format. Use 'YYYY-MM-DD HH:MM:SS'.", file=sys.stderr)
            return 1

    print(f"{Color.DIM}Streaming {args.file} …{Color.RESET}", file=sys.stderr)

    # Count raw lines while streaming (for malformed count) without extra pass
    raw_line_counter = [0]

    def counted_stream():
        with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                raw_line_counter[0] += 1
                yield line

    from parser import parse_line

    def entry_stream():
        with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                raw_line_counter[0] = lineno
                entry = parse_line(line, lineno)
                if entry is None:
                    continue
                if args.level and entry.level != args.level:
                    continue
                if start_time and entry.timestamp < start_time:
                    continue
                if end_time and entry.timestamp > end_time:
                    continue
                yield entry

    analyzer = LogAnalyzer(top_n=args.top)
    result = analyzer.process(entry_stream())
    result.malformed_lines = raw_line_counter[0] - result.total_lines_processed

    report = render_report(result, args.top, args.file)
    print(report)

    # Optionally save plain-text report
    if args.output:
        plain = strip_ansi(report)
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(plain)
            print(f"{Color.GREEN}Report saved to: {args.output}{Color.RESET}", file=sys.stderr)
        except OSError as exc:
            print(f"[ERROR] Could not write report: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
