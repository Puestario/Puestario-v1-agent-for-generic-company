#!/usr/bin/env python3
"""Check the managed release, generated instruction budgets, and documentation links."""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from managed.control import initial
from managed.runtime import managed_config, workspace_files


def check_release(root):
    problems = []
    required = ('managed/action_log.py', 'managed/install.py', 'managed/control.py',
                'managed/runtime.py', 'managed/company.example.json', 'managed/release.json',
                'runtimes/openclaw/plugins/action-log/index.js',
                'runtimes/openclaw/plugins/puestario-control/bridge.js')
    for name in required:
        if not (root / name).is_file():
            problems.append(f'Missing current release file: {name}')
    if problems:
        return problems
    state = initial(json.loads((root / 'managed/company.example.json').read_text()))
    state['install'] = {'port': 18791, 'gateway_token': 'synthetic-test-only'}
    config = managed_config(state, Path('/synthetic/company'), root)
    for path in config['plugins']['load']['paths']:
        folder = Path(path)
        for name in ('package.json', 'openclaw.plugin.json'):
            if not (folder / name).is_file():
                problems.append(f'Missing plugin manifest: {folder.name}/{name}')
        package = json.loads((folder / 'package.json').read_text())
        for entry in package['openclaw']['extensions']:
            if not (folder / entry).is_file():
                problems.append(f'Missing plugin entry: {folder.name}/{entry}')
    script = Path(config['plugins']['entries']['action-log']['config']['script'])
    if not script.is_file():
        problems.append('Configured outbound logger does not exist')
    pins = json.loads((root / 'managed/release.json').read_text())
    if not pins:
        problems.append('Release pins are missing')
    return problems


def check_size_budget(root):
    # Load the file in the requested tree, including synthetic mutations in tests.
    spec = importlib.util.spec_from_file_location('managed.budget_runtime', root / 'managed/runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    config = json.loads((root / 'managed/company.example.json').read_text())
    config.update(instructions='x' * 8000, company_name='c' * 200, agent_name='a' * 200, language='l' * 200)
    state = initial(config)
    state['install'] = {'port': 18791, 'gateway_token': 'synthetic-test-only'}
    limits = runtime.managed_config(state, Path('/synthetic/company'), root)['agents']['defaults']
    generated = runtime.workspace_files(state)
    problems = []
    for name, content in generated.items():
        if len(content) > limits['bootstrapMaxChars']:
            problems.append(f'{name} exceeds the per-file instruction limit')
    if sum(map(len, generated.values())) > limits['bootstrapTotalMaxChars']:
        problems.append('Generated instructions exceed the total instruction limit')
    for person in state['founders']:
        if any(person in content for content in generated.values()):
            problems.append('A founder number leaked into shared instructions')
    return problems


def check_docs(root):
    problems = []
    for path in sorted(root.rglob('*.md')):
        if set(path.relative_to(root).parts) & {'.git', 'node_modules', '.venv'}:
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            target = target.split('#', 1)[0]
            if not target or re.match(r'^[a-z]+:', target):
                continue
            if not (path.parent / unquote(target)).exists():
                problems.append(f'{path.relative_to(root)} links to missing {target}')
    return problems


CHECKS = {'release': check_release, 'size-budget': check_size_budget, 'docs': check_docs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('check', choices=[*CHECKS, 'all'])
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    names = CHECKS if args.check == 'all' else [args.check]
    results = {name: CHECKS[name](args.root) for name in names}
    for name, issues in results.items():
        print(f'{name}: {"FAIL" if issues else "ok"}')
        for issue in issues:
            print(f'  - {issue}')
    return int(any(results.values()))


if __name__ == '__main__':
    raise SystemExit(main())
