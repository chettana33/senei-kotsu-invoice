# -*- coding: utf-8 -*-
"""
台帳 auto update — Cloud Function (Firebase gen2, HTTP) — cloud version ของ taicho_auto.py
Flow: Drive (ใบขอรถ xlsx ใหม่) -> diff 台帳 -> apply sheets -> LINE (text + webapp link)
PDF: สร้างที่เครื่องเท่านั้น (HTML+Edge, emoji ตัวจริง — พี่เจ reject reportlab PNG 7 ก.ย. 69)
      ใช้ tools/taicho_pdf.py + ตรวจ tools/taicho_qa.py — ดู system-rules/taicho.md
State (processed + last_flag_date) = ไฟล์ JSON ใน Drive root (taicho_cloud_state.json)
Env: SHEETS_CLIENT_ID / SHEETS_CLIENT_SECRET / SHEETS_REFRESH_TOKEN (kimonoland sheets token,
     scope มี drive ด้วย — ใช้เรียก Drive API) / LINE_CHANNEL_ID / LINE_CHANNEL_SECRET / LINE_USER_IDS
"""
import base64
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import datetime as _dt
from collections import Counter
from datetime import date

from firebase_functions import https_fn
from firebase_functions.options import SupportedRegion
import openpyxl

SHEET_ID = "1H2WE2D8ZXrAI4jdOUm2N6DYGCWVD1SrYy9BqAfRFdC0"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_API = "https://www.googleapis.com/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
FORM_RE = re.compile(r"(\d{4})_千栄交通㈱_貸切バス手配依頼書(?:\(\d+\))?\.xlsx$")
TAB_MONTHS = {"26.8": 8, "26.9": 9, "26.10": 10, "26.11": 11, "26.12": 12,
              "27.01": 1, "27.02": 2, "27.03": 3}
DRIVE_PATH = ["チェー（個人）", "King BUS", "台帳入力（配車時間入力）"]
MONTH_BLOCK = 16
DAYS_IN_MONTH = {8: 30, 9: 30, 10: 31}
HEADER_COLOR = {1: (1, 0.9, 0.4), 2: (0.75, 0.75, 0.75), 3: (1, 0.65, 0.3),
                4: (0.6, 0.8, 1), 5: (1, 0.75, 0.8), 6: (0.7, 0.9, 0.7),
                7: (1, 0.9, 0.4), 8: (1, 0.65, 0.3), 9: (0.6, 0.8, 1),
                10: (1, 0.75, 0.8), 11: (0.7, 0.9, 0.7), 12: (1, 0.65, 0.3)}
STATE_NAME = "taicho_cloud_state.json"
TAICHO_WEBAPP_URL = ("https://script.google.com/macros/s/"
                     "AKfycbym-XXro-jSHP1yO2wgmV4RfNVSPyOFcJdiutRjSfTbEfwkODJxcDySGQ_oZN1rYQbc2A/exec")
SHORT_TAICHO_URL = "https://taicho-link.vercel.app"
# D2 ทิศทาง (พี่เจอนุมัติ 5 ก.ย. 69): ซ้าย=出発(จาก) ขวา=行先(ไป), 空=ฟ้า ホ=ส้ม
ROUTE_CODE = {"HTL": "ホ", "AP1": "空", "AP2": "空"}
C_BLUE = {"red": 0.12, "green": 0.38, "blue": 0.85}
C_ORANGE = {"red": 0.87, "green": 0.42, "blue": 0.06}
LEGEND_ROWS = ["変更は🟡", "新規は🟢", "ホ＝ホテル（橙）　空＝空港（青）　左=出発　右=行先"]


def env(key):
    v = os.environ.get(key)
    if not v:
        raise RuntimeError(f"missing env var: {key}")
    return v


# ---------------- tokens ----------------

def sheets_token():
    body = urllib.parse.urlencode({
        "client_id": env("SHEETS_CLIENT_ID"), "client_secret": env("SHEETS_CLIENT_SECRET"),
        "refresh_token": env("SHEETS_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def _api(method, url, token=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token or sheets_token()}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def _get_media(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


# ---------------- LINE ----------------

def send_line(text):
    cfg_body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": env("LINE_CHANNEL_ID"), "client_secret": env("LINE_CHANNEL_SECRET")}).encode()
    req = urllib.request.Request(LINE_TOKEN_URL, data=cfg_body)
    with urllib.request.urlopen(req, timeout=30) as r:
        lt = json.loads(r.read())["access_token"]
    for uid in env("LINE_USER_IDS").split(","):
        if not uid.strip():
            continue
        body = json.dumps({"to": uid.strip(),
                           "messages": [{"type": "text", "text": text}]}).encode()
        req = urllib.request.Request("https://api.line.me/v2/bot/message/push", data=body,
                                     headers={"Authorization": f"Bearer {lt}",
                                              "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
    print("  LINE sent:", text.splitlines()[0][:60], flush=True)


# ---------------- Drive: state + forms ----------------

def drive_find_folder(name, parent, token):
    q = f"name='{name}' and '{parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    r = _api("GET", f"{DRIVE_API}/files?q={urllib.parse.quote(q)}&fields=files(id,name)", token)
    return (r.get("files") or [{}])[0].get("id")


def drive_resolve(path_parts, token):
    parent = "root"
    for name in path_parts:
        found = drive_find_folder(name, parent, token)
        if not found:
            meta = json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder",
                               "parents": [parent]}).encode()
            req = urllib.request.Request(f"{DRIVE_API}/files?fields=id", data=meta, method="POST",
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Content-Type": "application/json"})
            found = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("id")
        parent = found
    return parent


def state_file_id(token):
    q = f"name='{STATE_NAME}' and trashed=false"
    r = _api("GET", f"{DRIVE_API}/files?q={urllib.parse.quote(q)}&fields=files(id)", token)
    files = r.get("files") or []
    if files:
        return files[0]["id"]
    meta = json.dumps({"name": STATE_NAME, "mimeType": "application/json"}).encode()
    req = urllib.request.Request(f"{DRIVE_API}/files?fields=id", data=meta, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read()).get("id")


class StateReadError(Exception):
    """อ่าน state ไม่ได้ (Drive/JSON เสีย) — ห้ามเดาว่า state ว่าง (10 ก.ย. 69)

    เดิม load_state คืน {"processed": []} ทุกกรณี → ถ้า Drive ตอบ 429/5xx ชั่วคราว
    bootstrap จะมองว่าเป็น state ใหม่ → mark ใบเก่า + ประมวลผลใบใหม่สุด = apply ทับ + LINE ซ้ำ
    """


def load_state(token):
    fid = state_file_id(token)
    try:
        raw = _get_media(f"{DRIVE_API}/files/{fid}?alt=media", token)
    except Exception as e:  # noqa: BLE001
        raise StateReadError(f"โหลด state ไม่ได้: {type(e).__name__}: {e}") from e
    if not raw.strip():  # ไฟล์ว่างจริง = ติดตั้งใหม่
        return {"processed": []}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise StateReadError(f"state ไม่ใช่ JSON: {type(e).__name__}: {e}") from e


def save_state(state, token):
    fid = state_file_id(token)
    data = json.dumps(state, ensure_ascii=False).encode()
    # media upload ต้องใช้ upload domain (/upload/drive/v3) — drive host กับ uploadType=media
    # ตอบ 200 แต่ไม่เขียน (lessons #81) — state เลยไม่เคยบันทึกตั้งแต่ phase 2a
    req = urllib.request.Request(f"https://www.googleapis.com/upload/drive/v3/files/{fid}?uploadType=media",
                                 data=data, method="PATCH",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


# ---------------- PDF: ถอดออกจาก cloud แล้ว (7 ก.ย. 69) ----------------
# PDF 台帳 ต้อง HTML+Edge ที่เครื่องเท่านั้น (emoji ตัวจริง — พี่เจ reject reportlab PNG, lessons #82)
# ดู rules: 00_SOP_Master/01_AI_Protocols/system-rules/taicho.md + QA: tools/taicho_qa.py
# cloud function นี้ = apply + LINE เท่านั้น (PDF สร้างที่เครื่อง: python tools/taicho_pdf.py pdf --date MMDD)

def pdf_filename(mm, mmdd):
    """ชื่อไฟล์ PDF ตามเดือนไส้ใน (ตรง tools/taicho_gsheets.py pdf_filename):
    mm=9 -> '9月-12月', mm=10 -> '10月-01月'; ปี = 2026 ถ้า mm>=8 else 2027."""
    m3 = mm + 3
    if m3 > 12:
        m3 -= 12
    year = 2026 if mm >= 8 else 2027
    return f"{year}台帳 - 千栄1568 - {mm}月-{m3:02d}月({mmdd}).pdf"


def _drive_find_file(name, parent, token):
    q = f"name='{name}' and '{parent}' in parents and trashed=false"
    r = _api("GET", f"{DRIVE_API}/files?q={urllib.parse.quote(q)}&fields=files(id,name)", token)
    return (r.get("files") or [{}])[0].get("id")


def list_forms(token):
    """คืน [(mmdd, file_id, name, modifiedTime)] เรียง mmdd จากทุก folder เดือนที่เกี่ยวข้อง
    (9 ก.ย. 69: เพิ่ม modifiedTime — ใช้กันข้ามไฟล์ชื่อซ้ำที่ 千栄 ส่งซ้ำ)"""
    found = []
    for year, months in ((2026, [8, 9, 10, 11, 12]), (2027, [1, 2, 3])):
        for mm in months:
            try:
                folder = drive_resolve(DRIVE_PATH + [str(year), f"{mm}月"], token)
            except Exception:
                continue
            q = f"'{folder}' in parents and trashed=false"
            r = _api("GET", f"{DRIVE_API}/files?q={urllib.parse.quote(q)}&fields=files(id,name,modifiedTime)", token)
            for f in r.get("files") or []:
                m = FORM_RE.match(f["name"])
                if m:
                    found.append((m.group(1), f["id"], f["name"], f.get("modifiedTime", "")))
    return sorted(found, key=lambda t: t[0])


# ---------------- sheets 台帳 ----------------

def find_main_tab():
    d = _api("GET", f"{SHEETS_API}/{SHEET_ID}?fields=sheets(properties(title,sheetId))")
    best = None
    for s in d["sheets"]:
        m = re.match(r"^千栄1568 (\d+)月-\d+月", s["properties"]["title"])
        if m:
            m0 = int(m.group(1))
            if best is None or m0 > best[0]:
                best = (m0, s["properties"]["title"], s["properties"]["sheetId"])
    return (best[1], best[2]) if best else (None, None)


def sheets_get(values_range):
    name, _ = find_main_tab()
    if not name:
        raise RuntimeError("ไม่พบ tab 台帳 หลัก")
    rng = urllib.parse.quote(f"'{name}'!{values_range}")
    return _api("GET", f"{SHEETS_API}/{SHEET_ID}/values/{rng}?majorDimension=ROWS")


def sheets_update(values_range, values):
    name, _ = find_main_tab()
    if not name:
        raise RuntimeError("ไม่พบ tab 台帳 หลัก")
    rng = urllib.parse.quote(f"'{name}'!{values_range}")
    return _api("PUT", f"{SHEETS_API}/{SHEET_ID}/values/{rng}?valueInputOption=USER_ENTERED",
                body={"values": values})


def batch_update(requests, gid=None):
    return _api("POST", f"{SHEETS_API}/{SHEET_ID}:batchUpdate", body={"requests": requests})


def month_sections(rows, base_row):
    sections = {}
    for i, row in enumerate(rows):
        a = row[0] if row else None
        if a and isinstance(a, str):
            m = re.search(r"(\d+)月", a)
            if m:
                sections[int(m.group(1))] = base_row + i + 3
    return sections


def col_for_day(day):
    n = 1 + day
    if n <= 26:
        return chr(ord("A") + n - 1)
    return "A" + chr(ord("A") + n - 27)


def read_taicho():
    res = sheets_get("A1:AG80")
    rows = res.get("values", [])
    sections = month_sections(rows, 1)
    taicho = {}
    for month, entry_row in sections.items():
        idx = entry_row - 1
        entry = rows[idx] if idx < len(rows) else []
        cells = {}
        for day in range(1, 32):
            c = col_for_day(day)
            ci = ord(c[0]) - ord("A") if len(c) == 1 else (ord(c[0]) - ord("A")) * 26 + ord(c[1]) - ord("A") + 26
            v = entry[ci] if ci < len(entry) else None
            if v not in (None, ""):
                cells[day] = v
        ndays = DAYS_IN_MONTH.get(month, 30)
        hidx = idx - 3
        if hidx >= 0:
            hdr = rows[hidx] if hidx < len(rows) else []
            nums = []
            for v in hdr[1:]:
                try:
                    n = int(v)
                    if 1 <= n <= 31:
                        nums.append(n)
                except (TypeError, ValueError):
                    pass
            if nums:
                ndays = max(nums)
        taicho[month] = {"row": entry_row, "cells": cells, "ndays": ndays}
    return taicho


# ---------------- ใบขอรถ ----------------

def serial_to_date(n):
    if isinstance(n, _dt.datetime):
        return n.date()
    if isinstance(n, (int, float)):
        return (_dt.datetime(1899, 12, 30) + _dt.timedelta(days=n)).date()
    return None


def fmt_time(c):
    if isinstance(c, _dt.time):
        return c.strftime("%H:%M")
    if isinstance(c, str):
        if "→" in c:
            c = c.split("→")[-1].strip()
        c = re.sub(r"\s+", "", c)
        if re.match(r"^\d{1,2}[:：]\d{2}$", c):
            hh, mm = re.split(r"[:：]", c)
            return f"{int(hh):02d}:{mm}"
    return None


def hours_from(keiyu):
    if keiyu:
        m = re.search(r"\((\d+)H\)", str(keiyu))
        if m:
            return f"{m.group(1)}H"
    return None


def col_index(col):
    """'A'->0 ... 'Z'->25, 'AA'->26 ..."""
    if len(col) == 1:
        return ord(col[0]) - 65
    return (ord(col[0]) - 65) * 26 + (ord(col[1]) - 65) + 26


def d2_text(entry):
    """entry {t, h?, D, G} -> ข้อความ D2: 'ホ 10:00 2H 空' (ไม่มีรหัส D/G = คงแบบเดิม '10:00 2H')"""
    o = ROUTE_CODE.get(entry.get("D", "")) or ""
    g2 = ROUTE_CODE.get(entry.get("G", "")) or ""
    t = entry["t"]
    h = entry.get("h") or ""
    mid = f"{t}" + (f" {h}" if h else "")
    if o and g2:
        return f"{o} {mid} {g2}"
    return mid


def color_runs(text):
    """runs สี: ทุก 空 = ฟ้า, ホ = ส้ม (textFormatRuns มีแค่ startIndex + format)"""
    runs = []
    off = 0
    for ch in text:
        n = len(ch.encode("utf-16-le")) // 2
        col = C_BLUE if ch == "空" else C_ORANGE if ch == "ホ" else None
        if col:
            runs.append({"startIndex": off, "format": {"foregroundColor": col}})
        off += n
    return runs


def parse_form_bytes(data):
    """อ่านใบขอรถ -> {date: [entry]} โดย entry = {t, h, D, G} (D=配車場所 col D, G=行先 col G)
    วันที่ใบระบุ キャンセล (col J) ทั้งหมด = คิวถูกยกเลิก -> ฝาก {date: []} ให้ build_plan เห็น
    แล้วลบจาก master (บั๊ก 9 ก.ย. 69: 10/8 cancel-only day ไม่เคยลบ)"""
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    out = {}
    cancelled_only = set()
    for tab, month in TAB_MONTHS.items():
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]
        for r in range(10, ws.max_row + 1):
            n = ws.cell(row=r, column=14).value
            d = serial_to_date(n)
            if d is None or d.month != month or d.year not in (2026, 2027):
                continue
            j = ws.cell(row=r, column=10).value
            if j and "キャンセル" in str(j):
                cancelled_only.add(d)  # จดไว้ — หลัง loop ฝากวันว่างให้ build_plan ลบ
                continue
            c = fmt_time(ws.cell(row=r, column=3).value)
            if c is None:
                continue
            e = ws.cell(row=r, column=5).value
            f = ws.cell(row=r, column=6).value
            h = hours_from(e) or hours_from(f)
            D = str(ws.cell(row=r, column=4).value or "").strip()
            G = str(ws.cell(row=r, column=7).value or "").strip()
            out.setdefault(d, []).append({"t": c, "h": h, "D": D, "G": G})
    for d in cancelled_only:
        out.setdefault(d, [])  # วันที่มีแต่ cancel -> ว่าง (plan: ลบ)
    def _tk(e):
        return tuple(re.match(r"(\d{2}):(\d{2})", e["t"]).groups())
    return {d: sorted(v, key=_tk) for d, v in out.items()}


def strip_flags(s):
    """ตัด flag 🟡/🟢 (+ ช่องว่างหน้า flag) และช่องว่างท้ายบรรทัด (ตรงกับ tools/taicho_gsheets.py)"""
    lines = [re.sub(r"\s*[🟡🟢]", "", ln).rstrip() for ln in (s or "").split("\n")]
    return "\n".join(lines).rstrip("\n")


def line_time(line):
    """เวลาออกตัวของบรรทัด (HH:MM) — ใช้จับคู่ว่าเป็นช่องเวลาเดิมหรือช่องใหม่
    รับ 全角コロン '：' ด้วย (เซลล์พิมพ์มือ/ของเก่า) แล้วคืนรูป 半角 เสมอ"""
    m = re.search(r"(\d{2})[:：](\d{2})", line or "")
    return f"{m.group(1)}:{m.group(2)}" if m else None


def _line_plain(line):
    """เนื้อบรรทัดสำหรับเทียบ (ตัด flag 🟡🟢 + 🔷 + ช่องว่างซ้ำ)"""
    s = re.sub(r"[🟡🟢🔷]", "", line or "")
    return re.sub(r"\s+", " ", s).strip()


def _flag_of(line):
    """flag ที่บรรทัดนี้ติดอยู่ ('' = ไม่ติด)"""
    for f in ("🟢", "🟡"):
        if f in (line or ""):
            return f
    return ""


D2_RE = re.compile(r"^(?:[ホ空]\s*)?\d{1,2}[:：]\d{2}(?:\s+\d+H)?(?:\s+[ホ空])?$")


def _foreign_lines(text):
    """บรรทัดที่ระบบสร้างไม่ได้เอง — 🔷 หรือไม่ตรงรูปแบบ D2 **ทั้งบรรทัด** (เช่น 'ホ 06:00 空 迎車',
    '運転手: 佐藤', 'ホテル 06:00 空') — ห้ามเขียนทับเงียบ ๆ
    (gate เทียบข้อความเต็ม: ถ้าไม่กันไว้ = เขียนทับแล้วบรรทัดนั้นหาย; ตรวจทั้งบรรทัดเพื่อไม่ให้ข้อความ
    ต่อท้ายบรรทัดที่ถูกต้องหลุด — review 10 ก.ย. 69)"""
    out = []
    for ln in (text or "").split("\n"):
        raw = ln.strip()
        s = strip_flags(ln).strip()
        if s and ("🔷" in s or not D2_RE.match(s)):
            out.append(raw)
    return out


def norm_cell(text):
    """ข้อความเซลล์แบบเทียบ: ตัดช่องว่างท้ายบรรทัด + บรรทัดว่าง (แต่ **ไม่ตัด flag**)
    — ใช้เป็น condition เขียนจริง: จับ flag ที่ผิด/ทิศทาง 空↔ホ เปลี่ยน แต่ไม่เขียนทิ้งเพราะช่องว่างล้วน"""
    return "\n".join(ln.rstrip() for ln in (text or "").split("\n") if ln.strip())


def plan_cell_text(cur_str, entries):
    """ข้อความเซลล์ + flag **ต่อบรรทัด**: 🟢 = เที่ยวใหม่ (ไม่มีในเซลล์เดิม) ·
    🟡 = เที่ยวเดิม (เวลา+ชั่วโมงตรง) แต่เนื้อเปลี่ยน · ไม่ติด = เท่าเดิม

    แก้ 10 ก.ย. 69 (พี่เจแจ้ง): เดิมต่อ " 🟢" ท้ายเซลล์เสมอ → ไปติดบรรทัดสุดท้ายที่ไม่ได้เปลี่ยน
    (เคสจริง 10月26: ลบ 18:30 ออก แต่ 🟢 ไปติด 06:00 = ผิด). ลบเที่ยว = ไม่มี flag (削除 แจ้งทาง LINE)
    """
    bucket = {}  # เวลา -> [บรรทัดเดิมที่ยังไม่ถูกจับคู่] (คงลำดับในเซลล์)
    for old in (cur_str or "").split("\n"):
        if old.strip():
            bucket.setdefault(line_time(old), []).append(old.strip())
    out = []
    for e in entries:
        ln = d2_text(e)
        key = line_time(ln)
        cand = bucket.get(key) or []
        flag = ""
        if cand:
            # 1) เที่ยวเดิมไม่เปลี่ยน (เนื้อเท่ากัน — ต่างแค่ flag) → คง flag เดิมของบรรทัดนั้น
            #    จับคู่ "ตรงบรรทัด" ไม่ใช่ตามเวลาเฉยๆ (กัน 🟢 ของรถอีกคันเวลาเดียวกันลามมาที่บรรทัดนี้)
            hit = next((o for o in cand if _line_plain(o) == _line_plain(ln)), None)
            if hit is not None:
                cand.remove(hit)
                flag = _flag_of(hit)
            else:
                # 2) ช่องเวลาเดิมแต่เนื้อเปลี่ยน → คง flag เดิมถ้ามี ไม่งั้น 🟡 (変更)
                flag = _flag_of(cand.pop(0)) or "🟡"
        else:
            flag = "🟢"  # ช่องเวลาใหม่ = 新規
        out.append(f"{ln} {flag}" if flag else ln)
    return "\n".join(out)


def build_plan(form_rows, skipped=None):
    """diff D2-aware: เทียบ (เวลา+ชั่วโมง) เท่านั้น กัน 空/ホ/🔷 รบกวน.
    plan[month][day] = (target_text, reason, cur) — target_text = บรรทัด D2 รวมของใบนี้

    `skipped` = list ที่จะถูกเติม (month, day, foreign_lines) ของวันที่ถูกข้าม เพราะเซลล์มีบรรทัด
    ที่ระบบสร้างไม่ได้ — caller ต้องรายงานให้พี่เจเห็น (ห้ามเงียบ: วันนั้นจะค้างไม่ถูกอัปเดต)
    """
    taicho = read_taicho()
    plan = {}
    for d, entries in sorted(form_rows.items()):
        month = d.month
        if month not in taicho:
            continue
        current = taicho[month]["cells"].get(d.day)
        cur_str = str(current) if current is not None else None
        foreign = _foreign_lines(cur_str)
        if foreign:
            print(f"  ⚠️ ข้าม {month}月{d.day:02d}: เซลล์มีบรรทัดที่ระบบสร้างไม่ได้ {foreign!r} "
                  f"— ให้คนตรวจก่อน (ห้ามเขียนทับให้ข้อมูลหาย)", flush=True)
            if skipped is not None:
                skipped.append((month, d.day, foreign))
            continue
        target_text = plan_cell_text(cur_str, entries)  # flag 🟢/🟡 ต่อบรรทัด (แก้ 10 ก.ย. 69)
        # gate เทียบข้อความ (เดิมเทียบแค่ เวลา+ชั่วโมง → ทิศทาง 空↔ホ เปลี่ยนแล้วไม่ถูกเขียน)
        # norm_cell = ไม่นับช่องว่างท้ายบรรทัด (กันเขียน/LINE ปลอมเพราะช่องว่างล้วน) แต่ยังนับ flag
        if norm_cell(cur_str) != norm_cell(target_text):
            cur_t = Counter(k for k in (line_time(ln) for ln in (cur_str or "").split("\n")) if k)
            new_t = Counter(k for k in (line_time(ln) for ln in target_text.split("\n")) if k)
            dropped = sum((cur_t - new_t).values())
            if not entries:
                reason = "ลบ (งานยกเลิก/ไม่มีแล้ว)"
            elif cur_str is None:
                reason = "ลงใหม่"
            elif dropped:
                reason = "แก้ไข+ลบ"  # ลบบางเที่ยว + ยังมีเที่ยวอื่นในวันเดียวกัน
            else:
                reason = "แก้ไข"
            plan.setdefault(month, {})[d.day] = (target_text, reason, cur_str)
    return plan


def write_cell_rich(entry_row, day, text, runs):
    """เขียนเซลล์วัน (row 1-based, day 1-31) พร้อม rich text runs (สี D2)"""
    name, gid = find_main_tab()
    if not name:
        raise RuntimeError("ไม่พบ tab 台帳 หลัก")
    col = col_for_day(day)
    ci = col_index(col)
    req = {
        "updateCells": {
            "range": {"sheetId": gid, "startRowIndex": entry_row - 1, "startColumnIndex": ci,
                      "endRowIndex": entry_row, "endColumnIndex": ci + 1},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": text},
                                  "textFormatRuns": runs}]}],
            "fields": "userEnteredValue,textFormatRuns",
        }}
    batch_update([req])


def apply_plan(plan, dry_run=True):
    taicho = read_taicho()
    for month, days in sorted(plan.items()):
        entry_row = taicho[month]["row"]
        for day in sorted(days):
            target_text, reason, cur = days[day]
            col = col_for_day(day)
            rng = f"{col}{entry_row}"
            if dry_run:
                print(f"  [{reason}] {month}月{day:02d} {rng}: {cur!r} -> {target_text!r}", flush=True)
                continue
            # flag 🟢/🟡 ต่อบรรทัดถูกใส่ใน plan_cell_text แล้ว — ห้ามต่อท้ายเซลล์ (10 ก.ย. 69)
            text = target_text
            write_cell_rich(entry_row, day, text, color_runs(text))
            print(f"  [เขียน D2] {month}月{day:02d} {rng}: {cur!r} -> {text!r}", flush=True)


# ---------------- flags / rotate ----------------

def clear_stale_flags(state):
    today = date.today().isoformat()
    if state.get("last_flag_date") == today:
        return 0
    if "last_flag_date" not in state:
        state["last_flag_date"] = today
        print(f"flag bootstrap: last_flag_date={today}", flush=True)
        return 0
    t = read_taicho()
    n = 0
    for month, info in t.items():
        row = info["row"]
        for day, v in info["cells"].items():
            if "🟢" in v or "🟡" in v:
                clean = strip_flags(v)
                if clean != v:
                    write_cell_rich(row, day, clean, color_runs(clean))
                    n += 1
    state["last_flag_date"] = today
    print(f"cleared {n} stale flag(s)", flush=True)
    return n


def rotate_table_if_needed():
    if date.today().day != 1:
        return False
    rotated = False
    while True:
        name, gid = find_main_tab()
        if not name:
            break
        t = read_taicho()
        if not t:
            break
        months = sorted(t.keys())
        first, last = months[0], months[-1]
        if first == date.today().month:
            break
        rotated = True
        first_entry = t[first]["row"]
        first_header = first_entry - 3
        last_header = t[last]["row"] - 3
        new_month = (last % 12) + 1
        new_year = 2027 if new_month == 1 else 2026
        year_label = 2027 if new_month < last else 2026
        m0 = (first % 12) + 1
        m3 = new_month
        new_title = f"千栄1568 {m0}月-{m3}月({year_label})"
        second_header = (t[months[1]]["row"] - 3) if len(months) > 1 else first_header + MONTH_BLOCK
        first_block = second_header - first_header
        prev_header = (t[months[-2]]["row"] - 3) if len(months) > 1 else last_header - MONTH_BLOCK
        last_block = last_header - prev_header
        tmp_title = "千栄1568 tmp"
        resp = _api("POST", f"{SHEETS_API}/{SHEET_ID}:batchUpdate",
                    body={"requests": [{"duplicateSheet": {
                        "sourceSheetId": gid, "insertSheetIndex": 0,
                        "newSheetName": tmp_title}}]})
        new_gid = None
        for r in resp.get("replies", []):
            p = r.get("duplicateSheet", {}).get("properties", {})
            new_gid = p.get("sheetId")
        if new_gid is None:
            raise RuntimeError("duplicateSheet failed")
        batch_update([{"deleteDimension": {"range": {"sheetId": new_gid, "dimension": "ROWS",
                        "startIndex": first_header - 1, "endIndex": first_header - 1 + first_block}}}])
        tok = sheets_token()
        a_rows = _api("GET", f"{SHEETS_API}/{SHEET_ID}/values/A1:A80?majorDimension=ROWS").get("values", [])
        last_hdr_1based = None
        for i, row in enumerate(a_rows, start=1):
            a = row[0] if row else ""
            if re.search(r"\d+月", str(a)):
                last_hdr_1based = i
        if last_hdr_1based is None:
            raise RuntimeError("หา header ล่าสุดไม่เจอ")
        dest = last_hdr_1based - 1 + last_block
        src = dest - last_block
        batch_update([{"copyPaste": {"source": {"sheetId": new_gid, "startRowIndex": src,
                        "endRowIndex": dest, "startColumnIndex": 0, "endColumnIndex": 33},
                        "destination": {"sheetId": new_gid, "startRowIndex": dest, "endColumnIndex": 33},
                        "pasteType": "PASTE_FORMAT"}}])
        h = dest + 1
        days = list(range(1, 32))
        rng = f"A{h}:AF{h + 9}"
        quote_rng = urllib.parse.quote(rng)
        _api("PUT", f"{SHEETS_API}/{SHEET_ID}/values/{quote_rng}?valueInputOption=USER_ENTERED",
             body={"values": [[f"{new_year}年 {new_month}月"] + days, [None] * 33, [None] * 33,
                              ["千栄1568"] + [None] * 32, [None] * 33, [None] + days, [None] * 33,
                              ["変更は🟡"] + [None] * 32, ["新規は🟢"] + [None] * 32,
                              [LEGEND_ROWS[2]] + [None] * 32]})
        batch_update([{"updateSheetProperties": {"properties": {"sheetId": new_gid, "title": new_title},
                                                 "fields": "title"}}])
        reqs = [
            {"updateDimensionProperties": {"range": {"sheetId": new_gid, "dimension": "ROWS",
                        "startIndex": 0, "endIndex": 956},
                        "properties": {"hiddenByUser": False}, "fields": "hiddenByUser"}},
            {"updateDimensionProperties": {"range": {"sheetId": new_gid, "dimension": "ROWS",
                        "startIndex": h + 2, "endIndex": h + 3},
                        "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
            {"repeatCell": {"range": {"sheetId": new_gid, "startRowIndex": h + 10, "endRowIndex": h + 11,
                        "startColumnIndex": 0, "endColumnIndex": 33},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}},
                        "fields": "userEnteredFormat.backgroundColor"}},
            {"repeatCell": {"range": {"sheetId": new_gid, "startRowIndex": h + 13, "endRowIndex": h + 14,
                        "startColumnIndex": 0, "endColumnIndex": 33},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}},
                        "fields": "userEnteredFormat.backgroundColor"}},
            {"updateDimensionProperties": {"range": {"sheetId": new_gid, "dimension": "ROWS",
                        "startIndex": h + 15, "endIndex": 956},
                        "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        ]
        t_new = read_taicho()
        m_list = list(t_new.keys())
        bottom = m_list[-1]
        for m, info in t_new.items():
            hdr = info["row"] - 3
            r, g, b = HEADER_COLOR.get(m, (0.9, 0.9, 0.9))
            reqs.append({"repeatCell": {"range": {"sheetId": new_gid, "startRowIndex": hdr - 1,
                        "endRowIndex": hdr, "startColumnIndex": 0, "endColumnIndex": 33},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                        "fields": "userEnteredFormat.backgroundColor"}})
            # legend = ชุดเดียวที่บล็อกล่างสุด (พี่เจสั่ง 5 ก.ย. 69) — ล้างบล็อกอื่น
            if m != bottom:
                base = info["row"] + 3  # 0-based ของ legend row แรก (entry+4)
                for rr in range(base, base + 3):
                    reqs.append({"updateCells": {
                        "range": {"sheetId": new_gid, "startRowIndex": rr, "endRowIndex": rr + 1,
                                  "startColumnIndex": 0, "endColumnIndex": 1},
                        "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                        "fields": "userEnteredValue"}})
        batch_update(reqs)
        print(f"rotate: {new_title}", flush=True)
    return rotated


# ---------------- orchestrator ----------------

def _mt_key(s):
    """คีย์เรียงเวลาแบบ epoch (float) — **ห้ามเทียบ ISO string ตรง ๆ** (lessons #121: state เก็บ
    '2026-09-10T09:35:17.339Z' (UTC+millis) แต่บางที่ได้ '+07:00'/ไม่มี millis → string compare
    เรียงผิด → re-apply + LINE ซ้ำ). parse ไม่ได้ (ค่าว่าง/รูปแบบแปลก) = 0.0 = เก่าสุด (ไม่ trigger re-add)"""
    if not s:
        return 0.0
    try:
        return _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _select_new_forms(procd, pmt, forms, bootstrapped, now=None):
    """คัดใบที่ต้องประมวลผลจาก state + ใบใน Drive (pure logic — test ได้, 9 ก.ย. 69 v2)
    แก้ procd/pmt ในที่ คืน (new_forms, bootstrapped). state processed = ชื่อล้วน (legacy) หรือ
    'name|file_id|modifiedTime' (v2). กัน: ชื่อซ้ำ千栄ส่งซ้ำ · แก้เนื้อหาไฟล์เดิม · legacy ครอบชื่อ"""
    def _key(nm, fid, mt):
        return f"{nm}|{fid}|{mt}"

    fresh_cutoff = ((now or _dt.datetime.now(_dt.timezone.utc)) - _dt.timedelta(days=1)).isoformat()
    by_name = {}
    for _, fid, nm, mt in forms:
        by_name.setdefault(nm, []).append((fid, mt))
    # (a) legacy (ชื่อล้วน): ชื่อซ้ำ 2 ไฟล์ หรือไฟล์เดียวถูกแก้ (mtime ใหม่พอ) = ปลด legacy
    plain_set = {p for p in procd if "|" not in p}
    for nm, flist in list(by_name.items()):
        if nm not in plain_set:
            continue
        maxmt = max((mt for _, mt in flist), key=_mt_key)
        if len(flist) > 1:
            if _mt_key(maxmt) < _mt_key(fresh_cutoff):
                continue  # ชื่อซ้ำของไฟล์เก่า = ไม่แตะ (กัน rebuild ใบเก่าทับข้อมูลใหม่)
            procd.remove(nm)
            print(f"dup-name {nm} ({len(flist)} files) -> retire legacy, newest wins", flush=True)
            continue
        fid, mt = flist[0]
        old = pmt.get(nm)
        if old is None:
            pmt[nm] = mt or ""
            print(f"proc_mt init {nm} = {mt}", flush=True)
        elif mt and _mt_key(mt) > _mt_key(old) and _mt_key(mt) >= _mt_key(fresh_cutoff):
            procd.remove(nm)
            print(f"re-add {nm} (updated {old} -> {mt})", flush=True)
    # (d) bootstrap ก่อนคัด (เฉพาะ state ใหม่จริง — flag กัน re-add โล่งแล้วเข้า bootstrap ผิดรอบ)
    if not bootstrapped:
        bootstrapped = True
        if not procd and forms:
            newest = forms[-1][2]
            for _, fid, nm, mt in forms:
                if nm != newest:
                    procd.append(_key(nm, fid, mt))
                    pmt[nm] = mt
            print(f"bootstrap: marked {len(procd)} old forms", flush=True)
    # (b) ใหม่ = key ยังไม่เคยบันทึก และชื่อไม่ถูก legacy ครอบ
    plain_set = {p for p in procd if "|" not in p}
    keyed_set = {p for p in procd if "|" in p}
    cands = []
    for mmdd, fid, nm, mt in forms:
        if nm in plain_set:
            continue
        if _key(nm, fid, mt) in keyed_set:
            continue
        cands.append((mmdd, fid, nm, mt))
    # (c) ชื่อซ้ำ/หลายเวอร์ชัน: เอาเฉพาะ mtime สูงสุด (กันของเก่าทับของใหม่)
    best = {}
    for mmdd, fid, nm, mt in cands:
        if nm not in best or _mt_key(mt) > _mt_key(best[nm][3]):
            best[nm] = (mmdd, fid, nm, mt)
    new_forms = [best[nm] for nm in sorted(best, key=lambda n: best[n][0])]
    return new_forms, bootstrapped


def run_flow():
    token = sheets_token()
    try:
        state = load_state(token)
    except StateReadError as e:
        # อ่าน state ไม่ได้ = หยุดทั้งรอบ (ไม่ apply / ไม่ LINE / ไม่เขียน state ทับ) — 10 ก.ย. 69
        print(f"ABORT: {e} — ไม่ประมวลผลรอบนี้ (กัน bootstrap ผิด = apply/LINE ซ้ำ)", flush=True)
        return "state read failed"
    try:
        rotate_table_if_needed()
        clear_stale_flags(state)
    except Exception as e:
        print(f"rotate/clear failed: {e}", flush=True)
    forms = list_forms(token)
    procd = state.setdefault("processed", [])
    if not isinstance(state.get("proc_mt"), dict):
        state["proc_mt"] = {}
    pmt = state["proc_mt"]
    new_forms, state["bootstrapped"] = _select_new_forms(
        procd, pmt, forms, state.get("bootstrapped", False))

    def _mark(nm, fid, mt):
        k = f"{nm}|{fid}|{mt}"
        if k not in procd:
            procd.append(k)
        pmt[nm] = mt or ""

    if not new_forms:
        print("No new form. done.", flush=True)
        save_state(state, token)
        return "no new form"
    for mmdd, fid, nm, mt in new_forms:
        try:
            data = _get_media(f"{DRIVE_API}/files/{fid}?alt=media", token)
            skipped = []
            plan = build_plan(parse_form_bytes(data), skipped=skipped)
            if not plan:
                msg = f"✅ 台帳を確認しました（{mmdd}）: 変更なし"
                if skipped:
                    # ห้ามเงียบ: วันที่มีบรรทัดที่ระบบสร้างไม่ได้ = ไม่ถูกอัปเดต ต้องบอกพี่เจ
                    msg = (f"⚠️ 台帳を確認しました（{mmdd}）: 変更なし（未更新 {len(skipped)} 日 — 手入力行あり）\n"
                           + "\n".join(f"  - {m}月{d}日: {f!r}" for m, d, f in skipped[:5])
                           + "\n要確認（システムは上書きしません）")
                    print(f"SKIPPED days: {skipped!r}", flush=True)
                print("no change:", nm, flush=True)
                send_line(f"{msg}\n{SHORT_TAICHO_URL}")
                send_line("宜しくお願い致します。")
                _mark(nm, fid, mt)
                save_state(state, token)
                continue
            apply_plan(plan, dry_run=False)
            JA_REASON = {"ลงใหม่": "新規🟢", "แก้ไข": "変更🟡", "แก้ไข+ลบ": "変更🟡＋削除",
                         "ลบ (งานยกเลิก/ไม่มีแล้ว)": "削除"}
            lines = []
            total = 0
            for month in sorted(plan):
                for day in sorted(plan[month]):
                    target, reason, cur = plan[month][day]
                    # target = ข้อความที่เขียนลง cell จริง (flag 🟢/🟡 ติดต่อบรรทัดแล้ว) — ห้ามเติม flag ซ้ำ
                    disp = target
                    lines.append(f"  - {month}月{day}日 [{JA_REASON.get(reason, reason)}]: {disp!r}")
                    total += 1
            for m, d, f in skipped:  # วันที่มีบรรทัดที่ระบบสร้างไม่ได้ = ข้ามจริง ต้องบอกให้พี่เจตรวจ
                lines.append(f"  - {m}月{d}日 [⚠️未更新]: 手入力行あり {f!r} — 要確認")
            msg = (f"📋 台帳を自動更新しました（{mmdd}、{total}箇所）:\n" + "\n".join(lines))
            send_line(msg)
            send_line(f"📄 台帳を開く（{mmdd}）\n{SHORT_TAICHO_URL}")
            # PDF สร้างที่เครื่องเท่านั้น (HTML+Edge — พี่เจ reject reportlab PNG 7 ก.ย. 69)
            # คำสั่ง: python tools/taicho_pdf.py pdf --date {mmdd} แล้ว python tools/taicho_qa.py <ไฟล์>
            print(f"PDF note: สร้าง PDF {mmdd} ที่เครื่อง (taicho_pdf.py HTML+Edge + taicho_qa.py)", flush=True)
            send_line("宜しくお願い致します。")
            _mark(nm, fid, mt)
            save_state(state, token)
        except Exception as e:
            print(f"failed {nm}: {e}", flush=True)
            try:
                send_line(f"⚠️ 台帳更新に失敗（{mmdd}）: {e}")
            except Exception:
                pass
    save_state(state, token)
    return f"processed {len(new_forms)} form(s)"


@https_fn.on_request(region=SupportedRegion.ASIA_SOUTHEAST1)
def taicho_monitor(req: https_fn.Request) -> https_fn.Response:
    """HTTP entry. 7 ก.ย. 69: PDF hook ถอดออก (reportlab reject — PDF = ที่เครื่อง HTML+Edge)
    body/query {pdf: 1} = ตอบวิธีสร้าง PDF ที่เครื่อง (taicho_pdf.py + taicho_qa.py)"""
    try:
        body = {}
        if req.method == "POST":
            raw = req.get_data(as_text=True)
            if raw and raw.lstrip()[:1] in ("{", "["):
                body = json.loads(raw)
        body.update({k: v for k, v in (req.args.items() if req.args else [])})
        if body.get("pdf") == "1":
            return https_fn.Response(
                "PDF สร้างที่เครื่องเท่านั้น (HTML+Edge — reportlab reject 7 ก.ย.): "
                "python tools/taicho_pdf.py pdf --date <MMDD> แล้ว python tools/taicho_qa.py <ไฟล์.pdf>",
                status=200)
        msg = run_flow()
        return https_fn.Response(f"OK {msg}", status=200)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        return https_fn.Response(f"ERROR: {e}", status=500)
