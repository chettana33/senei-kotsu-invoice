# -*- coding: utf-8 -*-
"""
CGMan ใบขอรถ monitor — Cloud Function (HTTP trigger, เรียกโดย Cloud Scheduler)
Flow: Gmail (เจอใบใหม่) -> Google Drive (upload folder 台帳入力/<year>/<MM>月)
      -> LINE (notify). Idempotent: เช็คไฟล์มีใน Drive แล้ว = ข้าม.
Env vars: GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN /
          LINE_CHANNEL_ID / LINE_CHANNEL_SECRET / LINE_USER_IDS (comma)
"""
import base64
import hashlib
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
# 13 พ.ย. 69 (มติพี่เจ "ลุย A"): state ของ "เมลที่ประมวลผลแล้ว" — กันสแกนเมลเดิมซ้ำทุก 5 นาที
# ต้นเหตุเคสจริง: 1 เมล ถูกสแกน 2 รอบ ⇒ รอบ 2 เจอชื่อไฟล์ซ้ำ เข้าเงื่อนไข "เวอร์ชันใหม่" (L167)
# ⇒ เซฟ `(MMDD)` ซ้ำ + แจ้ง LINE ซ้ำ + taicho-monitor apply ซ้ำ (変更なし) ทุกวัน
STATE_NAME = "_processed_cgman.json"
STATE_KEEP_DAYS = 60


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


def _get_bytes(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def drive_file_meta(folder_id, name, token):
    """metadata ของไฟล์ชื่อนี้ (id/size/md5Checksum) — เลือกไฟล์ที่ใหม่สุดถ้ามีชื่อซ้ำหลายไฟล์"""
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    files = _get(f"{DRIVE_API}/files?q={quote(q)}"
                 f"&fields=files(id,name,size,md5Checksum)&orderBy=modifiedTime desc", token).get("files", [])
    return files[0] if files else None


def drive_file_id(folder_id, name, token):
    meta = drive_file_meta(folder_id, name, token)
    return meta["id"] if meta else None


def load_state(folder_id, token):
    """{messageId: 'YYYY-MM-DD'} ของเมลที่ทำแล้ว

    มีไฟล์แต่อ่านไม่ได้ = **โยน error** (ไม่เดาว่าว่าง) — กันเคสเดียวกับ `taicho-monitor` 10 ก.ย. 69:
    อ่าน state พังชั่วคราวแล้ว bootstrap ใหม่ = สแกน 10 วันซ้ำทั้งชุด (ประวัติศาสตร์ถูกเขียนทับหาย)
    """
    fid = drive_file_id(folder_id, STATE_NAME, token)
    if not fid:
        return {}
    raw = _get_bytes(f"{DRIVE_API}/files/{fid}?alt=media", token).decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"state format ผิด (คาด dict, ได้ {type(data).__name__})")
    return data


def save_state(folder_id, state, token):
    """เขียนทับ state (ตัดรายการเก่ากว่า STATE_KEEP_DAYS) — พังแล้วไม่ทำให้รอบล้ม"""
    cutoff = (datetime.now() - timedelta(days=STATE_KEEP_DAYS)).strftime("%Y-%m-%d")
    state = {k: v for k, v in state.items() if v >= cutoff}
    body = json.dumps(state, ensure_ascii=False).encode("utf-8")
    try:
        fid = drive_file_id(folder_id, STATE_NAME, token)
        if fid:
            # 🔴 13 พ.ย. 69 (review Critical): `files.update` ของ Drive v3 ต้องเป็น PATCH เท่านั้น
            # (ไม่ระบุ method = urllib ส่ง POST ⇒ 4xx ทุกครั้งแล้วถูกกลืน ⇒ state อัปเดตไม่เคยสำเร็จ)
            # หลักฐานแบบอย่างในเรป: cloud-functions/taicho-monitor/main.py:174-178 (lessons #81)
            req = Request(
                f"{UPLOAD_URL}/{fid}?uploadType=media&fields=id",
                data=body,
                method="PATCH",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        else:
            # สร้างใหม่: ต้องมีชื่อ+parent ⇒ ใช้ multipart (uploadType=media ไม่รับ meta)
            boundary = "----cgs" + uuid.uuid4().hex
            meta = json.dumps({"name": STATE_NAME, "parents": [folder_id]})
            payload = (
                f"--{boundary}\r\n"
                "Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{meta}\r\n"
                f"--{boundary}\r\n"
                "Content-Type: application/json\r\n\r\n"
            ).encode("utf-8") + body + f"\r\n--{boundary}--\r\n".encode("utf-8")
            req = Request(
                f"{UPLOAD_URL}?uploadType=multipart&fields=id",
                data=payload,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": f"multipart/related; boundary={boundary}"},
            )
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            resp.read()
        return True
    except Exception as e:  # noqa: BLE001
        print("  cannot save state:", e, flush=True)
        return False


def fetch_attachment(msg_id, part, token):
    att = _get(f"{GMAIL_API}/messages/{msg_id}/attachments/{part['body']['attachmentId']}", token)
    raw = att["data"].replace("-", "+").replace("_", "/")
    raw += "=" * ((4 - len(raw) % 4) % 4)
    return base64.b64decode(raw)


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


def iter_parts(payload):
    """ไล่ part ทุกชั้น (Gmail ซ้อน multipart/mixed → related ได้) — เดิมอ่านชั้นเดียว = ใบหายเงียบ"""
    for p in payload.get("parts") or []:
        if p.get("parts"):
            yield from iter_parts(p)
        else:
            yield p


def run():
    token = refresh_access_token()
    # 13 พ.ย. 69: state อยู่ที่โฟลเดอร์ 台帳入力 ตัวเดียว (ไม่ผูกปี/เดือน)
    state_folder = resolve_folder(BASE_DIR_PATH, token)
    state = load_state(state_folder, token)
    since = (datetime.now() - timedelta(days=10)).strftime("%Y/%m/%d")
    query = f"from:{SENDER} has:attachment after:{since}"
    print("Checking Gmail for sender:", SENDER, flush=True)
    result = _get(f"{GMAIL_API}/messages?q={quote(query)}&maxResults=50", token)
    messages = result.get("messages", [])
    print("Found", len(messages), "matching message(s)", flush=True)

    folder_cache = {}
    to_upload = []
    done_ids = []
    seen_names = set()  # (folder, name) ที่คิวไว้แล้วในรอบนี้ — กัน attachment ชื่อซ้ำในเมลเดียว
    today = datetime.now().strftime("%Y-%m-%d")
    for m in messages:
        if m["id"] in state:
            print("  already processed (state), skip msg:", m["id"], flush=True)
            continue
        full = _get(f"{GMAIL_API}/messages/{m['id']}?format=full", token)
        email_dt = datetime.fromtimestamp(int(full.get("internalDate") or 0) / 1000)
        parts = [p for p in iter_parts(full.get("payload", {}))
                 if p.get("filename") and p.get("body", {}).get("attachmentId")]
        skipped = 0  # จำนวน attachment ที่ยังตัดสินไม่ได้ ⇒ ไม่ mark processed (รอบหน้าลองใหม่)
        for p in parts:
            name = os.path.basename(p["filename"].replace("\\", "/"))
            mm = month_from_filename(name)
            if mm is None:
                print("  cannot determine month from:", name, "- skipping", flush=True)
                skipped += 1
                continue
            year = email_dt.year
            if email_dt.month == 12 and mm <= 2:
                year += 1
            key = f"{year}-{mm}"
            if key not in folder_cache:
                folder_cache[key] = resolve_folder(BASE_DIR_PATH + [str(year), f"{mm}月"], token)
            folder_id = folder_cache[key]
            if (folder_id, name) in seen_names:
                print("  duplicate attachment in this run, skip:", name, flush=True)
                continue
            data = None
            meta = drive_file_meta(folder_id, name, token)
            if meta:
                # 🔴 11 พ.ย. 69 (มติพี่เจ): 千栄 ตั้งชื่อไฟล์ซ้ำได้ — ส่ง `1110_…xlsx` ทั้ง 10 และ 11 พ.ย.
                # (612,341 / 608,433 B · เนื้อใหม่) ⇒ เดิมโค้ดข้ามเพราะชื่อซ้ำ ทำให้ "ใบของวันนี้" ไม่เคยลง Drive
                # ⇒ ไม่มี apply · ไม่มี PDF (เคสจริง 11 พ.ย. 69). ตอนนี้เก็บเวอร์ชันใหม่เป็น base(MMDD ที่เมล์เข้า).ext
                #   = รูปแบบเดียวกับที่พี่เจแก้มือ (…(1111).xlsx) และ taicho_pdf_auto อ่านวันจาก mtime อยู่แล้ว
                base, ext = os.path.splitext(name)
                alt = f"{base}({email_dt.strftime('%m%d')}){ext}"
                if alt == name or drive_file_exists(folder_id, alt, token):
                    print("  already in Drive, skip:", name, flush=True)
                    continue
                # 🔴 13 พ.ย. 69: "ชื่อซ้ำ" ไม่เท่ากับ "เนื้อใหม่" — เมลเดิมถูกสแกนซ้ำก็เข้าทางนี้ได้
                # ⇒ เทียบ size (ฟรี) + md5Checksum จาก metadata ของ Drive (ไม่ต้องโหลดไฟล์เดิมซ้ำ)
                # เคสจริง 13 พ.ย. 16:40/16:45: เนื้อเดียวกัน ⇒ ต้องข้าม ไม่ใช่เซฟ `(1113)` ซ้ำ
                same_size = str(meta.get("size", "")) == str(p.get("body", {}).get("size", ""))
                if same_size:
                    old_md5 = meta.get("md5Checksum")
                    if not old_md5:
                        # อ่าน md5 ไม่ได้ = ตัดสินไม่ได้ ⇒ ข้ามรอบนี้ (fail-closed) แล้วลองใหม่รอบหน้า
                        print("  อ่าน md5 ของไฟล์เดิมไม่ได้ -> ข้ามรอบนี้ก่อน:", name, flush=True)
                        skipped += 1
                        continue
                    data = fetch_attachment(m["id"], p, token)
                    if old_md5 == hashlib.md5(data).hexdigest():
                        print("  same content as file in Drive -> skip:", name, flush=True)
                        continue
                else:
                    print("  existing file size ต่างกัน = เนื้อใหม่", flush=True)
                if data is None:
                    data = fetch_attachment(m["id"], p, token)
                print(f"  same name for NEW content -> save as: {alt}", flush=True)
                name = alt
            else:
                data = fetch_attachment(m["id"], p, token)
            if data is None:
                continue
            seen_names.add((folder_id, name))
            to_upload.append((name, data, folder_id))
            print("  new file:", name, len(data), "bytes", flush=True)
        if not skipped:
            done_ids.append(m["id"])
        else:
            print(f"  msg {m['id']}: ยังมี {skipped} attachment ที่ตัดสินไม่ได้ -> ไม่จด state", flush=True)

    for name, data, folder_id in to_upload:
        up = upload_to_drive(folder_id, name, data, token)
        print("  uploaded:", up.get("name"), up.get("id"), flush=True)

    # 13 พ.ย. 69: จด state ก่อนแจ้ง LINE — ถ้าแจ้งเตือนไม่ผ่าน จะไม่เกิดไฟล์/ข้อความซ้ำรอบหน้า
    if done_ids:
        for mid in done_ids:
            state[mid] = today
        save_state(state_folder, state, token)

    if to_upload:
        names = "\n".join(n for n, _, _ in to_upload)
        send_line(f"📥 King BUS ใบขอรถใหม่ ({len(to_upload)} ไฟล์)\n\n{names}")

    msg = f"uploaded {len(to_upload)} file(s)." if to_upload else "no new files."
    print("Done.", msg, flush=True)
    return len(to_upload)


@https_fn.on_request(region=SupportedRegion.ASIA_SOUTHEAST1, concurrency=1, max_instances=1)
def cgman_monitor(req: https_fn.Request) -> https_fn.Response:
    # 13 พ.ย. 69 (review Major): กัน invocation ซ้อน — taicho-monitor ตั้งแบบนี้แล้ว (เคสจริง 1 ต.ค. 69
    # รอบ 09:00 timeout แล้ว 09:01 ยิงทับ ⇒ apply ซ้ำ). ที่นี่ถ้าซ้อนกันจะเกิดไฟล์ชื่อซ้ำใน Drive
    try:
        n = run()
        return https_fn.Response(f"OK {n} file(s)", status=200)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return https_fn.Response(f"ERROR: {e}", status=500)
