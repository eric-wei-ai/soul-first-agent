# Three-Layer Memory Architecture

Your AI employee has amnesia. Every single conversation starts from zero. The context window — that rolling buffer of tokens the model can see — vanishes the moment the session ends. No matter how brilliant the reasoning was, no matter how many corrections you made, it is all gone.

The single most valuable investment you can make when building an AI agent is a **file-based memory system**. Not a vector database. Not a fine-tune. Files on disk, version-controlled, human-readable, and editable. Everything else is optimization on top of this foundation.

This document describes the three-layer memory architecture that has proven reliable in production deployments handling thousands of tasks per week.

---

## The Three Layers

### Layer 1: Session Memory (Conversation Context)

This is what the model can see right now — the messages in the current conversation, any files it has read, the system prompt. It lives entirely in RAM (the context window) and disappears when the session ends.

**Good for:**
- Working state and intermediate reasoning
- Current task details and step-by-step plans
- Temporary scratch calculations

**Bad for:**
- Anything that needs to survive past the current conversation
- Corrections, lessons learned, or facts about the world
- Team preferences, project status, or recurring patterns

Session memory is useful but unreliable. Treat it as a whiteboard that gets erased every night.

### Layer 2: Daily Log (`memory/YYYY-MM-DD.md`)

One file per day. Append-only during the day. This is the workhorse of the memory system.

**What it records:** events, decisions, errors, corrections, learnings — anything worth knowing tomorrow.

**Format:** timestamp + event. Keep it dead simple. No metadata bloat, no JSON wrappers, no tags. Plain markdown that a human can scan in ten seconds.

```markdown
# 2026-03-15

- 14:00 Set up knowledge base, first successful tool execution
- 15:00 Security test: 10 rounds, 9 passed, 1 needs improvement
- 16:30 Created 3 team todos, all confirmed by operator
- 17:15 Correction: weekly reports go out Monday, not Friday — updated MEMORY.md
- 18:00 Error: tried to access restricted endpoint, blocked by guardrail. Logged for review.
```

**Retention rules:**
- Logs older than 7 days get moved to `memory/archive/`
- A single day log exceeding **50KB** triggers a warning — this is context rot risk. If one day generates that much text, most of it is noise.

The daily log is the catch-all. When in doubt, write here.

### Layer 3: Long-term Memory (`memory/MEMORY.md`)

A single file. Curated, not appended. Updated weekly (or when corrections happen).

This file holds **facts that stay true across days**: team structure, project status, hard constraints, communication preferences, lessons learned from past mistakes.

```markdown
# Long-term Memory

## Team
- Engineering lead prefers async communication
- Design reviews happen every Thursday at 14:00
- Deploy freezes: last 3 days of each quarter

## Hard Constraints
- Never execute destructive operations without explicit confirmation
- All external API calls require rate limiting
- Budget alerts at 80% threshold, hard stop at 95%

## Lessons Learned
- Batch processing jobs that exceed 30 minutes should be split
- Error messages must include the operation that failed, not just the error code
- When formatting reports, use tables for > 3 items, bullet lists otherwise
```

**Critical rules for MEMORY.md:**
- Must stay under **20KB**. Bloated long-term memory is worse than no memory — it becomes noise that dilutes the signal.
- Outdated information must be **deleted**, not just appended over. If the deploy schedule changes, remove the old one.
- Weekly review cycle: read through daily logs from the past week, extract key learnings, update MEMORY.md, prune anything stale.

---

## Write Rules

These rules determine where information goes. They should be baked into your agent's system prompt.

| Trigger | Action |
|---|---|
| Operator says "remember this" | Write to daily log |
| Corrected on an error | Write to daily log **AND** update MEMORY.md |
| Learned new knowledge | Write to daily log |
| Not sure where to write | Daily log (it is the catch-all) |
| **NEVER** | Only "remember" in conversation context |

The last rule is the most important. If the agent says "I'll remember that" but does not write to a file, it has done nothing. The memory will vanish with the session. Every "remember" must produce a file write.

---

## What NOT to Record

Some things must never appear in memory files, regardless of layer:

- **Passwords, API keys, tokens, credentials** — never, under any circumstance
- **Sensitive personal information** — health data, financial details, private communications
- **Ephemeral task state** that will not matter tomorrow — intermediate calculation steps, draft formatting attempts, retry counts

If you are unsure whether something is sensitive, err on the side of not recording it. Memory files are often version-controlled and shared across systems.

---

## File Locking for Concurrent Access

When multiple sessions share the same filesystem — which is common in production — concurrent writes to memory files cause corruption. Two sessions appending to the same daily log at the same instant will interleave bytes and produce garbage.

The solution is a file lock wrapper. This uses POSIX `flock`, which is available on every Unix system and handles the coordination at the kernel level.

```python
#!/usr/bin/env python3
"""Safe concurrent file writes using flock."""
import fcntl
import argparse
import sys
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

Usage from your agent's tool layer:

```bash
python3 tools/file_lock_write.py memory/2026-03-15.md "- 14:00 Task completed" --mode append
```

For overwriting MEMORY.md during weekly reviews:

```bash
python3 tools/file_lock_write.py memory/MEMORY.md "$(cat updated_memory.md)" --mode overwrite
```

Every memory write your agent performs should go through this wrapper. Direct file writes are a race condition waiting to happen.

---

## Memory Health Checks

Run these checks on a schedule (daily is fine) and surface warnings to the operator:

| Check | Threshold | Action |
|---|---|---|
| Daily log file size | > 50KB | Alert: context rot risk. Review and trim. |
| MEMORY.md file size | > 20KB | Needs pruning. Schedule a review. |
| Number of knowledge files | > 50 | Suggest consolidation into fewer, focused files. |
| Daily logs older than 7 days | Any | Archive to `memory/archive/`. |

A simple health check script:

```bash
#!/bin/bash
# memory_health.sh — run daily

MEMORY_DIR="memory"

# Check daily log size
TODAY=$(date +%Y-%m-%d)
if [ -f "$MEMORY_DIR/$TODAY.md" ]; then
    SIZE=$(wc -c < "$MEMORY_DIR/$TODAY.md")
    if [ "$SIZE" -gt 51200 ]; then
        echo "WARNING: Today's log is ${SIZE} bytes (> 50KB). Context rot risk."
    fi
fi

# Check MEMORY.md size
if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
    SIZE=$(wc -c < "$MEMORY_DIR/MEMORY.md")
    if [ "$SIZE" -gt 20480 ]; then
        echo "WARNING: MEMORY.md is ${SIZE} bytes (> 20KB). Needs pruning."
    fi
fi

# Archive old logs
find "$MEMORY_DIR" -maxdepth 1 -name "????-??-??.md" -mtime +7 -exec mv {} "$MEMORY_DIR/archive/" \;
```

---

## Context Rot Detection

Context rot is what happens when your agent's effective memory degrades over time. The model is still running, still generating tokens, but the quality of its decisions is silently declining. Here are five symptoms to watch for:

1. **Forgets hard constraints.** The agent executes actions it was explicitly told never to perform. This is the most dangerous symptom — it means safety-critical information has fallen out of effective context.

2. **Output format drifts.** Reports that were consistently formatted start arriving in different structures. Tables become bullet lists. Headers disappear. The agent is losing its grip on established patterns.

3. **Asks questions that were already answered.** If an operator provided a preference three days ago and the agent asks again, the daily logs are not being read at session start, or the information never made it to MEMORY.md.

4. **Behavior shifts from cautious to reckless.** Early in deployment, agents tend to be conservative — asking for confirmation, flagging uncertainties. If that caution disappears without explanation, context that was reinforcing careful behavior has been lost.

5. **Token consumption spikes.** A sudden increase in tokens per task often means the agent is doing redundant work — re-reading files it already processed, re-deriving conclusions it already reached — because it has lost track of what it already knows.

When you detect these symptoms, the fix is almost always the same: review MEMORY.md for staleness, check that daily logs are being written and read, and verify that the session startup routine loads the right context. Memory systems do not fail dramatically. They degrade quietly until someone notices the output has gone wrong.

---

## Summary

Files are memory. Context is a whiteboard. Build the three layers — session, daily log, long-term — and enforce the write rules from day one. Everything else in your agent architecture depends on this foundation working reliably.
