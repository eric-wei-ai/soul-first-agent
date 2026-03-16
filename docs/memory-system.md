# Memory System — Three-Layer Architecture

## The Problem
AI agents wake up fresh every session. Without a memory system, every conversation starts from zero.

## Three Layers

### Layer 1: Daily Logs (Raw)
- Path: `memory/YYYY-MM-DD.md`
- One file per day, append-only
- Record: events, decisions, mistakes, learnings
- Think of it as a work journal

### Layer 2: Long-Term Memory (Curated)
- Path: `memory/MEMORY.md`
- One file, periodically updated from daily logs
- Contains: distilled insights, team context, lessons learned
- Review and clean up weekly

### Layer 3: Knowledge Base (Reference)
- Path: `knowledge/`
- Project docs, methodology, reference materials
- Not auto-injected into system prompt (read on demand)
- Can grow large without affecting response speed

## Key Rules
- "I'll remember that" without writing to a file = forgotten
- Daily logs are the trash can — write anything, sort later
- MEMORY.md is curated — only keep what matters across days

_Content to be expanded by contributors._
