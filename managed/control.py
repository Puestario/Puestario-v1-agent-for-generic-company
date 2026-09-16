"""Typed, host-owned operations. Identity is supplied ONLY by the trusted plugin.

This module is not an internet server and has no shared agent-visible admin token.
Only the host plugin/installer can execute it; the model has no shell or filesystem
tool in the managed profile. A local OS administrator remains a trusted operator.
"""
import copy
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from . import adapters
from .store import DeskError, Store, digest, record

PHONE = re.compile(r"^\+[1-9][0-9]{7,14}$")
GROUP = re.compile(r"^[0-9]{5,30}(?:-[0-9]+)?@g\.us$")
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
CHECKS = {"founders", "staff-dm", "staff-group", "private-data", "first-job", "reminder",
          "restart", "containment", "backup-restore", "model", "channel"}
SETUP_ACTIONS = {"company.update", "resource.put", "resource.remove", "founder.add"}
ACCESS_ACTIONS = {"person.put", "person.remove", "group.put", "group.remove", "founder.add", "founder.remove"}


def phone(value):
    if not isinstance(value, str):
        raise DeskError("A verified phone number is required")
    value = value.removeprefix("whatsapp:")
    if value.endswith("@s.whatsapp.net"):
        value = "+" + value[:-15]
    if not PHONE.fullmatch(value):
        raise DeskError("Use a verified international phone number, including +")
    return value


def text(value, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise DeskError(f"Provide text between 1 and {limit} characters")
    return value.strip()


def slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise DeskError("Use a name with 2–41 lowercase letters, numbers, or hyphens")
    return value


def initial(config, now=None):
    now = time.time() if now is None else now
    if set(config) - {"company_id", "company_name", "agent_name", "timezone", "language", "account_id", "founders", "model", "fallbacks", "instructions"}:
        raise DeskError("Unknown company setup field")
    ZoneInfo(config.get("timezone", "America/New_York"))
    founders = {phone(p["number"]): {"name": text(p["name"]), "active": True} for p in config["founders"]}
    if len(founders) < 2:
        raise DeskError("Start with both founders' verified numbers")
    fallbacks = config.get("fallbacks", [])
    if not isinstance(fallbacks, list) or len(fallbacks) > 5:
        raise DeskError("Choose up to five fallback models")
    instructions = config.get("instructions", "")
    if not isinstance(instructions, str) or len(instructions) > 8000:
        raise DeskError("Shared company instructions must be text of at most 8000 characters")
    company = {"company_id": slug(config["company_id"]), "company_name": text(config["company_name"]),
               "agent_name": text(config["agent_name"]), "timezone": config.get("timezone", "America/New_York"),
               "language": text(config.get("language", "English and Spanish")), "model": text(config["model"]),
               "fallbacks": [text(model) for model in fallbacks], "instructions": instructions}
    return {"schema": 1, "company": company, "account_id": slug(config.get("account_id", "default")),
            "revision": 1, "mode": "SETUP", "setup": None, "ready": False, "paused": False,
            "founders": founders, "people": {}, "groups": {}, "resources": {}, "jobs": {}, "notes": {},
            "history": [], "outbox": {}, "checks": {}, "receipts": {}, "gateway_pending": True,
            "created": now, "boot": None}


def configuration_digest(state):
    return digest({key: state[key] for key in ("company", "account_id", "founders", "people", "groups", "resources")})


def expire(state, now):
    lease = state.get("setup")
    if lease and lease["until"] <= now:
        state["setup"] = None
        state["mode"] = "READY" if state["ready"] else "SETUP"
        record(state, "system", "setup.expired", {}, now)


def identify(state, actor, now):
    expire(state, now)
    if not isinstance(actor, dict) or actor.get("channel") != "whatsapp" or actor.get("account") != state["account_id"]:
        raise DeskError("Trusted sender context for this WhatsApp account is required")
    sender = phone(actor.get("sender"))
    target = actor.get("conversation", "")
    is_group = isinstance(target, str) and bool(GROUP.fullmatch(target))
    if not is_group and phone(target) != sender:
        raise DeskError("The conversation does not match the sender")
    founder = state["founders"].get(sender, {}).get("active", False)
    person = state["people"].get(sender, {})
    if not founder and not person.get("active"):
        raise DeskError("This person does not have access")
    if is_group:
        group = state["groups"].get(target)
        if not group or (not founder and sender not in group["members"]):
            raise DeskError("This person or group does not have access")
    if not founder:
        if state["paused"] or state["gateway_pending"]:
            raise DeskError("The desk is paused while its settings are checked")
        if not state["ready"] and not (state.get("setup") and person.get("tester")):
            raise DeskError("The desk is still being set up")
    return sender, founder, is_group


def session_gate(store, actor, session_id, has_history=False, now=None):
    """Old model history cannot survive a permission change. /new creates a fresh UUID."""
    now = time.time() if now is None else now
    if not isinstance(session_id, str) or not session_id:
        raise DeskError("A trusted session ID is required")
    with store.locked() as state:
        _, founder, is_group = identify(state, actor, now)
        epoch = state.get("access_epoch", 0)
        sessions = state.setdefault("sessions", {})
        previous = sessions.get(session_id)
        route = {k: actor[k] for k in ("channel", "account", "conversation")}
        if previous is None:
            if has_history:
                raise DeskError("Access changed. Send /new before continuing")
            sessions[session_id] = {"epoch": epoch, "route": route, "owner_private": founder and not is_group}
        elif previous.get("route") != route:
            raise DeskError("The session belongs to another conversation")
        elif previous.get("epoch") != epoch:
            if founder and not is_group and previous.get("owner_private"):
                previous["epoch"] = epoch  # An unchanged founder can finish a multi-step setup.
            else:
                raise DeskError("Access changed. Send /new before continuing")
        return {"allowed": True, "epoch": epoch, "owner_private": founder and not is_group}


def require_founder(state, actor, now):
    sender, founder, is_group = identify(state, actor, now)
    if not founder:
        raise DeskError("That change needs a verified administrator")
    if is_group:
        raise DeskError("Send this setup request in your private chat with the agent")
    return sender


def require_setup(state, sender, now):
    lease = state.get("setup")
    if not lease or lease["owner"] != sender or lease["until"] <= now:
        raise DeskError("Open Setup for this founder before changing company or app settings")


def access(state, actor, resource_id, operation, now):
    sender, founder, is_group = identify(state, actor, now)
    resource = state["resources"].get(resource_id)
    if not resource:
        raise DeskError("This business resource is not configured")
    allowed = founder or operation in state["people"][sender].get("resources", {}).get(resource_id, [])
    if is_group:
        # A group's explicit resources are public-to-that-group, even for a founder.
        allowed = allowed and operation in state["groups"][actor["conversation"]].get("resources", {}).get(resource_id, [])
    if not allowed or (operation == "write" and not resource.get("writable")):
        raise DeskError("This person or conversation cannot use that information")
    return resource


def grants(state, value):
    if not isinstance(value, dict):
        raise DeskError("Resources must be a map of resource names to read/write permissions")
    out = {}
    for name, permissions in value.items():
        if name not in state["resources"] or not isinstance(permissions, list) or not permissions or set(permissions) - {"read", "write"}:
            raise DeskError("Choose configured resources and read/write permissions")
        if "write" in permissions and not state["resources"][name].get("writable"):
            raise DeskError("This resource is read-only")
        out[name] = sorted(set(permissions))
    return out


def next_due(schedule, zone, now):
    if not isinstance(schedule, dict):
        raise DeskError("Provide at, every_minutes, or daily scheduling")
    if set(schedule) == {"at"}:
        at = datetime.fromisoformat(schedule["at"].replace("Z", "+00:00"))
        if at.tzinfo is None or at.timestamp() <= now:
            raise DeskError("Use a future date and time with a time zone")
        return at.timestamp()
    if set(schedule) == {"every_minutes"}:
        minutes = schedule["every_minutes"]
        if type(minutes) is not int or not 1 <= minutes <= 10080:
            raise DeskError("Choose between 1 and 10080 minutes")
        return now + minutes * 60
    if set(schedule) == {"daily"} and isinstance(schedule["daily"], str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", schedule["daily"]):
        local = datetime.fromtimestamp(now, ZoneInfo(zone))
        hour, minute = map(int, schedule["daily"].split(":"))
        candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate.timestamp() <= now:
            candidate += timedelta(days=1)
        # Round-trip through UTC handles a daylight-saving gap deterministically.
        return candidate.astimezone(timezone.utc).timestamp()
    raise DeskError("Choose exactly one: at, every_minutes, or daily HH:MM")


def notify_founders(state, sender, summary, now):
    for number, owner in state["founders"].items():
        if owner["active"] and number != sender:
            key = str(uuid.uuid4())
            state["outbox"][key] = {"kind": "notice", "creator": sender, "to": number,
                                    "text": summary, "status": "pending", "at": now}


def public_status(state, founder=False):
    result = {"mode": state["mode"], "ready": state["ready"], "paused": state["paused"],
              "revision": state["revision"], "settings_applied": not state["gateway_pending"]}
    if founder:
        result.update(setup=state["setup"], people=state["people"], groups=state["groups"],
                      founders=state["founders"], resources=state["resources"],
                      missing_checks=sorted(CHECKS - set(valid_checks(state))),
                      pending_notices=sum(v["status"] != "sent" for v in state["outbox"].values()))
    return result


def valid_checks(state):
    expected = configuration_digest(state)
    return {key for key, proof in state["checks"].items() if proof.get("passed") and proof.get("config") == expected}


def dispatch(store, actor, operation, args=None, request_id=None, expected_revision=None, now=None):
    args = args or {}
    if not isinstance(args, dict):
        raise DeskError("Operation arguments must be an object")
    now = time.time() if now is None else now
    # All operations run under the same host file lock, including sends and revocation.
    with store.locked() as state:
        sender, founder, is_group = identify(state, actor, now)
        if expected_revision is not None and expected_revision != state["revision"]:
            raise DeskError("Settings changed. Read the current status and try the new change")
        key = digest([sender, request_id]) if request_id else None
        fingerprint = digest([operation, args, actor["conversation"]])
        if key in state["receipts"]:
            receipt = state["receipts"][key]
            if receipt["fingerprint"] != fingerprint:
                raise DeskError("This request ID was already used for a different change")
            return receipt["result"]
        if operation == "status":
            return public_status(state, founder and not is_group)
        if operation == "gate":
            return {"allowed": True, "founder": founder, "group": is_group}
        if operation == "resources.list":
            visible = []
            for name in state["resources"]:
                try:
                    r = access(state, actor, name, "read", now)
                    visible.append({"name": name, "kind": r["kind"], "writable": r.get("writable", False)})
                except DeskError:
                    pass
            return {"resources": visible}
        if operation in {"resource.read", "resource.write"}:
            name = slug(args.get("resource"))
            resource = access(state, actor, name, "write" if operation.endswith("write") else "read", now)
            if operation.endswith("write"):
                if not request_id:
                    raise DeskError("A host request ID is required for a write")
                # Persist an uncertain receipt BEFORE the external side effect; a crash must not replay it.
                from .store import atomic_json
                state["receipts"][key] = {"fingerprint": fingerprint, "result": {"status": "unverified", "message": "Read the sheet before retrying this write"}}
                record(state, sender, "resource.write.attempt", {"resource": name}, now)
                atomic_json(store.path, state)
                result = adapters.sheet_write(store.root, resource, args.get("rows"))
            else:
                result = {"untrusted_business_data": adapters.read(store.root, resource), "resource": name}
            record(state, sender, operation, {"resource": name}, now)
        elif operation in {"note.save", "note.list"}:
            if is_group:
                raise DeskError("Use private chat for private notes")
            notes = state["notes"].setdefault(sender, {})
            if operation == "note.list":
                return {"private_notes": notes}
            notes[slug(args.get("name"))] = text(args.get("text"), 4000)
            record(state, sender, operation, {"name": args["name"]}, now)
            result = {"saved": True, "visibility": "only this person's private chat"}
        elif operation.startswith("job."):
            result = job_operation(state, actor, operation, args, now)
        else:
            sender = require_founder(state, actor, now)
            if operation in SETUP_ACTIONS:
                require_setup(state, sender, now)
            result = admin_operation(store, state, sender, operation, args, now)
        if key:
            state["receipts"][key] = {"fingerprint": fingerprint, "result": result}
        return result


def job_operation(state, actor, operation, args, now):
    sender, founder, is_group = identify(state, actor, now)
    if is_group:
        raise DeskError("Set up reminders in private chat; name an approved group if it should receive one")
    if operation == "job.list":
        return {"jobs": [dict(job, id=key) for key, job in state["jobs"].items() if founder or job["creator"] == sender]}
    if operation in {"job.remove", "job.reschedule"}:
        key = args.get("id")
        job = state["jobs"].get(key)
        if not job or (not founder and job["creator"] != sender):
            raise DeskError("That job is not available to you")
        if operation.endswith("remove"):
            job["enabled"] = False
        else:
            job["next_due"] = next_due(args.get("schedule"), job["timezone"], now)
            job["schedule"] = args["schedule"]
            job["enabled"] = True
        record(state, sender, operation, {"id": key}, now)
        return {"id": key, "enabled": job["enabled"], "next_due": job["next_due"]}
    if operation != "job.add":
        raise DeskError("Unknown job operation")
    target = args.get("to", sender)
    if not founder and target != sender:
        raise DeskError("Staff reminders must go to their own private chat")
    target_actor = recipient_actor(state, target)
    resource_id = args.get("resource")
    if resource_id:
        access(state, actor, resource_id, "read", now)
        access(state, target_actor, resource_id, "read", now)
    elif GROUP.fullmatch(target or ""):
        raise DeskError("Group schedules must use an explicitly shared resource")
    content = text(args.get("text", "Scheduled report"), 2000)
    schedule = args.get("schedule")
    key = str(uuid.uuid4())
    job = {"creator": sender, "to": target, "resource": resource_id, "text": content,
           "schedule": schedule, "timezone": state["company"]["timezone"], "enabled": True,
           "next_due": next_due(schedule, state["company"]["timezone"], now), "runs": []}
    state["jobs"][key] = job
    record(state, sender, operation, {"id": key, "to": target, "resource": resource_id}, now)
    return {"id": key, "next_due": job["next_due"], "timezone": job["timezone"],
            "total_jobs": sum(j["enabled"] for j in state["jobs"].values())}


def recipient_actor(state, target):
    if GROUP.fullmatch(target or ""):
        if target not in state["groups"]:
            raise DeskError("This group is not approved")
        # Group access is an explicit data grant, independent of the initiating founder's private grants.
        founder = next((p for p, row in state["founders"].items() if row["active"]), None)
        return {"channel": "whatsapp", "account": state["account_id"], "sender": founder, "conversation": target}
    target = phone(target)
    if not (state["founders"].get(target, {}).get("active") or state["people"].get(target, {}).get("active")):
        raise DeskError("The recipient no longer has access")
    return {"channel": "whatsapp", "account": state["account_id"], "sender": target, "conversation": target}


def admin_operation(store, state, sender, operation, args, now):
    if operation == "setup.open":
        minutes = args.get("minutes", 15)
        if type(minutes) is not int or not 1 <= minutes <= 60:
            raise DeskError("Setup can open for 1 to 60 minutes")
        state["setup"] = {"owner": sender, "until": now + minutes * 60}
        state["mode"] = "SETUP"
    elif operation == "setup.close":
        missing = sorted(CHECKS - valid_checks(state))
        if missing or state["gateway_pending"] or state["paused"]:
            raise DeskError("Not Ready. Installer checks still needed: " + ", ".join(missing or ["settings/paused state"]))
        state.update(ready=True, mode="READY", setup=None)
        state["accepted_release"] = state.get("install", {}).get("source_revision")
        state["accepted_config"] = configuration_digest(state)
    elif operation == "desk.pause":
        state["paused"] = True
    elif operation == "desk.resume":
        if state["gateway_pending"]:
            raise DeskError("Apply and check the settings before resuming")
        state["paused"] = False
    elif operation == "person.put":
        target = phone(args.get("number"))
        if target in state["founders"]:
            raise DeskError("Use founder controls for a founder's number")
        state["people"][target] = {"name": text(args.get("name")), "active": True,
                                   "tester": args.get("tester") is True, "resources": grants(state, args.get("resources", {}))}
    elif operation in {"person.remove", "founder.remove"}:
        target = phone(args.get("number"))
        collection = state["founders"] if operation.startswith("founder") else state["people"]
        if target not in collection or not collection[target]["active"]:
            raise DeskError("This person is not active in that role")
        if operation.startswith("founder") and sum(p["active"] for p in collection.values()) <= 1:
            raise DeskError("Keep one active founder or recover at the machine")
        collection[target]["active"] = False
        for group in state["groups"].values():
            group["members"] = [p for p in group["members"] if p != target]
        for job in state["jobs"].values():
            if target in (job["creator"], job["to"]):
                job["enabled"] = False
        for notice in state["outbox"].values():
            if notice["to"] == target:
                notice["status"] = "cancelled"
    elif operation == "founder.add":
        target = phone(args.get("number"))
        state["founders"][target] = {"name": text(args.get("name")), "active": True}
        state["people"].pop(target, None)
    elif operation == "group.put":
        target = args.get("id", "")
        if not GROUP.fullmatch(target):
            raise DeskError("Use the exact WhatsApp group ID")
        members = [phone(p) for p in args.get("members", [])]
        for member in members:
            recipient_actor(state, member)
        state["groups"][target] = {"name": text(args.get("name")), "members": sorted(set(members)),
                                    "resources": grants(state, args.get("resources", {}))}
    elif operation == "group.remove":
        if args.get("id") not in state["groups"]:
            raise DeskError("That group is not configured")
        del state["groups"][args["id"]]
        for job in state["jobs"].values():
            if job["to"] == args["id"]:
                job["enabled"] = False
    elif operation == "company.update":
        allowed = {"company_name", "agent_name", "language", "timezone", "model", "fallbacks", "instructions"}
        if not args or set(args) - allowed:
            raise DeskError("Choose company name, agent name, language, timezone, model, fallbacks, or instructions")
        for key, value in args.items():
            if key == "fallbacks":
                if not isinstance(value, list) or len(value) > 5:
                    raise DeskError("Choose up to five fallback models")
                value = [text(item) for item in value]
            else:
                value = text(value, 8000 if key == "instructions" else 200)
            if key == "timezone":
                ZoneInfo(value)
            state["company"][key] = value
    elif operation == "resource.put":
        name = slug(args.get("name"))
        resource = copy.deepcopy(args.get("resource", {}))
        allowed = {"kind", "connection", "spreadsheet_id", "range", "calendar_id", "location_id", "writable"}
        if not isinstance(resource, dict) or set(resource) - allowed:
            raise DeskError("Unknown resource setting; credentials must be entered at the machine")
        adapters.validate_resource(resource)
        if resource.get("writable") and resource["kind"] != "google-sheets":
            raise DeskError("Only explicitly scoped Google Sheet writes are supported in this release")
        state["resources"][name] = resource
    elif operation == "resource.remove":
        name = slug(args.get("name"))
        if name not in state["resources"]:
            raise DeskError("That resource does not exist")
        del state["resources"][name]
        for row in list(state["people"].values()) + list(state["groups"].values()):
            row.get("resources", {}).pop(name, None)
        for job in state["jobs"].values():
            if job.get("resource") == name:
                job["enabled"] = False
    elif operation == "connection.check":
        name = slug(args.get("resource"))
        if name not in state["resources"]:
            raise DeskError("Choose a configured resource")
        data = adapters.read(store.root, state["resources"][name])
        if not data.get("account"):
            raise DeskError("Connection did not identify the configured business account")
        record(state, sender, operation, {"resource": name, "account": data["account"]}, now)
        return {"connected": True, "resource": name, "account": data["account"], "scope": "configured read operation verified"}
    else:
        raise DeskError("Unknown operation")
    if operation in SETUP_ACTIONS:
        state["ready"] = False
    if operation in ACCESS_ACTIONS or operation in SETUP_ACTIONS:
        state["gateway_pending"] = True
        state["access_epoch"] = state.get("access_epoch", 0) + 1
    revision = record(state, sender, operation, {k: v for k, v in args.items() if k not in {"instructions", "resource"}}, now)
    if operation in ACCESS_ACTIONS:
        notify_founders(state, sender, f"Puestario: {sender} made {operation} (change {revision}).", now)
    return {"saved": True, "operation": operation, "revision": revision, "mode": state["mode"],
            "settings_applied": not state["gateway_pending"]}
