#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


DEFAULT_TOP = 8


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the crawled OpenClaw helper knowledge base.")
    parser.add_argument("query", help="Question, command, error text, or feature area to search for.")
    parser.add_argument("--repo-root", type=Path, default=find_repo_root(Path.cwd()))
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    kb_dir = args.repo_root / "data" / "openclaw"
    commands = load_json(kb_dir / "commands.json")
    pages = load_json(kb_dir / "pages.json")

    results = {
        "commands": rank_records(args.query, commands, ["command", "category", "source_url"], args.top),
        "pages": rank_records(args.query, pages, ["title", "url", "text"], args.top),
    }

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print_text_results(results)
    return 0


def find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "data" / "openclaw").exists() or (path / ".git").exists():
            return path
    return start


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing knowledge file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Expected a JSON list: {path}")
    return data


def rank_records(query: str, records: list[dict[str, Any]], fields: list[str], top: int) -> list[dict[str, Any]]:
    query_terms = tokenize(query)
    if not query_terms:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        haystack = " ".join(str(record.get(field, "")) for field in fields)
        score = score_text(query_terms, haystack)
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [summarize_record(score, record) for score, record in scored[:top]]


def score_text(query_terms: list[str], text: str) -> float:
    lower = text.lower()
    text_terms = tokenize(text)
    term_counts: dict[str, int] = {}
    for term in text_terms:
        term_counts[term] = term_counts.get(term, 0) + 1

    score = 0.0
    for term in query_terms:
        count = term_counts.get(term, 0)
        if count:
            score += 2.0 + math.log(count)
        if term in lower:
            score += 0.5
    if " ".join(query_terms) in lower:
        score += 5.0
    return score


def summarize_record(score: float, record: dict[str, Any]) -> dict[str, Any]:
    summary = dict(record)
    summary["score"] = round(score, 3)
    if "text" in summary:
        summary["snippet"] = snippet(summary.pop("text"))
    return summary


def snippet(text: str, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower())


def print_text_results(results: dict[str, list[dict[str, Any]]]) -> None:
    print("Commands")
    for item in results["commands"]:
        safety = []
        if item.get("writes_config"):
            safety.append("writes config")
        if item.get("destructive"):
            safety.append("destructive")
        suffix = f" ({', '.join(safety)})" if safety else ""
        print(f"- {item['command']}{suffix}")
        print(f"  Source: {item['source_url']}")

    print("\nDocs")
    for item in results["pages"]:
        print(f"- {item.get('title', item.get('url'))}")
        print(f"  URL: {item.get('url')}")
        if item.get("snippet"):
            print(f"  {item['snippet']}")


if __name__ == "__main__":
    raise SystemExit(main())
