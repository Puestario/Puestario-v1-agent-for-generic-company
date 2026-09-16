"""Bounded business operations. No caller-selected hosts or credentials in model output."""
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from .store import DeskError, atomic_json

KINDS = {"google-sheets", "google-calendar", "stripe", "ghl"}
MAX_RESPONSE = 2_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeskError("The service redirected the request; connection needs review")


def request(method, url, token=None, payload=None, headers=None, form=False):
    # Only adapter-owned URLs reach this function. Never follow a redirect with a credential.
    hdr = {"Accept": "application/json", **(headers or {})}
    if token:
        hdr["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        hdr["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        data = urllib.parse.urlencode(payload).encode() if form else json.dumps(payload, allow_nan=False).encode()
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        raise DeskError(f"Service returned HTTP {exc.code}; no success confirmed") from None
    except (OSError, urllib.error.URLError):
        raise DeskError("Service unavailable; no success confirmed") from None
    if len(raw) > MAX_RESPONSE:
        raise DeskError("Service response is too large; narrow the request")
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        raise DeskError("Service did not return valid JSON") from None


def load_secret(root, connection):
    path = root / "secrets" / (connection + ".json")
    if path.is_symlink() or not path.is_file():
        raise DeskError("Connect this app at the machine first")
    return json.loads(path.read_text())


def google_token(root, connection, secret):
    if secret.get("access_token") and secret.get("expires_at", 0) > time.time() + 60:
        return secret["access_token"]
    needed = ("client_id", "client_secret", "refresh_token")
    if not all(isinstance(secret.get(k), str) and secret[k] for k in needed):
        raise DeskError("Google needs a completed OAuth sign-in with offline access")
    result = request("POST", "https://oauth2.googleapis.com/token", payload={
        **{key: secret[key] for key in needed}, "grant_type": "refresh_token"}, form=True)
    if not isinstance(result.get("access_token"), str):
        raise DeskError("Google did not return an access token")
    secret.update(access_token=result["access_token"], expires_at=time.time() + int(result.get("expires_in", 0)))
    atomic_json(root / "secrets" / (connection + ".json"), secret)
    return secret["access_token"]


def validate_resource(resource):
    if "writable" in resource and type(resource["writable"]) is not bool:
        raise DeskError("Writable must be true or false, not text")
    kind = resource.get("kind")
    if kind not in KINDS:
        raise DeskError("Supported apps: Google Sheets, Google Calendar, Stripe, GHL")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,40}", resource.get("connection", "")):
        raise DeskError("Use a short connection name, such as google-main")
    if kind == "google-sheets":
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", resource.get("spreadsheet_id", "")):
            raise DeskError("A specific spreadsheet ID is required")
        if not re.fullmatch(r"[^!\r\n]{1,100}![A-Z]{1,3}[1-9][0-9]{0,5}:[A-Z]{1,3}[1-9][0-9]{0,5}", resource.get("range", "")):
            raise DeskError("Use a bounded sheet range, such as Sales!A1:H100")
        left, top, right, bottom = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", resource["range"].split("!")[1]).groups()
        def col(value):
            result = 0
            for char in value:
                result = result * 26 + ord(char) - 64
            return result
        width, height = col(right) - col(left) + 1, int(bottom) - int(top) + 1
        if not 1 <= width <= 100 or not 1 <= height <= 1000 or width * height > 10000:
            raise DeskError("Choose a forward range of at most 100 columns, 1000 rows and 10000 cells")
    elif kind == "google-calendar":
        if not isinstance(resource.get("calendar_id"), str) or not 1 <= len(resource["calendar_id"]) <= 250:
            raise DeskError("A specific calendar ID is required")
    elif kind == "ghl":
        if not re.fullmatch(r"[A-Za-z0-9]{5,100}", resource.get("location_id", "")):
            raise DeskError("A specific GHL location ID is required")


def read(root, resource):
    validate_resource(resource)
    secret = load_secret(root, resource["connection"])
    kind = resource["kind"]
    token = google_token(root, resource["connection"], secret) if kind.startswith("google-") else secret.get("token")
    if not isinstance(token, str) or len(token) < 8:
        raise DeskError("App credential is missing")
    quote = lambda value: urllib.parse.quote(value, safe="")
    if kind == "google-sheets":
        base = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(resource["spreadsheet_id"])
        meta = request("GET", base + "?fields=spreadsheetId,properties.title", token)
        if meta.get("spreadsheetId") != resource["spreadsheet_id"]:
            raise DeskError("Google returned a different spreadsheet; connection needs review")
        data = request("GET", base + "/values/" + quote(resource["range"]), token)
        return {"account": meta.get("spreadsheetId"), "label": meta.get("properties", {}).get("title"),
                "range": data.get("range"), "rows": data.get("values", []), "complete_for_requested_range": True}
    if kind == "google-calendar":
        base = "https://www.googleapis.com/calendar/v3/calendars/" + quote(resource["calendar_id"])
        meta = request("GET", base, token)
        query = urllib.parse.urlencode({"timeMin": datetime.now(timezone.utc).isoformat(), "singleEvents": "true",
                                       "orderBy": "startTime", "maxResults": 50})
        data = request("GET", base + "/events?" + query, token)
        return {"account": meta.get("id"), "label": meta.get("summary"), "events": data.get("items", []),
                "more_available": bool(data.get("nextPageToken")), "scope": "next 50 upcoming events"}
    if kind == "stripe":
        account = request("GET", "https://api.stripe.com/v1/account", token)
        query = urllib.parse.urlencode({"limit": 100, "created[gte]": int(time.time()) - 86400})
        data = request("GET", "https://api.stripe.com/v1/charges?" + query, token)
        return {"account": account.get("id"), "scope": "charges created in the last 24 hours; up to 100",
                "more_available": bool(data.get("has_more")), "charges": [
                    {k: row.get(k) for k in ("id", "amount", "currency", "paid", "refunded", "created")}
                    for row in data.get("data", [])]}
    location = request("GET", "https://services.leadconnectorhq.com/locations/" + quote(resource["location_id"]),
                       token, headers={"Version": "2021-07-28"})
    if location.get("location", {}).get("id") != resource["location_id"]:
        raise DeskError("GHL did not confirm the configured business location")
    query = urllib.parse.urlencode({"locationId": resource["location_id"], "limit": 100})
    data = request("GET", "https://services.leadconnectorhq.com/contacts/?" + query, token,
                   headers={"Version": "2021-07-28"})
    return {"account": resource["location_id"], "scope": "up to 100 contacts in the configured location",
            "more_available": bool(data.get("meta", {}).get("nextPageUrl")),
            "contacts": [{k: row.get(k) for k in ("id", "firstName", "lastName", "dateAdded", "source")}
                         for row in data.get("contacts", [])]}


def sheet_write(root, resource, rows):
    """Write only the owner-configured exact range; read back before claiming success."""
    validate_resource(resource)
    if resource["kind"] != "google-sheets" or not resource.get("writable"):
        raise DeskError("This resource is read-only")
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise DeskError("Provide 1 to 1000 rows")
    area = resource["range"].split("!")[1]
    left, top, right, bottom = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", area).groups()
    def col(s):
        n = 0
        for ch in s:
            n = n * 26 + ord(ch) - 64
        return n
    width, height = col(right) - col(left) + 1, int(bottom) - int(top) + 1
    if len(rows) != height or any(not isinstance(row, list) or len(row) != width for row in rows):
        raise DeskError("Write must fill exactly the configured range; no partial or wider write")
    if any(type(v) not in (str, int, float, bool) for row in rows for v in row):
        raise DeskError("Cells must contain text, numbers, or true/false")
    if any(isinstance(v, float) and not math.isfinite(v) for row in rows for v in row):
        raise DeskError("Numbers must be finite")
    secret = load_secret(root, resource["connection"])
    token = google_token(root, resource["connection"], secret)
    base = "https://sheets.googleapis.com/v4/spreadsheets/" + urllib.parse.quote(resource["spreadsheet_id"], safe="")
    url = base + "/values/" + urllib.parse.quote(resource["range"], safe="")
    try:
        request("PUT", url + "?valueInputOption=RAW", token, {"range": resource["range"], "values": rows})
        observed = request("GET", url + "?valueRenderOption=UNFORMATTED_VALUE", token).get("values", [])
    except DeskError:
        raise DeskError("Write outcome uncertain. Read the sheet before trying again") from None
    padded = [(row + [""] * width)[:width] for row in observed]
    padded += [[""] * width for _ in range(height - len(padded))]
    if padded != rows:
        raise DeskError("Write outcome uncertain: read-back did not match. Do not retry automatically")
    return {"status": "succeeded", "range": resource["range"], "check": "readback_matched"}
