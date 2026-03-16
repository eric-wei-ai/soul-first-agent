# Multi-Session Concurrent Operations

When you deploy an AI employee that handles both direct messages and group chats, you are running multiple independent sessions against a shared filesystem. This document covers the coordination patterns that prevent data corruption and keep sessions aware of each other's work.

## The Problem

Each conversation with your AI employee spawns a separate session. A DM is one session. A group chat is another. Both sessions read and write to the same workspace directory — the same memory files, the same task lists, the same daily logs.

Without coordination, you get predictable failures:

- Two sessions append to the same daily log at the same instant. One write overwrites the other.
- A task gets picked up in a DM session, but the group chat session has no record of it. Someone asks "what's the status?" and the AI says "no active tasks."
- Both sessions update `MEMORY.md` simultaneously. The file ends up with a corrupted merge of both writes.

This is not a theoretical risk. It happens reliably once more than one person interacts with the same AI employee, or once you start mixing DM task execution with group chat coordination.

## DM vs Group Chat Division of Labor

The fix starts with a clear division: each session type has a primary responsibility.

**DM session** is the worker. It executes specific tasks — deep analysis, writing code, long-running operations. When someone needs something done, they assign it in a DM.

**Group chat session** is the coordinator. It handles status updates, multi-person discussions, and quick Q&A. It reads from memory files to report on progress but does not execute heavy tasks.

**Critical rule**: two sessions must NOT simultaneously write to core memory files without a locking mechanism.

| Operation | DM Session | Group Session |
|-----------|-----------|---------------|
| Task execution | Primary | No |
| Status reporting | No | Primary |
| Daily log writes | Yes (task logs) | Yes (interaction logs) |
| MEMORY.md updates | Yes (via file lock) | Yes (via file lock) |
| Code/file creation | Yes | No |
| Todo creation | Yes | Yes |

This table is a convention, not a technical enforcement. The enforcement comes from file locking and path separation, covered next.

## File Locking to Prevent Conflicts

Any write to shared files MUST use a file lock. Here is the wrapper script that every session uses:

```python
#!/usr/bin/env python3
"""File lock wrapper for safe concurrent writes."""
import fcntl
import argparse
from pathlib import Path

def locked_write(filepath: str, content: str, mode: str = "append"):
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    open_mode = "a" if mode == "append" else "w"
    with open(path, open_mode) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath")
    parser.add_argument("content")
    parser.add_argument("--mode", choices=["append", "overwrite"], default="append")
    args = parser.parse_args()
    locked_write(args.filepath, args.content, args.mode)
```

The rule is simple: ALL writes to `memory/*.md` files MUST go through this wrapper. Direct writes are prohibited.

```bash
# Correct — uses exclusive file lock
python3 tools/file_lock_write.py memory/2026-03-15.md "- 14:00 Task completed" --mode append

# Wrong — race condition risk
echo "- 14:00 Task completed" >> memory/2026-03-15.md
```

The `fcntl.LOCK_EX` call acquires an exclusive lock. If another process already holds the lock, the caller blocks until it is released. This guarantees that only one session writes at a time. The `finally` block ensures the lock is always released, even if the write raises an exception.

## Path Separation Strategy

File locking solves corruption but does not solve readability. When both sessions append to the same daily log, the entries interleave in ways that are hard to follow. An optional upgrade is to separate write paths by session type:

- DM writes to: `memory/dm-YYYY-MM-DD.md`
- Group chat writes to: `memory/group-YYYY-MM-DD.md`
- A nightly merge job (e.g., 22:00) combines both into: `memory/YYYY-MM-DD.md`

With path separation, file locking is still recommended (a single session could theoretically race with itself on rapid successive calls), but the contention window drops to near zero.

Here is the merge script:

```bash
#!/bin/bash
# Nightly merge of session-specific logs into unified daily log
DATE=$(date +%Y-%m-%d)
MEMORY_DIR="memory"
MERGED="${MEMORY_DIR}/${DATE}.md"

echo "# ${DATE}" > "${MERGED}"
echo "" >> "${MERGED}"

if [ -f "${MEMORY_DIR}/dm-${DATE}.md" ]; then
    echo "## DM Session" >> "${MERGED}"
    cat "${MEMORY_DIR}/dm-${DATE}.md" >> "${MERGED}"
    echo "" >> "${MERGED}"
fi

if [ -f "${MEMORY_DIR}/group-${DATE}.md" ]; then
    echo "## Group Session" >> "${MERGED}"
    cat "${MEMORY_DIR}/group-${DATE}.md" >> "${MERGED}"
    echo "" >> "${MERGED}"
fi

# Archive session-specific files
mkdir -p "${MEMORY_DIR}/archive"
[ -f "${MEMORY_DIR}/dm-${DATE}.md" ] && mv "${MEMORY_DIR}/dm-${DATE}.md" "${MEMORY_DIR}/archive/"
[ -f "${MEMORY_DIR}/group-${DATE}.md" ] && mv "${MEMORY_DIR}/group-${DATE}.md" "${MEMORY_DIR}/archive/"
```

Schedule this with cron or your preferred task runner. The merged file becomes the single source of truth for that day's activity.

## Cross-Session Information Sync

Sessions cannot see each other's conversation history. The DM session has zero visibility into what was said in the group chat, and vice versa. The ONLY reliable bridge between sessions is the filesystem.

This means three things in practice:

**Before starting a task**, read relevant memory files to check if the other session has context. Maybe the group chat already discussed requirements. Maybe the DM session already completed half the work. The memory files are the only way to know.

**After completing a task**, write results to memory files immediately. Do not wait for the conversation to end. Do not assume someone will ask for a status update. The write happens as part of task completion, not as a follow-up.

**When switching context between sessions**, always re-brief with full context. Never assume continuity.

Here are the anti-patterns that cause the most confusion:

- "Continue working on that thing" — the other session has no idea what "that" refers to. Instead: "Continue the security audit — last completed step was scanning agent definitions, 50 of 154 done."
- Assuming the DM session knows what was discussed in group chat — it does not. Instead: write a summary to `memory/` after important group discussions so any session can read it.
- Relying on conversation memory for task state — conversation memory is session-scoped and ephemeral. Task progress must live in files.

## Operator Best Practices

The human working with a multi-session AI employee should follow these guidelines:

**One window, one responsibility.** Use the DM for task execution. Use the group chat for coordination and status. Do not mix them. If you start assigning tasks in the group chat, you lose the clean division of labor and increase the chance of write conflicts.

**Do not fire multiple tasks in rapid succession.** Send a task, wait for acknowledgment, then send the next one. The AI employee executes sequentially within a session — sending three tasks at once does not make them run in parallel, it just makes the queue harder to track.

**Use explicit status triggers.** Say "current status" or "task list" to get a status report. The AI reads memory files to construct its answer, so the report reflects all sessions' work, not just the current conversation.

**Task progress lives in files, not in conversation memory.** If you close the chat window and reopen it, the AI should be able to reconstruct full context from the filesystem alone. If it cannot, your logging discipline has a gap.

## Execution Rules for the AI Employee

These are the rules that the AI employee itself must follow in a multi-session environment:

1. **Receive task** — immediately log to the daily file. The log entry includes the task description, who assigned it, and the timestamp.
2. **Long task starting** — announce "Working on X, estimated ~Y minutes" so the operator knows the session is occupied.
3. **Task complete** — report the result in conversation AND update the daily log. Both must happen. The conversation report is for the operator's immediate awareness; the log entry is for cross-session visibility.
4. **Cross-session information** — ONLY through `memory/` files. Never rely on conversation memory for anything that another session might need to know.
5. **Sequential execution** — each session executes strictly one task at a time. No parallel tasks within a single session. If a new task arrives while one is in progress, acknowledge it and queue it, but do not interrupt the current work.

These rules are simple but they require discipline. The most common failure mode is not a technical bug — it is skipping the log write because the task felt too small to record. Every task gets logged. No exceptions.
