# Multi-Agent Session Concurrency: Conflict-Free Design

> How to prevent race conditions when multiple AI agents share the same workspace and memory files.

---

## Table of Contents

1. [Problem Description](#1-problem-description)
2. [Root Cause Analysis](#2-root-cause-analysis)
3. [Solution Overview](#3-solution-overview)
4. [Solution 1 — File Locking](#4-solution-1--file-locking)
5. [Solution 2 — Path Separation](#5-solution-2--path-separation)
6. [Solution 3 — Role-Based Responsibility Split](#6-solution-3--role-based-responsibility-split)
7. [Putting It Together](#7-putting-it-together)
8. [Common Mistakes](#8-common-mistakes)
9. [Quick Reference](#9-quick-reference)

---

## 1. Problem Description

In a multi-agent AI system, several agent sessions may run simultaneously. Each session processes incoming messages independently, yet they often share:

- A **common workspace directory** (e.g., `/workspace/`)
- **Shared memory files** (e.g., `memory/MEMORY.md`, `memory/2026-03-15.md`)
- **State files** and task logs

When two agents try to write the same file at the same moment, a **race condition** occurs:

```
Session A                        Session B
─────────                        ─────────
read("memory/today.md")          read("memory/today.md")
  → "# 2026-03-15\n- Event A"     → "# 2026-03-15\n- Event A"
append("- Event B")              append("- Event C")
write(file)                      write(file)   ← overwrites A's write
```

**Result**: Only "Event C" survives. "Event B" is silently lost.

This is not a theoretical risk — it happens in production whenever:
- A direct-message session and a group-chat session both update the daily log
- Two parallel task agents both write their results to a shared file
- An orchestrator and a sub-agent both update a shared state file

---

## 2. Root Cause Analysis

### 2.1 Non-Atomic Read-Modify-Write

The standard pattern `read → modify → write` is not atomic. Any other writer can interleave between these steps.

### 2.2 No Built-in Coordination

Each agent session runs in its own process or async context. Without an explicit coordination mechanism, there is no awareness of other writers.

### 2.3 Shared Mutable State

Shared memory files act as mutable global state. The more agents share a file, the higher the probability of collision.

### 2.4 Silent Failures

File overwrites do not raise exceptions. The losing agent successfully completes its write — it simply overwrites the winner's data with stale content.

---

## 3. Solution Overview

Three complementary strategies, applied in layers:

| Layer | Strategy | Best For |
|-------|----------|----------|
| L1 | **File Locking** | Serialize writes to any shared file |
| L2 | **Path Separation** | Eliminate sharing by giving each session its own files |
| L3 | **Responsibility Split** | Designate a single writer per file category |

Use all three together for maximum safety. Use L1 alone as a quick fix.

---

## 4. Solution 1 — File Locking

### 4.1 Concept

Before writing a shared file, acquire an exclusive lock. Other writers block until the lock is released. This serializes writes without data loss.

### 4.2 Implementation

```python
# tools/file_lock_write.py
"""
Atomic file writer with advisory locking.
Usage:
    python file_lock_write.py <path> <content> [--mode append|overwrite]
"""

import fcntl
import os
import sys
import argparse
import time
from pathlib import Path


def locked_write(file_path: str, content: str, mode: str = "append") -> None:
    """
    Write content to a file under an exclusive advisory lock.

    Args:
        file_path: Target file path (created if it does not exist).
        content:   Text to write.
        mode:      "append" adds to the end; "overwrite" replaces all content.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = path.with_suffix(path.suffix + ".lock")

    with open(lock_path, "w") as lock_file:
        try:
            for attempt in range(10):
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if attempt == 9:
                        raise TimeoutError(
                            f"Could not acquire lock on {file_path} after 10 attempts"
                        )
                    time.sleep(0.1 * (attempt + 1))

            open_mode = "a" if mode == "append" else "w"
            with open(file_path, open_mode, encoding="utf-8") as f:
                f.write(content)

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description="Write a file with exclusive locking.")
    parser.add_argument("path", help="Target file path")
    parser.add_argument("content", help="Content to write")
    parser.add_argument(
        "--mode",
        choices=["append", "overwrite"],
        default="append",
        help="Write mode (default: append)",
    )
    args = parser.parse_args()

    locked_write(args.path, args.content, args.mode)
    print(f"[ok] wrote to {args.path} (mode={args.mode})")


if __name__ == "__main__":
    main()
```

### 4.3 Usage

```bash
# Append a log entry
python tools/file_lock_write.py memory/2026-03-15.md "- 14:00 Task completed\n" --mode append

# Overwrite a state file
python tools/file_lock_write.py state/current.json '{"status": "idle"}' --mode overwrite
```

```python
from tools.file_lock_write import locked_write

locked_write("memory/2026-03-15.md", "- 15:00 Agent B finished analysis\n")
```

### 4.4 How It Works

```
Session A                        Session B
─────────                        ─────────
open("today.md.lock")            open("today.md.lock")
flock(LOCK_EX) ✓ acquired        flock(LOCK_EX) … blocked …
write("- Event B\n")
flock(LOCK_UN)
                                 … unblocked → LOCK_EX ✓ acquired
                                 write("- Event C\n")
                                 flock(LOCK_UN)
```

Both events are preserved, in arrival order.

### 4.5 Limitations

- `fcntl.flock` is advisory: uncooperative writers that skip locking are not blocked.
- Does not work across network filesystems (NFS, SMB). Use Redis `SET NX` or etcd for distributed deployments.
- Lock files (`.lock`) accumulate — add a cleanup step or use `tmp` directories.

---

## 5. Solution 2 — Path Separation

### 5.1 Concept

Eliminate sharing entirely by giving each session its own write path. Merge later during a quiet window.

### 5.2 Directory Layout

```
memory/
├── dm-2026-03-15.md         ← written only by direct-message session
├── group-2026-03-15.md      ← written only by group-chat session
├── agent-task-2026-03-15.md ← written only by task-runner session
└── 2026-03-15.md            ← merged nightly, read-only during the day
```

### 5.3 Session → Path Mapping

```python
# tools/session_path.py

from datetime import date
from enum import Enum


class SessionType(Enum):
    DIRECT_MESSAGE = "dm"
    GROUP_CHAT     = "group"
    TASK_RUNNER    = "agent-task"
    ORCHESTRATOR   = "orchestrator"


def daily_log_path(session_type: SessionType, base_dir: str = "memory") -> str:
    today = date.today().strftime("%Y-%m-%d")
    return f"{base_dir}/{session_type.value}-{today}.md"
```

### 5.4 Nightly Merge Script

```python
# tools/merge_daily_logs.py

import glob
import os
from datetime import date
from pathlib import Path
from file_lock_write import locked_write


def merge_logs(base_dir: str = "memory") -> None:
    today = date.today().strftime("%Y-%m-%d")
    output_path = f"{base_dir}/{today}.md"
    pattern = f"{base_dir}/*-{today}.md"

    fragments = sorted(glob.glob(pattern))
    if not fragments:
        return

    lines = [f"# {today}\n\n"]
    for fragment in fragments:
        session_label = Path(fragment).stem.replace(f"-{today}", "")
        lines.append(f"## [{session_label}]\n")
        with open(fragment, encoding="utf-8") as f:
            lines.append(f.read().strip())
        lines.append("\n\n")

    locked_write(output_path, "".join(lines), mode="overwrite")

    archive_dir = Path(base_dir) / "archive"
    archive_dir.mkdir(exist_ok=True)
    for fragment in fragments:
        os.rename(fragment, archive_dir / Path(fragment).name)


if __name__ == "__main__":
    merge_logs()
```

---

## 6. Solution 3 — Role-Based Responsibility Split

### 6.1 Concept

Assign exclusive write ownership of each file category to a single session type. No two session types should ever write the same file.

### 6.2 Ownership Table

| File | Owner | Others |
|------|-------|--------|
| `memory/YYYY-MM-DD.md` | Group-chat session (coordinator) | Read-only |
| `memory/MEMORY.md` | Group-chat session (coordinator) | Read-only |
| `state/tasks.json` | Orchestrator session | Read-only |
| `output/<task-id>.md` | Task-runner session (per task) | Read-only |
| `tmp/<session-id>/` | Each session (private) | No access |

### 6.3 Enforcement via Write Guard

```python
# tools/write_guard.py

WRITE_OWNERSHIP = {
    "memory/MEMORY.md":   "group",
    "state/tasks.json":   "orchestrator",
}

WRITE_PATTERNS = [
    ("memory/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md", "group"),
    ("output/*.md", "task-runner"),
]

import fnmatch


def assert_write_allowed(file_path: str, session_type: str) -> None:
    if file_path in WRITE_OWNERSHIP:
        owner = WRITE_OWNERSHIP[file_path]
        if session_type != owner:
            raise PermissionError(
                f"Session '{session_type}' cannot write '{file_path}'. Owner: '{owner}'"
            )
        return

    for pattern, owner in WRITE_PATTERNS:
        if fnmatch.fnmatch(file_path, pattern):
            if session_type != owner:
                raise PermissionError(
                    f"Session '{session_type}' cannot write '{file_path}'. "
                    f"Pattern '{pattern}' is owned by '{owner}'"
                )
            return
```

---

## 7. Putting It Together

```python
# agent/memory_writer.py

from tools.write_guard import assert_write_allowed
from tools.file_lock_write import locked_write
from tools.session_path import daily_log_path, SessionType
from datetime import datetime


class MemoryWriter:
    def __init__(self, session_type: SessionType):
        self.session_type = session_type

    def log(self, message: str) -> None:
        """Append a timestamped entry to this session's daily log."""
        path = daily_log_path(self.session_type)          # L2: path separation
        assert_write_allowed(path, self.session_type.value)  # L3: ownership check
        ts = datetime.now().strftime("%H:%M")
        locked_write(path, f"- {ts} {message}\n")         # L1: file locking

    def update_long_term_memory(self, content: str) -> None:
        """Update MEMORY.md — only allowed for the group session."""
        path = "memory/MEMORY.md"
        assert_write_allowed(path, self.session_type.value)  # raises if not group
        locked_write(path, content, mode="overwrite")


# Usage
writer = MemoryWriter(SessionType.DIRECT_MESSAGE)
writer.log("Completed user onboarding task")
# → writes to memory/dm-2026-03-15.md with file lock
```

---

## 8. Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Writing shared files without a lock | Silent data loss under concurrent load | Always use `locked_write` for shared files |
| Using the same daily log path in all sessions | Guaranteed race conditions at scale | Apply path separation from day one |
| Assuming sequential execution | Works in dev, breaks in production when parallelism increases | Design for concurrency, not against it |
| Forgetting to release locks on exception | Deadlock — all writers block forever | Use `try/finally` or context managers to guarantee unlock |
| Locking the data file directly | File corruption if the write fails mid-way | Lock a separate `.lock` file; write to data file only after lock is held |
| Skipping write guard in sub-agents | Sub-agents silently overwrite coordinator's files | Enforce `assert_write_allowed` in every agent's write path |

---

## 9. Quick Reference

```
Problem:   Two agents write the same file → one write is lost (silent)
Root cause: read-modify-write is not atomic; no built-in coordination

Fix L1 — File Locking
  locked_write(path, content)           # serialize with fcntl.flock

Fix L2 — Path Separation
  daily_log_path(SessionType.DM)        # → memory/dm-YYYY-MM-DD.md
  merge_logs()                          # nightly merge to canonical file

Fix L3 — Responsibility Split
  assert_write_allowed(path, session)   # raises if wrong session writes
  WRITE_OWNERSHIP = { "memory/MEMORY.md": "group", ... }

Combined usage:
  1. assert_write_allowed(path, session_type)   # check ownership
  2. locked_write(path, content)                # acquire lock, write, release
  3. Use session-specific paths for daily logs  # no sharing = no conflict
```

---

*Part of the [soul-first-agent](https://github.com/eric-wei-ai/soul-first-agent) framework — production-tested patterns for deploying AI employees in enterprise environments.*
