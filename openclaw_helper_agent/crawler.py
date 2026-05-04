from __future__ import annotations

import argparse
import dataclasses
import hashlib
import html.parser
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_INDEX_URL = "https://docs.openclaw.ai/llms.txt"
DEFAULT_OUTPUT_DIR = Path("data/openclaw")
DEFAULT_TIMEOUT_SECONDS = 30
USER_AGENT = "openclaw-helper-agent-crawler/0.1"
MAX_COMMAND_TOKENS = 18
MAX_COMMAND_LENGTH = 220


@dataclasses.dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str
    sha256: str


@dataclasses.dataclass(frozen=True)
class Command:
    command: str
    source_url: str
    category: str
    destructive: bool
    writes_config: bool


class HtmlTextParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag in {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "pre", "code"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "pre"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)
            self._parts.append(" ")

    def text(self) -> str:
        joined = "".join(self._parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in joined.splitlines()]
        return "\n".join(line for line in lines if line)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "refresh":
        return refresh(args)

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl OpenClaw docs for helper-agent knowledge.")
    subparsers = parser.add_subparsers(dest="command")

    refresh_parser = subparsers.add_parser("refresh", help="Refresh crawled OpenClaw knowledge files.")
    refresh_parser.add_argument("--index-url", default=DEFAULT_INDEX_URL)
    refresh_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    refresh_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    refresh_parser.add_argument("--max-pages", type=int, default=0, help="Limit pages for testing. 0 means unlimited.")
    refresh_parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N pages. 0 disables progress.")
    refresh_parser.add_argument("--check", action="store_true", help="Exit 1 if generated files changed.")
    return parser


def refresh(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    previous_hashes = file_hashes(output_dir, include_report=False)
    started_at = int(time.time())

    index_text = fetch_text(args.index_url, args.timeout)
    urls = discover_urls(args.index_url, index_text)
    if args.max_pages:
        urls = urls[: args.max_pages]

    pages: list[Page] = []
    errors: list[dict[str, str]] = []
    total_urls = len(urls)
    for index, url in enumerate(urls, start=1):
        try:
            raw = fetch_text(url, args.timeout)
            text = html_to_text(raw) if looks_like_html(raw) else raw
            pages.append(
                Page(
                    url=url,
                    title=extract_title(text, url),
                    text=text,
                    sha256=sha256(text),
                )
            )
        except CrawlerError as exc:
            errors.append({"url": url, "error": str(exc)})
        if args.progress_every and index % args.progress_every == 0:
            print(f"Fetched {index}/{total_urls} pages...", flush=True)

    commands = extract_commands(pages)

    write_json(output_dir / "pages.json", [dataclasses.asdict(page) for page in pages])
    write_json(output_dir / "commands.json", [dataclasses.asdict(command) for command in commands])

    current_hashes = file_hashes(output_dir, include_report=False)
    changed = previous_hashes != current_hashes
    report = {
        "index_url": args.index_url,
        "started_at": started_at,
        "page_count": len(pages),
        "command_count": len(commands),
        "errors": errors,
        "changed": changed,
        "hashes": current_hashes,
    }
    write_json(output_dir / "crawl_report.json", report)

    print(f"Crawled {len(pages)} pages and extracted {len(commands)} commands.")
    if errors:
        print(f"Finished with {len(errors)} fetch errors. See crawl_report.json.")
    if args.check and changed:
        print("Knowledge files changed.")
        return 1
    return 0


def discover_urls(index_url: str, index_text: str) -> list[str]:
    base = urllib.parse.urlparse(index_url)
    host_root = f"{base.scheme}://{base.netloc}"
    urls: set[str] = {host_root + "/", "https://docs.openclaw.ai/cli"}

    for match in re.finditer(r"https?://[^\s)>\"]+", index_text):
        url = cleanup_url(match.group(0))
        if is_openclaw_docs_url(url):
            urls.add(url)

    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", index_text):
        href = cleanup_url(match.group(1))
        url = urllib.parse.urljoin(host_root, href)
        if is_openclaw_docs_url(url):
            urls.add(url)

    return sorted(urls)


def extract_commands(pages: Iterable[Page]) -> list[Command]:
    commands: dict[tuple[str, str], Command] = {}
    command_pattern = re.compile(r"\bopenclaw(?:\s+(?!openclaw\b)[A-Za-z0-9_./:@|<>{}\[\]=,*+-]+)+")

    for page in pages:
        category = category_from_url(page.url)
        for match in command_pattern.finditer(page.text):
            command = normalize_command(match.group(0))
            if not command:
                continue
            commands[(command, page.url)] = Command(
                command=command,
                source_url=page.url,
                category=category,
                destructive=is_destructive(command),
                writes_config=writes_config(command),
            )

        if page.url.rstrip("/").endswith("/cli"):
            for command in extract_command_tree_entries(page.text):
                commands[(command, page.url)] = Command(
                    command=command,
                    source_url=page.url,
                    category=category_from_command(command),
                    destructive=is_destructive(command),
                    writes_config=writes_config(command),
                )

    return sorted(commands.values(), key=lambda item: (item.command, item.source_url))


def extract_command_tree_entries(text: str) -> list[str]:
    entries: set[str] = set()
    in_tree = False
    stack: list[tuple[int, str]] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if "openclaw [--dev]" in line:
            in_tree = True
            stack = [(0, "openclaw")]
            continue
        if in_tree and not line.strip():
            continue
        if in_tree and re.match(r"^[A-Z][A-Za-z ]+$", line.strip()):
            break
        if not in_tree:
            continue

        stripped = line.strip(" `")
        if not stripped or stripped.startswith("#"):
            continue
        indent = max(len(line) - len(line.lstrip()), 0)
        token = stripped.split()[0]
        token = token.split("|")[0]
        token = token.strip()
        if not re.match(r"^[a-z][a-z0-9-]*$", token):
            continue

        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else "openclaw"
        command = f"{parent} {token}"
        entries.add(command)
        stack.append((indent, command))

    return sorted(entries)


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return raw.decode(encoding, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CrawlerError(f"Could not fetch {url}: {exc}") from exc


def html_to_text(raw: str) -> str:
    parser = HtmlTextParser()
    parser.feed(raw)
    return parser.text()


def looks_like_html(raw: str) -> bool:
    sample = raw[:500].lower()
    return "<html" in sample or "<!doctype html" in sample


def extract_title(text: str, url: str) -> str:
    for line in text.splitlines():
        clean = line.strip("# ").strip()
        if clean:
            return clean[:160]
    return url


def cleanup_url(url: str) -> str:
    return url.strip().rstrip(".,;")


def is_openclaw_docs_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc == "docs.openclaw.ai"


def normalize_command(command: str) -> Optional[str]:
    command = command.strip().strip("`")
    command = re.sub(r"\s+", " ", command)
    command = command.rstrip(".,;:")
    command = truncate_to_command_tokens(command)
    if len(command) > MAX_COMMAND_LENGTH or len(command.split()) > MAX_COMMAND_TOKENS:
        return None
    if command in {"openclaw"}:
        return None
    return command


def truncate_to_command_tokens(command: str) -> str:
    parts = command.split()
    if not parts:
        return command

    tokens = [parts[0]]
    for token in parts[1:]:
        clean = token.strip().rstrip(".,;:")
        if clean == "openclaw" or not is_command_token(clean):
            break
        tokens.append(clean)
    return " ".join(tokens)


def is_command_token(token: str) -> bool:
    if not token:
        return False
    if token.startswith(("-", "<", "[", "{")):
        return True
    if "|" in token:
        return all(is_command_token(part) for part in token.split("|") if part)
    return bool(re.match(r"^[a-z0-9_./:@=,*+-]+$", token))


def category_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/")
    if not path:
        return "overview"
    parts = path.split("/")
    if parts[0] in {"cli", "start", "providers", "channels", "concepts"}:
        return parts[0]
    return parts[-1].removesuffix(".md")


def category_from_command(command: str) -> str:
    parts = command.split()
    return parts[1] if len(parts) > 1 else "cli"


def is_destructive(command: str) -> bool:
    destructive_words = {"reset", "uninstall", "remove", "rm", "delete", "clear", "purge", "revoke", "reject"}
    return bool(destructive_words.intersection(command_words(command)))


def writes_config(command: str) -> bool:
    write_words = {
        "add",
        "approve",
        "configure",
        "create",
        "edit",
        "disable",
        "enable",
        "install",
        "login",
        "logout",
        "rename",
        "set",
        "unset",
        "update",
    }
    return bool(write_words.intersection(command_words(command)))


def command_words(command: str) -> set[str]:
    words: set[str] = set()
    for token in command.split():
        words.update(part for part in token.split("|") if part)
    return words


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hashes(output_dir: Path, include_report: bool = True) -> dict[str, str]:
    if not output_dir.exists():
        return {}
    hashes: dict[str, str] = {}
    for path in sorted(output_dir.glob("*.json")):
        if not include_report and path.name == "crawl_report.json":
            continue
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


class CrawlerError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
