# OpenClaw Helper Agent Knowledge Base

This repository contains a small crawler scaffold for keeping an OpenClaw helper
agent up to date with the current OpenClaw documentation and CLI surface.

## What It Does

- Reads the OpenClaw documentation index from `https://docs.openclaw.ai/llms.txt`
- Crawls OpenClaw docs pages
- Extracts likely `openclaw ...` CLI commands and examples
- Writes normalized JSON files for an agent/RAG pipeline
- Supports a `--check` mode for scheduled update detection

## Quick Start

```bash
python3 -m openclaw_helper_agent.crawler refresh
```

Generated files are written to `data/openclaw/`:

- `pages.json`: crawled documentation pages
- `commands.json`: extracted CLI command inventory
- `crawl_report.json`: crawl metadata, hashes, and change status

To check whether the local knowledge base is stale:

```bash
python3 -m openclaw_helper_agent.crawler refresh --check
```

`--check` exits with code `1` when generated knowledge files changed.

The included GitHub Actions workflow runs daily and opens a pull request when
the generated OpenClaw knowledge files change.

## Suggested Agent Flow

1. Run the crawler on a schedule.
2. Commit or publish refreshed JSON artifacts.
3. Build embeddings/search index from `pages.json`.
4. Route user intent through `commands.json` first for precise CLI help.
5. Fall back to the docs index for deeper explanations.

## Using The Skill

This repo includes a Codex skill at `skills/openclaw-helper/`.

Use it with prompts like:

```text
Use $openclaw-helper to find the safest command ladder for debugging my OpenClaw gateway.
```

```text
Use $openclaw-helper to check whether the OpenClaw helper knowledge base is stale.
```

```text
Use $openclaw-helper to explain the OpenClaw command for changing the default model.
```

The skill tells an agent to search the local command/docs knowledge base first,
cite source URLs, prefer read-only diagnostics, and ask before suggesting
destructive OpenClaw commands.
