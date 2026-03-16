# soul-first-agent

> Design your AI employee from the soul outward.

A practical playbook for building production-grade AI employees using [OpenClaw](https://github.com/openclaw/openclaw) — based on real deployment experience.

## The Core Idea

Most AI agent setups start with tools and capabilities. We start with **identity and values** — the `SOUL.md` file that defines who your AI employee is, what it cares about, and what it will never do.

```
SOUL.md → identity, values, security boundaries
AGENTS.md → operating procedures, workflows  
IDENTITY.md → name, personality, communication style
```

Build the soul first. Everything else follows.

## What's Inside

| File | What it covers |
|------|----------------|
| `SOUL-template.md` | Reusable template for defining AI employee identity |
| `docs/soul-design.md` | How to design a SOUL.md that actually works |
| `docs/security-design.md` | SecOps review mechanism — human oversight for high-risk actions |
| `docs/memory-system.md` | Three-layer memory architecture (session / daily log / long-term) |
| `docs/agent-onboarding.md` | How to safely evaluate and install third-party agents |
| `docs/multi-session.md` | Running multiple AI sessions without conflicts |
| `docs/junior-soul-architecture.md` | Four-layer architecture for enterprise AI employees |
| `examples/` | Real deployment examples |
| `tools/file_lock_write.py` | Safe concurrent file writes across sessions |

## Quick Start

**1. Clone this repo**
```bash
git clone https://github.com/eric-wei-ai/soul-first-agent
```

**2. Copy the SOUL template**
```bash
cp SOUL-template.md your-project/SOUL.md
```

**3. Customize for your context**
Edit `SOUL.md` to define:
- Your AI employee's role and personality
- What it should always do
- What it must never do (security boundaries)
- How it communicates

**4. Set up memory system**
```
memory/
├── MEMORY.md          # Long-term: facts that stay true across days
└── YYYY-MM-DD.md      # Daily log: what happened today
```

**5. Add security review**
For any action with irreversible consequences, route through a SecOps sub-agent before executing. See `docs/security-design.md`.

## Key Principles

**Soul before tools.** Define identity and values before capabilities. A well-defined soul makes security easier — the AI knows what it won't do.

**Memory is files, not context.** Conversation context disappears. Write everything important to files. The memory system is your AI's persistent brain.

**Security is architecture, not prompts.** Prompt guardrails help but aren't sufficient. Build security into the workflow: human approval gates, SecOps review, file locks.

**Parallel sessions need coordination.** Multiple AI sessions on the same machine share the same filesystem. Use file locks and clear ownership rules to prevent conflicts.

## What We Learned Building This

- A SOUL.md that's too long becomes noise. Keep the core under 500 tokens; use knowledge files for the rest.
- Security boundaries work best when the AI internalizes *why*, not just *what*.
- The memory system is the single most valuable investment — more than any tool integration.
- Third-party agent libraries need security review before installation. We audited 154 agents and found 2 that required modification.
- Multi-session coordination is a real problem once you have more than one person using the same AI employee.

## License

MIT
