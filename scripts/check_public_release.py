#!/usr/bin/env python3
"""Fail closed when a public GitHub release contains likely local secrets.

The scanner intentionally checks the tracked tree plus staged changes.  It is a
release guard, not a substitute for rotating a secret that has already leaked.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ENV_FILES = {".env.example"}
BLOCKED_PATH_PARTS = {".venv", "node_modules", "data", "dist", "__pycache__"}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx", ".sqlite", ".db"}
TOKEN_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
)
ASSIGNMENT = re.compile(
    r"(?im)^[ \t]*(?:export[ \t]+)?(?:[A-Z][A-Z0-9_]*_)?"
    r"(?:API[_-]?KEY|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|SECRET(?:[_-]?KEY)?|"
    r"PRIVATE[_-]?KEY|PASSWORD)[ \t]*[:=][ \t]*[\"']?([^\s\"'#]+)"
)
PLACEHOLDER = re.compile(
    r"^(?:your[-_].*|replace[-_]?.*|change[-_]?.*|example|placeholder|"
    r"dummy|test|xxx+|<.*>|\$\{[^}]+\})$",
    re.IGNORECASE,
)


def git_paths(*args: str) -> set[Path]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=True
    )
    return {Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item}


def is_blocked_path(path: Path) -> str | None:
    if path.name.startswith(".env") and path.as_posix() not in ALLOWED_ENV_FILES:
        return "private environment file"
    if any(part in BLOCKED_PATH_PARTS for part in path.parts):
        return "local build/data directory"
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        return "private-key or local database file"
    return None


def scan_text(path: Path) -> list[str]:
    try:
        content = (ROOT / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings: list[str] = []
    for pattern in TOKEN_PATTERNS:
        if pattern.search(content):
            findings.append("recognizable token or private-key material")
    for match in ASSIGNMENT.finditer(content):
        value = match.group(1).strip()
        if value and not PLACEHOLDER.match(value):
            findings.append("non-placeholder secret-like assignment")
            break
    return findings


def main() -> int:
    try:
        paths = git_paths("ls-files", "-z") | git_paths("diff", "--cached", "--name-only", "-z")
    except subprocess.CalledProcessError as error:
        print(f"Cannot inspect Git state: {error}", file=sys.stderr)
        return 2

    findings: list[str] = []
    for path in sorted(paths):
        reason = is_blocked_path(path)
        if reason:
            findings.append(f"{path}: {reason}")
            continue
        for text_reason in scan_text(path):
            findings.append(f"{path}: {text_reason}")

    if findings:
        print("Public-release safety check failed:", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        print("Remove the file/value, unstage it, and rotate any exposed real secret before publishing.", file=sys.stderr)
        return 1

    print(f"Public-release safety check passed ({len(paths)} tracked/staged paths scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
