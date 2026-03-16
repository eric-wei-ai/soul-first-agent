# Soul-First Agent 🦀

> Design AI employees starting from the soul, not the code.

## What is this?

A practical guide for deploying AI agents as real team members — not chatbots. Based on production experience running an AI employee in a 5-person enterprise team via DingTalk.

**Core principle:** Define who the agent *is* before what it *does*. Start with `SOUL.md`.

## Why "Soul-First"?

Most AI agent guides start with tools, APIs, and code. This project starts with identity, values, and boundaries — because an agent without a soul is just an expensive autocomplete.

| Traditional Approach | Soul-First Approach |
|---------------------|-------------------|
| Pick model → write code → deploy | Define soul → set boundaries → deploy |
| Agent has no personality | Agent has opinions and judgment |
| Reactive (responds when asked) | Proactive (monitors, escalates, follows up) |
| Forgets everything between sessions | Persistent memory via files |
| No security model | Layered security with SecOps review |

## Quick Start

1. Copy `SOUL-template.md` to your agent's workspace as `SOUL.md`
2. Customize identity, values, and boundaries for your team
3. Read `docs/soul-design.md` for design principles
4. Set up memory system per `docs/memory-system.md`
5. Add security layer per `docs/security-design.md`

## Documentation

| Doc | Description |
|-----|-------------|
| [Soul Design](docs/soul-design.md) | How to write an effective SOUL.md |
| [Security Design](docs/security-design.md) | SecOps review mechanism, prompt injection defense |
| [Memory System](docs/memory-system.md) | Three-layer memory architecture |
| [Multi-Session](docs/multi-session.md) | Managing concurrent sessions without conflicts |
| [Agent Onboarding](docs/agent-onboarding.md) | Safely introducing external agents |
| [Junior Soul Architecture](docs/junior-soul-architecture.md) | Four-layer architecture for AI employees |

## Examples

- [DingTalk Setup](examples/dingtalk-setup/) — Enterprise deployment via Stream Mode
- [SecOps Review](examples/secops-review/) — Security audit workflow

## Key Insight

> "Rules are for yourself, not for show. Every rule you write must be enforced, or it's waste paper."

## License

MIT

---

_Born from a marathon deployment session where three collaborators — a human, a CLI agent, and a chat agent — built an AI employee from scratch in one night._
