# Multi-Session Management

## The Problem
An agent may have multiple concurrent sessions (DM + group chat). They can't see each other's conversation history.

## Solution: File-Based Bridge
- The only reliable cross-session bridge is **memory files**
- Each session writes to files, other sessions read them
- Never rely on conversation memory across sessions

## Conflict Prevention
- Use file locks for shared files
- Or separate paths: `memory/dm-YYYY-MM-DD.md` vs `memory/group-YYYY-MM-DD.md`
- Merge daily at a scheduled time

_Content to be expanded by contributors._
