#!/usr/bin/env python3
"""Targeted public-data checks. Reports locations, never matching secret values.

This is a safety net for common mistakes, not a comprehensive secrets audit.
Use --history for every commit reachable through fetched refs, as well as the
current source tree. CI fetches full history. Never run this on a client folder.
"""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'provider credential': re.compile(r'(?:sk_(?:live|test)_[A-Za-z0-9]{12,}|sk-ant-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,}|xox[baprs]-[A-Za-z0-9-]{15,})'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AGE-SECRET-KEY-1[A-Z0-9]{20,}'),
    'signed token': re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'),
    'personal home path': re.compile(r'/(?:Users|home)/(?!(?:puestario|operator|example|runner|sandbox|test)(?:/|\b))[^/\s<>"\']+'),
}
EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PHONE = re.compile(r'(?<![\w\\])\+\d{10,15}\b')
EXAMPLE_PHONE = re.compile(r'^\+1\d{3}55501\d{2}$|^\+447700900\d{3}$')
PUBLIC_EMAILS = {'info@puestario.com'}


def inspect_text(path, text):
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(f'{path}:{n}: {label}')
        for email in EMAIL.findall(line):
            domain = email.rsplit('@', 1)[-1].lower()
            if email not in PUBLIC_EMAILS and domain not in {'example.com', 'example.org', 'example.net', 'test.com', 'g.us'}:
                findings.append(f'{path}:{n}: non-example email; review before publishing')
        for phone in PHONE.findall(line):
            if not EXAMPLE_PHONE.fullmatch(phone):
                findings.append(f'{path}:{n}: non-example phone; review before publishing')
    return findings


def private_path(path):
    p = Path(path)
    return bool(set(p.parts) & {'secrets', 'credentials', 'managed-company'}) or p.name in {
        'control.json', 'company.json', 'release-manifest.json', '.env', 'google-oauth.json', 'google-token.json'
    } or p.suffix in {'.age', '.agekey', '.pem', '.p12'} or p.name.startswith('.env.')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def scan(root=ROOT, history=False):
    findings = []
    paths = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
    for name in sorted(set(filter(None, paths))):
        path = root / name
        if not path.exists():
            continue
        if private_path(name):
            findings.append(f'{name}: private runtime file must stay outside Git')
        if path.is_symlink():
            findings.append(f'{name}: linked source file needs review')
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        findings.extend(inspect_text(name, text))
    commits = []
    if history:
        commits = git(root, 'rev-list', '--all').decode().splitlines()
        seen = set()
        for commit in commits:
            for row in git(root, 'ls-tree', '-rz', commit).split(b'\0'):
                if not row:
                    continue
                meta, raw_path = row.split(b'\t', 1)
                mode, kind, oid = meta.split()
                if kind != b'blob':
                    continue
                name = raw_path.decode(); label = f'{commit[:8]}:{name}'
                if private_path(name):
                    findings.append(f'{label}: private runtime file in history')
                if (oid, name) in seen:
                    continue
                seen.add((oid, name))
                try:
                    text = git(root, 'cat-file', 'blob', oid.decode()).decode('utf-8')
                except UnicodeDecodeError:
                    continue
                rows = inspect_text(label, text)
                # Historical synthetic allowlist example. Scope the exception to this
                # immutable blob, line and category; do not hide other history findings.
                if oid.decode() == '0883944345298c9d25b43220273811685e1cbb0e' and name == 'tests/test_memory_log.py':
                    rows = [row for row in rows if row != f'{label}:124: non-example phone; review before publishing']
                findings.extend(rows)
    return sorted(set(findings)), len(commits)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    findings, count = scan(history=args.history)
    if findings:
        print('\n'.join(findings))
        raise SystemExit(1)
    print(f'Public-data check passed; {count} fetched commits checked. Targeted scan only.')
