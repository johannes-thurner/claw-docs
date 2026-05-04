---
name: openclaw-helper
description: Use when helping users with OpenClaw setup, CLI commands, configuration, providers/models, gateway, channels, agents, sessions, browser/nodes, plugins/skills, cron/tasks, troubleshooting, or keeping an OpenClaw helper-agent knowledge base up to date from crawled docs.
---

# OpenClaw Helper

## Core Workflow

1. Use the local knowledge base before answering from memory:

```bash
python3 skills/openclaw-helper/scripts/search_openclaw_kb.py "user question or command"
```

2. Prefer command records from `data/openclaw/commands.json` for exact CLI syntax. Use `data/openclaw/pages.json` for explanations and feature context.
3. Cite `source_url` values when giving OpenClaw-specific guidance.
4. If the user asks about the latest docs or a command is missing, refresh first:

```bash
python3 -m openclaw_helper_agent.crawler refresh
```

5. For automation/staleness checks, use:

```bash
python3 -m openclaw_helper_agent.crawler refresh --check
```

## Response Pattern

For CLI help, answer with:

- the recommended command
- what it does
- important options or placeholders to fill
- whether it changes config or may be destructive
- source docs URL

For troubleshooting, proceed in this order:

1. Identify the OpenClaw area: install, gateway, model/provider, channel, session, agent, node/browser, plugin/skill, cron/task, auth/security, or config.
2. Search the KB for the error text and feature area.
3. Start with read-only diagnostic commands.
4. Ask before suggesting commands marked destructive.
5. Give a short next-step ladder rather than a giant command dump.

## Safety Rules

- Treat `destructive: true` command records as approval-required.
- Treat `writes_config: true` command records as state-changing; explain the effect before recommending them.
- Prefer read-only status/list/show/log/doctor commands for first diagnostics.
- Do not invent OpenClaw commands. If the KB does not contain a command, say that and either refresh or cite the closest docs page.

## Knowledge Files

- `data/openclaw/commands.json`: extracted CLI inventory with category, safety flags, and source URL.
- `data/openclaw/pages.json`: crawled docs text with titles and hashes.
- `data/openclaw/crawl_report.json`: crawl metadata, counts, errors, and change state.

Use `references/agent-workflows.md` for examples of how to turn user intent into agent behavior.
