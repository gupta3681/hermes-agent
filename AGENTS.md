# Jarvis — repository guide for people and agents

## What we are building

Jarvis is our fork of Nous Research's Hermes Agent. The intended product is an agent that
lives in WhatsApp and works naturally with multiple people. Hermes supplies the agent loop,
tools, memory, scheduling, and messaging infrastructure; we will design Jarvis's architecture
and own its behavior contracts here.

**Current state:** an upstream-based fork with Jarvis guidance, baseline contract tests, and the standalone
frontends removed.
The earlier personal harness and multiplayer prototype are separate repositories/branches;
their changes are not automatically part of this checkout. The mobile app is not the current
product focus. Do not claim that signup, per-user memory isolation, roles, account provisioning,
or a hosted service already exists simply because an upstream primitive exists.

**Architecture is still being decided with Aryan.** Shared group conversations are the intended
experience. Ownership of group memory, private-DM behavior, membership roles, action approvals,
and runtime isolation need explicit design decisions. Do not silently choose those policies,
import earlier patches, or redesign the core while doing documentation or test work.

## Start here

1. Read this file and `docs/jarvis/TESTING.md`.
2. Check `git status` and your branch before changing anything. Preserve others' edits.
3. Find the existing implementation and read its area's `AGENTS.md` using the map below.
4. Explain the behavior being changed and its verification; keep changes reviewable.
5. Run the relevant tests through `scripts/run_tests.sh`, then `python scripts/check`.

The initial working branch is `codex/jarvis-architecture`. `origin` is our fork;
`upstream` is NousResearch/hermes-agent. Preserve upstream history, MIT license, and attribution.
This fork is public: use synthetic fixtures; never commit tokens, phone numbers belonging to
real people, personal memory, chats, browser profiles, production configuration, or private
harness exports. Do not operate on the live VPS as a side effect of local development.

## Repository map

| Area | What it does | Guidance to read before editing |
|---|---|---|
| `run_agent.py`, `agent/` | Agent facade and conversation/turn phases, memory, prompts | `agent/AGENTS.md` |
| `gateway/` | Message ingress, identities, sessions, routing, approvals | `gateway/AGENTS.md` |
| `plugins/platforms/whatsapp/` | WhatsApp transport integration | `plugins/AGENTS.md`, `gateway/AGENTS.md` |
| `gateway/session.py`, `gateway/session_identity.py` | Conversation keys and trusted routing identity | `gateway/AGENTS.md` |
| `hermes_state.py`, `hermes_state_*.py` | Persistent sessions and state | root guide plus nearby guidance |
| `tools/`, `model_tools.py`, `toolsets.py` | Tool execution, registry, tool selection | `tools/AGENTS.md` |
| `hermes_cli/`, `cli.py` | CLI, config, setup, profiles | `hermes_cli/AGENTS.md` |
| `cron/` | Scheduled tasks and delivery | `cron/AGENTS.md` |
| `tests/` | Upstream tests and our `test_jarvis_*` contracts | `tests/AGENTS.md` |
| `pm/`, `pyproject.toml` | Managed environments and dependencies | `pm/AGENTS.md` |
| `hermes_platform/` | OS facts and executable lookup | `hermes_platform/AGENTS.md` |
| `tui_gateway/`, `apps/shared/` | Shared backend RPC and generated client contracts; retained | `tui_gateway/AGENTS.md` |
| `skills/`, `optional-skills/` | Reusable agent workflows | `skills/AGENTS.md` |
| `scripts/build/`, `docker/build_agent.py` | Shared headless payload builds and assembly | `scripts/build/README.md`, `pm/AGENTS.md` |
| `docs/jarvis/` | Our project guidance and testing scope | this file |

Many root modules are facades. Search sibling modules for behavior rather than growing the
facade. Use `rg` and `rg --files`; follow production imports when selecting a test patch seam.
The upstream guide as it existed when this guide was introduced is preserved at
`docs/jarvis/UPSTREAM_AGENT_GUIDE.md`; live area guides remain authoritative for their areas.

## Engineering rules we retain

- Preserve conversation prompt caching: do not rewrite past messages, replace cached system
  prompts, or switch toolsets mid-conversation. Respect upstream compression semantics.
- Prefer existing capabilities, CLI/skills, or plugins over adding core model tools. Never
  duplicate a subsystem without first checking the existing interfaces and consumers.
- Use `get_hermes_home()` for runtime state. A session key or a different directory is not
  an OS security boundary. Do not claim full tenant isolation from routing tests.
- Bind the correct profile scope for background tasks, thread hops, callbacks, and child
  processes. Never infer identity/authority from a display name or message text.
- Shared chat history does not grant access to someone else's credentials or private data.
  Approval and authorization rules must be enforced in code, not just prompt instructions.
- Use real code paths and temporary state for routing/config/authorization tests. Mock only
  external effects or narrow collaborators, not the behavior the assertion is meant to prove.
- Do not send messages, call paid models, link accounts, deploy, restart services, or change
  the live personal assistant as part of ordinary tests.
- Use the managed dependency workflow in `pm/AGENTS.md`; no raw pip/uv mutations of Hermes
  environments. Preserve dependency bounds/pins and lockfile consistency.
- Keep tests behavioral: no source-text assertions, frozen implementation snapshots, blanket
  skips, or automatic passing placeholders for missing features.
- Follow `SECURITY.md` for vulnerability reporting. Never publish private exploit details in
  a normal issue/PR. Review new shared-context paths for actual authorization boundaries.
- Run `python scripts/check` for blocking checks; do not disable rules to get green results.

## Tests we own

Our tests use the `test_jarvis_*` filename prefix and stay under the source-matching test area.
They call real Hermes interfaces and describe Jarvis's requirements in plain language. This
makes our intended behavior easy to find without copying or replacing the upstream suite.

```sh
scripts/run_tests.sh tests/gateway/test_jarvis_session_contracts.py tests/gateway/test_jarvis_whatsapp_contracts.py -q
```

These are baseline compatibility contracts, not proof that the complete Jarvis architecture
has shipped. `docs/jarvis/TESTING.md` separates verified contracts from pending product work.

## Removed product surfaces

Desktop, bootstrap installer, Ink terminal UI, browser dashboard frontend, and the docs-site
build are removed. Reference docs remain under `website/docs/`. Do not restore these surfaces
as an automatic repair. Telegram, IRC, ntfy, SimpleX, BlueBubbles, SMS/Twilio, and Photon iMessage
adapters are also removed, along with Raft and the achievements dashboard plugin.
See `docs/jarvis/PRUNING.md` for retained dependencies and verification.

Desktop packaging/publication code under `scripts/bundles` is retired. Shared build code
lives in `scripts/build`; source update readers must not import publisher implementations.
