# Log Analyzer

A production-quality CLI tool for parsing, analyzing, and summarizing system log files — built with Python, regex, and a streaming-first architecture.

---

## Features

- **Zero memory overhead** — processes log files line-by-line using generators; handles files with millions of lines.
- **Regex-based parsing** — extracts timestamp, log level, and message from each line; skips malformed lines gracefully.
- **Message normalization** — replaces dynamic tokens (IPs, UUIDs, numbers, paths, URLs) with placeholders so that semantically identical errors are grouped together.
- **Level breakdown** — counts and visualizes entries by severity (DEBUG / INFO / WARNING / ERROR / CRITICAL).
- **Top-N error grouping** — surfaces the most frequent recurring error patterns ranked by occurrence.
- **Critical error detection** — flags messages containing keywords like `failed`, `critical`, `fatal`, `crash`, `timeout`, `deadlock`, and more.
- **Time-based analysis** — shows error counts bucketed by hour and identifies the busiest minutes.
- **Flexible filtering** — filter by log level and/or a time range before analysis begins.
- **Report export** — saves a clean plain-text report to any file path.
- **ANSI color output** — rich terminal colors; auto-disabled when output is piped or `--no-color` is passed.

---

## Project Structure

```
log_analyzer/
├── main.py          # CLI entry point (argparse, report rendering)
├── parser.py        # Regex parsing + streaming generator
├── analyzer.py      # Statistical analysis engine
├── utils.py         # Message normalization, helpers
├── app.log      # ~3 000-line sample log for testing
└── README.md
```

---

## Requirements

- Python **3.8+**
- No third-party dependencies — standard library only.

---

## Installation

```bash
git clone <repo-url>
cd log_analyzer
# No pip install needed
```

---

## Usage

### Basic analysis
```bash
python main.py --file sample_logs/app.log
```

### Filter to ERROR level only
```bash
python main.py --file sample_logs/app.log --level ERROR
```

### Show top 5 recurring errors
```bash
python main.py --file sample_logs/app.log --top 5
```

### Filter by time range
```bash
python main.py --file sample_logs/app.log \
  --start "2024-01-15 09:00:00" \
  --end   "2024-01-15 12:00:00"
```

### Save report to file
```bash
python main.py --file sample_logs/app.log --output report.txt
```

### Combine flags
```bash
python main.py --file sample_logs/app.log \
  --level ERROR \
  --top 10 \
  --start "2024-01-15 08:00:00" \
  --output error_report.txt
```

### Disable color output
```bash
python main.py --file sample_logs/app.log --no-color
```

---

## Log Format

The parser expects lines in the following format:

```
YYYY-MM-DD HH:MM:SS LEVEL Message text here
```

**Example:**
```
2024-01-15 10:23:45 ERROR Failed to connect to Redis at 10.0.0.3:6379 after 3 retries
2024-01-15 10:23:47 INFO  Request processed in 245ms
2024-01-15 10:24:01 WARNING Disk usage at 78% on /dev/sda1
```

Lines that do not match this pattern are counted as malformed and skipped.

---

## Output Example

```
══════════════════════════════════════════════════════════════════════
                      LOG ANALYSIS REPORT
══════════════════════════════════════════════════════════════════════

  FILE   sample_logs/app.log
  FROM   2024-01-15 08:00:03
  TO     2024-01-15 10:29:57
  SPAN   2.50 hours

──────────────────────────────────────────────────────────────────────
  SUMMARY
──────────────────────────────────────────────────────────────────────
  Total entries processed : 3,000
  Malformed / skipped     : 8
  Critical alerts         : 42

──────────────────────────────────────────────────────────────────────
  LOG LEVEL BREAKDOWN
──────────────────────────────────────────────────────────────────────
  CRITICAL      42  ( 1.4%)  ██████████████████████████
  ERROR        387  (12.9%)  ...
  ...

──────────────────────────────────────────────────────────────────────
  TOP 10 RECURRING ERRORS
──────────────────────────────────────────────────────────────────────

  #1 [CRITICAL]  Count: 89
  Pattern : Failed to connect to Redis at <IP>:<N> after <N> retries
  Example : Failed to connect to Redis at 10.0.0.3:6379 after 3 retries
  Window  : 2024-01-15 08:01:12  →  2024-01-15 10:29:44
```

---

## CLI Reference

| Flag | Short | Default | Description |
|---|---|---|---|
| `--file PATH` | `-f` | *(required)* | Log file to analyze |
| `--level LEVEL` | `-l` | all | Filter by log level |
| `--top N` | `-n` | `10` | Number of top errors to show |
| `--output FILE` | `-o` | — | Save plain-text report to file |
| `--start DATETIME` | | — | Start of time range filter |
| `--end DATETIME` | | — | End of time range filter |
| `--no-color` | | false | Disable ANSI color output |

---

## Design Decisions

| Concern | Approach |
|---|---|
| Memory | Generator-based streaming; O(unique patterns) memory, not O(lines) |
| Grouping | Regex normalization replaces dynamic tokens before counting |
| Extensibility | Modular: swap `parser.py` for a different log format with no other changes |
| Performance | Single pass over the file; no sorting until the very end |
| Portability | Zero dependencies; pure standard library |
