#!/usr/bin/env python3
"""Subject-neutral quality contract for AdventureLearning projects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)
CHOICE_RE = re.compile(
    r'<button\b[^>]*class=["\'][^"\']*\bchoice\b[^"\']*["\'][^>]*>',
    re.IGNORECASE,
)
TARGET_RE = re.compile(r'\b(?:data-result|data-out)=["\']([^"\']+)["\']', re.IGNORECASE)
OUTCOME_RE = re.compile(
    r'<div\b[^>]*id=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*\boutcome\b[^"\']*["\'][^>]*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)


def audit_page(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    rel = path.as_posix()

    if "<title>" not in text.lower():
        errors.append(f"{rel}: missing title")
    if not re.search(r'<meta\b[^>]*name=["\']viewport["\']', text, re.IGNORECASE):
        errors.append(f"{rel}: missing mobile viewport")

    ids = ID_RE.findall(text)
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"{rel}: duplicate IDs: {', '.join(duplicates)}")

    outcomes = {match.group(1): match.group(2) for match in OUTCOME_RE.finditer(text)}
    choices = CHOICE_RE.findall(text)
    if not choices and "data-i10-adventure" in text:
        return
    if not choices:
        errors.append(f"{rel}: no adventure choices found")
        return

    for choice in choices:
        target = TARGET_RE.search(choice)
        if not target:
            errors.append(f"{rel}: choice missing data-result/data-out")
        elif target.group(1) not in outcomes:
            errors.append(f"{rel}: choice points to missing outcome #{target.group(1)}")

    for outcome_id, body in outcomes.items():
        if not re.search(r'class=["\'][^"\']*\b(?:continue|continue-button)\b', body, re.IGNORECASE):
            errors.append(f"{rel}: outcome #{outcome_id} has no continuation control")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()

    errors: list[str] = []
    text_files = [
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".py", ".yml", ".yaml", ".md"}
        and ".git" not in path.parts
        and ".adventure-learning" not in path.parts
        and "vendor" not in path.parts
    ]

    for path in text_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in CONFLICT_MARKERS):
            errors.append(f"{path.relative_to(root)}: unresolved merge marker")

    pages = sorted((root / "adventures").glob("*/index.html"))
    if not pages:
        errors.append("no adventures/*/index.html pages found")
    for page in pages:
        audit_page(page.relative_to(root), errors)

    corpus = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in text_files)
    if not re.search(r"restart", corpus, re.IGNORECASE):
        errors.append("project has no Restart control or handler")
    if not re.search(r"share", corpus, re.IGNORECASE):
        errors.append("project has no Share control or handler")

    risky_continue_hidden = (
        ".outcome.risky .continue-button" in corpus
        and re.search(r"display\s*:\s*none", corpus, re.IGNORECASE)
    )
    retry_guard = "if(correct)" in corpus or "if (correct)" in corpus
    if risky_continue_hidden and not retry_guard:
        errors.append("risky Continue buttons are hidden but choices have no retry-safe correct-answer guard")

    if errors:
        print("AdventureLearning shared contract FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"AdventureLearning shared contract passed: {len(pages)} adventure page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
