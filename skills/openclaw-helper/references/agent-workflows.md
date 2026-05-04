# OpenClaw Helper Agent Workflows

## Useful User Prompts

- "Use $openclaw-helper to find the command for adding a Telegram channel."
- "Use $openclaw-helper to debug why my OpenClaw gateway is not responding."
- "Use $openclaw-helper to check whether our OpenClaw command knowledge is stale."
- "Use $openclaw-helper to explain this OpenClaw config field."
- "Use $openclaw-helper to build a safe setup checklist for OpenClaw on a new machine."

## Intent Routing

- Setup/install: search for `onboard`, `setup`, `doctor`, `dashboard`, `gateway`.
- Provider/model issues: search for `models`, provider name, auth, credential, status.
- Channel issues: search for the channel name plus `gateway`, `sessions`, `logs`.
- Agent behavior: search for `agents`, `skills`, `plugins`, `sessions`, model routing.
- Browser/node/mobile: search for `browser`, `nodes`, `device`, `mobile`.
- Automation: search for `cron`, `hooks`, `tasks`, `schedule`.
- Security: search for `secrets`, `allowlist`, `tokens`, `auth`, `credentials`.

## Answer Shapes

CLI command answer:

```text
Use:
<command>

This does <short explanation>. It is <read-only/config-changing/destructive>.
Source: <source_url>
```

Troubleshooting answer:

```text
Start with these read-only checks:
1. <command>
2. <command>

If that confirms <condition>, the next state-changing step is <command>.
Source: <source_url>
```

Refresh answer:

```text
Run:
python3 -m openclaw_helper_agent.crawler refresh --check

Exit code 0 means no generated knowledge changed. Exit code 1 means the docs changed and the agent KB should be refreshed/re-indexed.
```

## Indexing Plan

For a full helper agent, use both retrieval layers:

1. Exact command lookup over `commands.json`
2. Semantic search over `pages.json`

The agent should route first to exact command lookup when the user asks "what command" or provides a CLI-like phrase. It should route to semantic page retrieval when the user asks conceptual questions, setup planning, or troubleshooting.
