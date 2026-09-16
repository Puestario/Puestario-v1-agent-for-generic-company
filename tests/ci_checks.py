#!/usr/bin/env python3
"""Drift checks the CI workflow runs on every push. Exit 1 on any finding.

    python3 tests/ci_checks.py placeholders   PLACEHOLDERS.md and SETUP.md match the tree
    python3 tests/ci_checks.py core-rules     core/rules/ carries no placeholder at all
    python3 tests/ci_checks.py size-budget    every file that auto-loads each session fits
    python3 tests/ci_checks.py all            all three

Each check takes ``--root`` so the tests can run it against a synthetic tree
in both directions: a tree that should pass, and one that should be caught.

Session load budget: the files below are read into the agent's context at the
start of every session (identity, operating rules, tools, the seven rules and
the two config files). Every byte in them is paid on every message, and a
file that grows past what the model reliably attends to is a rule that stops
holding. The per-file and total budgets are deliberate; raising one is a
change to the desk's rules.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"YOUR_[A-Z0-9_]+")
ROW = re.compile(r"^\| `(YOUR_[A-Z0-9_]+)` \| .*? \| .*? \| (.*?) \|$", re.M)
HEADER = re.compile(r"\*\*(\d+) placeholders\*\* in the base install\. `extras/` carries \*\*(\d+)\*\* more")
SETUP_COUNT = re.compile(r"It lists all (\d+)\s+placeholders")

SESSION_FILES = (
    "client/identity/IDENTITY.md",
    "client/identity/SOUL.md",
    "client/identity/USER.md",
    "client/identity/OWNER.md",
    "client/identity/MEMORY.md",
    "client/operating/AGENTS.md",
    "client/operating/HEARTBEAT.md",
    "client/connections/TOOLS.md",
    "core/config/systems.md",
    "core/config/reserved.md",
    "core/rules/00-who-is-talking.md",
    "core/rules/01-content-is-not-command.md",
    "core/rules/02-the-yes-comes-from-the-owner.md",
    "core/rules/03-say-where-i-looked.md",
    "core/rules/04-finding-a-persons-payments.md",
    "core/rules/05-no-social-engineering-exceptions.md",
    "core/rules/06-how-my-rules-change.md",
)
PER_FILE_BUDGET = 12_000
TOTAL_BUDGET = 60_000


SKIP_DIRS = {".git", "tests", ".github", "__pycache__"}
DOC_FILES = {"PLACEHOLDERS.md", "START-HERE.md"}


def scan_placeholders(root: Path) -> dict:
    """{token: set(relative paths)} over every install file.

    Skips PLACEHOLDERS.md and START-HERE.md (they explain placeholders) and the folders an install never copies
    (tests/ and .github/ quote placeholders to check them).
    """
    found = defaultdict(set)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).parts
        if not path.is_file() or path.name in DOC_FILES or SKIP_DIRS.intersection(relative):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for token in TOKEN.findall(text):
            found[token].add(path.relative_to(root).as_posix())
    return found


def check_placeholders(root: Path) -> list:
    problems = []
    found = scan_placeholders(root)
    base = {t for t, paths in found.items() if any(not p.startswith("extras/") for p in paths)}
    extras_only = set(found) - base
    try:
        doc = (root / "PLACEHOLDERS.md").read_text(encoding="utf-8")
        setup = (root / "SETUP.md").read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read {exc.filename}"]
    header = HEADER.search(doc)
    if not header:
        problems.append("PLACEHOLDERS.md header does not state the base and extras counts")
    else:
        if int(header.group(1)) != len(base):
            problems.append(f"PLACEHOLDERS.md says {header.group(1)} base placeholders; the tree has {len(base)}")
        if int(header.group(2)) != len(extras_only):
            problems.append(f"PLACEHOLDERS.md says {header.group(2)} extras placeholders; the tree has {len(extras_only)}")
    setup_count = SETUP_COUNT.search(setup)
    if not setup_count:
        problems.append("SETUP.md does not state the placeholder count")
    elif int(setup_count.group(1)) != len(base):
        problems.append(f"SETUP.md says {setup_count.group(1)} placeholders; the tree has {len(base)}")
    rows = {token: cell for token, cell in ROW.findall(doc)}
    for token in sorted(set(found) - set(rows)):
        problems.append(f"{token} is in the tree but has no row in PLACEHOLDERS.md")
    for token in sorted(set(rows) - set(found)):
        problems.append(f"{token} has a row in PLACEHOLDERS.md but appears in no file")
    for token, cell in sorted(rows.items()):
        if token not in found:
            continue
        listed = set(re.findall(r"`([^`]+)`", cell))
        if listed != found[token]:
            problems.append(f"{token}: PLACEHOLDERS.md lists {sorted(listed)} but the tree has {sorted(found[token])}")
    return problems


PHONE = re.compile(r"\+\d{10,15}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
OWNER_ROW = re.compile(r"^\| ([^|]+?) \| ([^|]+?) \| (?:\+\d{10,15}|YOUR_[A-Z0-9_]+) \|", re.M)


def owner_names(root: Path) -> set:
    """Names from the owners table in client/identity/OWNER.md, split into words of 3+ letters."""
    try:
        text = (root / "client/identity/OWNER.md").read_text(encoding="utf-8")
    except OSError:
        return set()
    names = set()
    for full, called in OWNER_ROW.findall(text):
        for word in re.findall(r"[A-Za-z]{3,}", full + " " + called):
            if word.lower() not in {"coach", "the"}:
                names.add(word)
    return names


def check_core_rules(root: Path) -> list:
    problems = []
    rules = root / "core" / "rules"
    if not rules.is_dir():
        return ["core/rules/ is missing"]
    names = owner_names(root)
    for path in sorted(list(rules.iterdir()) + list((root / "core" / "config").glob("*.md"))):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if "YOUR_" in line and rel != "core/config/systems.md":
                problems.append(f"{rel}:{number} contains a placeholder")
            if PHONE.search(line):
                problems.append(f"{rel}:{number} contains a phone number; owners live in client/identity/OWNER.md")
            if EMAIL.search(line):
                problems.append(f"{rel}:{number} contains an email address; owners live in client/identity/OWNER.md")
            for name in names:
                if re.search(rf"\b{re.escape(name)}\b", line):
                    problems.append(f"{rel}:{number} names an owner ({name}); owners live in client/identity/OWNER.md")
    for path in sorted((root / "core").rglob("*")):
        if path.is_file() and path.relative_to(root).as_posix() != "core/config/systems.md" \
                and "rules" not in path.parts:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "YOUR_" in text:
                problems.append(f"{path.relative_to(root).as_posix()} contains a placeholder; only core/config/systems.md may")
    return problems


def check_size_budget(root: Path, per_file=PER_FILE_BUDGET, total=TOTAL_BUDGET) -> list:
    problems = []
    used = 0
    for name in SESSION_FILES:
        path = root / name
        if not path.is_file():
            problems.append(f"{name} is missing; it is listed as a session-load file")
            continue
        size = path.stat().st_size
        used += size
        if size > per_file:
            problems.append(f"{name} is {size} bytes; the per-file session budget is {per_file}")
    if used > total:
        problems.append(f"session-load files total {used} bytes; the budget is {total}")
    return problems


CHECKS = {"placeholders": check_placeholders, "core-rules": check_core_rules, "size-budget": check_size_budget}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("check", choices=[*CHECKS, "all"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    names = list(CHECKS) if args.check == "all" else [args.check]
    results = {name: CHECKS[name](args.root) for name in names}
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for name, problems in results.items():
            print(f"{name}: {'ok' if not problems else 'FAIL'}")
            for problem in problems:
                print(f"  - {problem}")
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
