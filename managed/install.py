"""Operator-only installation and acceptance. Never imported as a model tool."""
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from .control import CHECKS, configuration_digest, initial
from .runtime import OPENCLAW_VERSION, SANDBOX_IMAGE, apply, environment
from .store import DeskError, Store, atomic_json, record


def require_real_company(config):
    """Refuse the shipped examples before creating state or contacting a runtime."""
    initial(config)  # Validate the complete shape first.
    if config["company_id"] == "example-office" or config["company_name"] == "Example Office":
        raise DeskError("Replace the example company in your private company.json before installing")
    for person in config["founders"]:
        number = person["number"].removeprefix("whatsapp:")
        if number.endswith("@s.whatsapp.net"):
            number = "+" + number[:-15]
        if re.fullmatch(r"\+1[2-9][0-9]{2}55501[0-9]{2}", number) or "replace this example" in person["name"].lower():
            raise DeskError("Replace both example administrator names and verify their actual phone numbers")


def source_files(source):
    # Copy the reviewed inventory only, never ignored .env files or leftover client secrets.
    run = subprocess.run(["git", "ls-files", "-z", "--", "managed",
        "runtimes/openclaw/plugins/puestario-control", "runtimes/openclaw/plugins/action-log"], cwd=source, check=True, capture_output=True, text=True)
    for name in sorted(filter(None, run.stdout.split("\0"))):
        relative = Path(name)
        path = source / relative
        if path.is_symlink() or not path.is_file():
            raise DeskError("Reviewed release files must be regular files")
        yield relative


def initialize(root, source, config, revision, port=18791, staging=False):
    if not staging:
        require_real_company(config)
    if not 1024 <= port <= 65535:
        raise DeskError("Choose a private gateway port between 1024 and 65535")
    root, source = Path(root).expanduser().resolve(), Path(source).resolve()
    if root == source or source in root.parents or root in source.parents:
        raise DeskError("Install outside the source checkout")
    store = Store(root)
    if root.exists() and any(root.iterdir()):
        raise DeskError("Company folder is not empty. Use doctor/apply; never initialize over company data")
    if not staging:
        actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=source, check=True, capture_output=True, text=True).stdout
        if revision != actual or dirty:
            raise DeskError("Install from a clean checkout at the exact reviewed commit")
        observed = subprocess.run(["openclaw", "--version"], capture_output=True, text=True, check=True).stdout
        if OPENCLAW_VERSION not in observed.split():
            raise DeskError("Install the pinned OpenClaw version before continuing")
    state = initial(config)
    release = root / "release"
    state["install"] = {"source_revision": revision, "release": str(release), "openclaw": OPENCLAW_VERSION,
                        "port": port, "gateway_token": secrets.token_urlsafe(36), "staging": staging}
    store.initialize(state)
    manifest = {}
    for relative in source_files(source):
        destination = release / relative
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source / relative, destination)
        destination.chmod(0o400)
        manifest[str(relative)] = hashlib.sha256(destination.read_bytes()).hexdigest()
    atomic_json(root / "release-manifest.json", {"revision": revision, "files": manifest})
    for folder in ("security", "secrets", "evidence", "workspace", "gateway", "backups"):
        (root / folder).mkdir(mode=0o700, exist_ok=True)
    apply(store, validate=not staging)
    return {"installed": True, "ready": False, "staging": staging, "root": str(root),
            "next": "Connect model and phone, run doctor, complete the acceptance checklist"}


def doctor(store):
    state = store.read()
    checks = {}
    def check(name, fn):
        try: checks[name] = bool(fn())
        except Exception: checks[name] = False
    check("private-root", lambda: store.root.stat().st_mode & 0o077 == 0)
    check("private-control", lambda: store.path.stat().st_mode & 0o077 == 0)
    def release_ok():
        manifest = json.loads((store.root / "release-manifest.json").read_text())
        release = Path(state["install"]["release"])
        return release == store.root / "release" and all(
            not (release / rel).is_symlink() and hashlib.sha256((release / rel).read_bytes()).hexdigest() == expected
            and (release / rel).stat().st_mode & 0o022 == 0 for rel, expected in manifest["files"].items())
    check("protected-release", release_ok)
    check("reviewed-release", lambda: not state["install"].get("staging") and len(state["install"]["source_revision"]) == 40)
    def cli(args):
        return subprocess.run(args, env=environment(store.root), capture_output=True, text=True, timeout=45)
    check("openclaw-version", lambda: OPENCLAW_VERSION in cli(["openclaw", "--version"]).stdout.split())
    check("config-valid", lambda: cli(["openclaw", "config", "validate", "--json"]).returncode == 0)
    def plugin_ok():
        run = cli(["openclaw", "plugins", "inspect", "puestario-control", "--runtime", "--json"])
        data = json.loads(run.stdout)
        return run.returncode == 0 and data.get("plugin", {}).get("status") == "loaded" and not any(
            row.get("level") == "error" for row in data.get("diagnostics", [])) and "puestario" in {
                name for row in data.get("tools", []) for name in row.get("names", [])} and {
                    "before_agent_run", "llm_output", "before_tool_call", "message_sending"}.issubset({
                        row["name"] for row in data.get("typedHooks", [])})
    check("protected-plugin-loaded", plugin_ok)
    check("docker-running", lambda: cli(["docker", "info"]).returncode == 0)
    check("sandbox-image", lambda: cli(["docker", "image", "inspect", SANDBOX_IMAGE]).returncode == 0)
    check("age-encryption", lambda: "1.3.2" in cli(["age", "--version"]).stdout)
    check("gateway-live", lambda: cli(["openclaw", "gateway", "health", "--json"]).returncode == 0)
    return {"passed": all(checks.values()), "checks": checks, "ready": state["ready"],
            "missing_acceptance": sorted(CHECKS - set(k for k, v in state["checks"].items()
                if v.get("passed") and v.get("config") == configuration_digest(state)))}


def accept(store, check, evidence, operator):
    if check not in CHECKS:
        raise DeskError("Unknown acceptance check")
    data = Path(evidence).read_bytes()
    if not 20 <= len(data) <= 5_000_000 or not operator.strip():
        raise DeskError("Provide a saved test result and the operator's name")
    # This is a signed-off local test, not an automatically proved claim.
    report = doctor(store)
    if not report["passed"]:
        raise DeskError("Machine checks must pass before recording client acceptance")
    with store.locked() as state:
        proof_hash = hashlib.sha256(data).hexdigest()
        target = store.root / "evidence" / f"{check}-{proof_hash}.txt"
        target.write_bytes(data)
        target.chmod(0o600)
        state["checks"][check] = {"passed": True, "config": configuration_digest(state),
            "operator": operator, "evidence_sha256": proof_hash, "at": time.time(), "type": "operator-attestation"}
        record(state, "local-operator", "acceptance", {"check": check, "operator": operator, "sha256": proof_hash}, time.time())
    return {"recorded": check, "type": "operator-attestation"}


def service_file(store):
    """Generate only. Enabling login/startup is an explicit local preparation step."""
    state = store.read()
    executable = shutil.which("openclaw")
    if not executable:
        raise DeskError("OpenClaw is not installed")
    label = "com.puestario.desk." + state["company"]["company_id"]
    value = {"Label": label, "ProgramArguments": [executable, "gateway", "run"],
             "WorkingDirectory": state["install"]["release"], "RunAtLoad": True, "KeepAlive": True,
             "EnvironmentVariables": {k: v for k, v in environment(store.root).items() if k.startswith("OPENCLAW_") or k == "ACTION_LOG"},
             "StandardOutPath": str(store.root / "security/gateway.stdout.log"),
             "StandardErrorPath": str(store.root / "security/gateway.stderr.log"),
             "ThrottleInterval": 30}
    value["EnvironmentVariables"]["PATH"] = os.environ.get("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    target = store.root / f"{label}.plist"
    target.write_bytes(plistlib.dumps(value))
    target.chmod(0o600)
    return {"file": str(target), "enabled": False, "note": "Install as this dedicated operator's LaunchAgent; requires login after FileVault unlock"}
