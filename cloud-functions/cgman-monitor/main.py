# -*- coding: utf-8 -*-
"""
CGMan ใบขอรถ monitor — Cloud Function (HTTP trigger, เรียกโดย Cloud Scheduler)
Flow: Gmail (เจอใบใหม่) -> Google Drive (upload folder 台帳入力/<year>/<MM>月)
      -> LINE (notify). Idempotent: เช็คไฟล์มีใน Drive แล้ว = ข้าม.
Env vars: GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN /
          LINE_CHANNEL_ID / LINE_CHANNEL_SECRET / LINE_USER_IDS (comma)
"""
import base64
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from firebase_functions import https_fn
from firebase_functions.options import SupportedRegion

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
TOKEN_URL = "https://oauth2.googleapis.com/token"
LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
SENDER = "rsv@cgman.jp"
FOLDER_MIME = "application/vnd.google-apps.folder"
BASE_DIR_PATH = ["チェー（個人）", "King BUS", "台帳入力（配車時間入力）"]
HTTP_TIMEOUT = 45


def env(key):
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"missing env var: {key}")
    return val


def _post(url, data, headers=None):
    body = urlencode(data).encode("utf-8")
    req = Request(url, data=body, headers=headers or {"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def refresh_access_token():
    resp = _post(TOKEN_URL, {
        "client_id": env("GMAIL_CLIENT_ID"),
        "client_secret": env("GMAIL_CLIENT_SECRET"),
        "refresh_token": env("GMAIL_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    })
    if "access_token" not in resp:
        raise RuntimeError(f"token refresh failed: {resp}")
    return resp["access_token"]


def month_from_filename(name):
    m = re.search(r"(?:^|[^0-9])([0-1]?\d)([0-3]?\d)(?:_|\-|\s|\.)", name)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1))
    m = re.search(r"(\d{1,2})\s*月", name)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1))
    return None


def find_drive_folder(name, parent_id, token):
    q = f"name='{name}' and '{parent_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false"
    return _get(f"{DRIVE_API}/files?q={quote(q)}&fields=files(id,name)", token).get("files", [])


def resolve_folder(path_parts, token):
    parent = "root"
    for name in path_parts:
        found = find_drive_folder(name, parent, token)
        if not found:
            meta = json.dumps({"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}).encode("utf-8")
            req = Request(f"{DRIVE_API}/files?fields=id,name", data=meta,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                found = [json.loads(resp.read().decode("utf-8"))]
        parent = found[0]["id"]
    return parent


def drive_file_exists(folder_id, name, token):
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    return bool(_get(f"{DRIVE_API}/files?q={quote(q)}&fields=files(id,name)", token).get("files"))


def upload_to_drive(folder_id, name, data, token):
    boundary = "----cgman" + uuid.uuid4().hex
    meta = json.dumps({"name": name, "parents": [folder_id]})
    head = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{meta}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    body = head + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = Request(
        f"{UPLOAD_URL}?uploadType=multipart&fields=id,name",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
    )
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_line(text):
    token = _post(LINE_TOKEN_URL, {
        "grant_type": "client_credentials",
        "client_id": env("LINE_CHANNEL_ID"),
        "client_secret": env("LINE_CHANNEL_SECRET"),
    })["access_token"]
    for uid in env("LINE_USER_IDS").split(","):
        if not uid.strip():
            continue
        body = json.dumps({"to": uid.strip(), "messages": [{"type": "text", "text": text}]}).encode("utf-8")
        req = Request("https://api.line.me/v2/bot/message/push", data=body,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            resp.read()
    print("  LINE notification sent")


def run():
    token = refresh_access_token()
    since = (datetime.now() - timedelta(days=10)).strftime("%Y/%m/%d")
    query = f"from:{SENDER} has:attachment after:{since}"
    print("Checking Gmail for sender:", SENDER, flush=True)
    result = _get(f"{GMAIL_API}/messages?q={quote(query)}&maxResults=50", token)
    messages = result.get("messages", [])
    print("Found", len(messages), "matching message(s)", flush=True)

    folder_cache = {}
    to_upload = []
    for m in messages:
        full = _get(f"{GMAIL_API}/messages/{m['id']}?format=full", token)
        email_dt = datetime.fromtimestamp(int(full.get("internalDate") or 0) / 1000)
        for p in full.get("payload", {}).get("parts", []):
            if not (p.get("filename") and p.get("body", {}).get("attachmentId")):
                continue
            name = os.path.basename(p["filename"].replace("\\", "/"))
            mm = month_from_filename(name)
            if mm is None:
                print("  cannot determine month from:", name, "- skipping", flush=True)
                continue
            year = email_dt.year
            if email_dt.month == 12 and mm <= 2:
                year += 1
            key = f"{year}-{mm}"
            if key not in folder_cache:
                folder_cache[key] = resolve_folder(BASE_DIR_PATH + [str(year), f"{mm}月"], token)
            folder_id = folder_cache[key]
            if drive_file_exists(folder_id, name, token):
                print("  already in Drive, skip:", name, flush=True)
                continue
            att = _get(f"{GMAIL_API}/messages/{m['id']}/attachments/{p['body']['attachmentId']}", token)
            raw = att["data"].replace("-", "+").replace("_", "/")
            raw += "=" * ((4 - len(raw) % 4) % 4)
            to_upload.append((name, base64.b64decode(raw), folder_id))
            print("  new file:", name, len(to_upload[-1][1]), "bytes", flush=True)

    for name, data, folder_id in to_upload:
        up = upload_to_drive(folder_id, name, data, token)
        print("  uploaded:", up.get("name"), up.get("id"), flush=True)

    if to_upload:
        names = "\n".join(n for n, _, _ in to_upload)
        send_line(f"📥 King BUS ใบขอรถใหม่ ({len(to_upload)} ไฟล์)\n\n{names}")

    msg = f"uploaded {len(to_upload)} file(s)." if to_upload else "no new files."
    print("Done.", msg, flush=True)
    return len(to_upload)


@https_fn.on_request(region=SupportedRegion.ASIA_SOUTHEAST1)
def cgman_monitor(req: https_fn.Request) -> https_fn.Response:
    try:
        n = run()
        return https_fn.Response(f"OK {n} file(s)", status=200)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return https_fn.Response(f"ERROR: {e}", status=500)
