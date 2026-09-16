"""Local Google desktop sign-in. No credentials pass through the agent."""
import base64
import hashlib
import http.server
import json
import secrets
import time
import urllib.parse
import webbrowser
from .adapters import request
from .control import slug
from .store import DeskError, atomic_json

SCOPES = {
    "sheets-read": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "sheets-write": "https://www.googleapis.com/auth/spreadsheets",
    "calendar-read": "https://www.googleapis.com/auth/calendar.readonly",
    "drive-backup": "https://www.googleapis.com/auth/drive.file",
}


def connect(store, name, client_file, scopes):
    slug(name)
    if not scopes or set(scopes) - SCOPES.keys():
        raise DeskError("Choose named Google scopes from the installation guide")
    client = json.loads(client_file.read_text()).get("installed", {})
    if not client.get("client_id") or not client.get("client_secret"):
        raise DeskError("Use a Google Desktop app OAuth client file")
    csrf, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    received = {}
    class Callback(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            valid = parsed.path == "/callback" and secrets.compare_digest(query.get("state", [""])[0], csrf)
            if valid: received.update(query)
            self.send_response(200 if valid else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"You may return to the Puestario installer." if valid else b"Unrecognized sign-in request.")
    with http.server.HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 2
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        query = {"client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
                 "scope": " ".join(SCOPES[s] for s in scopes), "state": csrf,
                 "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"}
        if not webbrowser.open("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(query)):
            raise DeskError("Open a local browser and run sign-in again")
        deadline = time.monotonic() + 300
        while not received and time.monotonic() < deadline: server.handle_request()
    if not received.get("code") or received.get("error"):
        raise DeskError("Google sign-in was cancelled or timed out")
    token = request("POST", "https://oauth2.googleapis.com/token", payload={
        "client_id": client["client_id"], "client_secret": client["client_secret"], "code": received["code"][0],
        "code_verifier": verifier, "redirect_uri": redirect, "grant_type": "authorization_code"}, form=True)
    if not token.get("refresh_token") or not token.get("access_token"):
        raise DeskError("Google did not grant offline access; sign-in was not saved")
    atomic_json(store.root / "secrets" / (name + ".json"), {"client_id": client["client_id"],
        "client_secret": client["client_secret"], "refresh_token": token["refresh_token"], "access_token": token["access_token"],
        "expires_at": time.time() + int(token.get("expires_in", 0)), "scopes": scopes})
    return {"sign_in_saved": True, "connection": name, "connected": False,
            "next": "Configure the exact business resource and run connection.check to verify its account"}
