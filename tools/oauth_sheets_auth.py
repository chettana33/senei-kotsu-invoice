#!/usr/bin/env python3
"""Get a Google OAuth refresh token that includes the Sheets API scope.

Opens the browser for the user to authorize once, then stores a new
credentials file alongside the existing one. Does NOT touch existing tokens.
"""
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CRED_SRC = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.json"
OUT = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.sheets.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
PORT = 8080
REDIRECT = f"http://localhost:{PORT}"

received = threading.Event()
auth_code = None
state = "taicho-sheets-2026"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        global auth_code
        q = urllib.parse.urlparse(self.path)
        if q.path != "/":
            self.send_error(404)
            return
        params = urllib.parse.parse_qs(q.query)
        if params.get("state", [""])[0] != state:
            self.send_error(403, "state mismatch")
            return
        auth_code = params.get("code", [None])[0]
        body = b"<html><body><h2>OK - you can close this tab.</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        received.set()

    def log_message(self, *a):  # silence
        pass


def main():
    with open(CRED_SRC) as f:
        cred = json.load(f)
    inst = cred.get("installed") or cred
    client_id = cred.get("client_id") or inst["client_id"]
    client_secret = cred.get("client_secret") or inst["client_secret"]

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    print("Opening browser for Google authorization...")
    webbrowser.open(auth_url)
    print(f"Waiting for redirect on {REDIRECT} ...")
    if not received.wait(timeout=300):
        print("TIMEOUT: no authorization received.")
        server.shutdown()
        sys.exit(1)
    server.shutdown()

    if not auth_code:
        print("No code received. Aborting.")
        sys.exit(1)

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    tok = json.load(urllib.request.urlopen(req, timeout=30))

    new_cred = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tok["refresh_token"],
        "token_uri": "https://oauth2.googleapis.com/token",
        "scope": tok.get("scope", ""),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(new_cred, f, ensure_ascii=False, indent=2)
    print("Saved new credentials ->", OUT)
    print("Scopes:", tok.get("scope", ""))
    print("DONE")


if __name__ == "__main__":
    main()
