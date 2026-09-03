#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""king-bus-taicho AUTO — ตรวจใบขอรถใหม่ vs 台帳 Google Sheets + apply อัตโนมัติ + LINE.

รันซ้ำได้ทุก N นาที (Task Scheduler): สแกนโฟลเดอร์เดือนที่เกี่ยวข้อง (26.8-26.12, 27.01-27.03)
หาใบขอรถ MMDD_千栄交通㈱_貸切バス手配依頼書.xlsx ที่ยังไม่เคยตรวจ
→ diff กับ台帳 (reuse taicho_gsheets.py) → ถ้ามีการเปลี่ยนแปลง apply ทันที
→ ส่ง LINE สรุป (มี/ไม่มี) → บันทึกสถานะ (ตรวจ 1 ครั้งต่อไฟล์)

รอบแรก (state ว่าง): ทำเครื่องหมายไฟล์เก่าทั้งหมดว่า processed ยกเว้นไฟล์ใหม่สุด
(จะตรวจ LINE เฉพาะไฟล์ใหม่สุด เพื่อพิสูจน์ว่าสคริปต์ทำงาน — ไม่ LINE ถล่มประวัติเก่า)

ความปลอดภัย: LINE channel secret อ่านจาก config นอก repo (ห้าม commit ขึ้น GitHub)
"""
import glob
import json
import logging
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import taicho_gsheets as tg  # reuse: read_request_form / build_plan / apply_plan

BASE_PARENT = r"H:\My Drive\チェー（個人）\King BUS\台帳入力（配車時間入力）"
# เฉพาะปี/เดือนที่มี tab 千栄1568 ในใบขอรถ (SOP: 26.8-26.12, 27.01-27.03)
YEAR_MONTHS = {2026: [8, 9, 10, 11, 12], 2027: [1, 2, 3]}
LINE_CONFIG = r"C:\Users\chett\.config\opencode\gmail-monitor\line_config.json"
# Web App 台帳 (Apps Script — อ่านสดจาก Sheets, emoji ติดทุกเบราว์เซอร์) — 1 ก.ย. 69
# v9 (NATIVE sandbox → print ใช้ได้มือถือ + rotate hint หมุนจอ) 1 ก.ย. 69
TAICHO_WEBAPP_URL = ("https://script.google.com/macros/s/"
                     "AKfycbym-XXro-jSHP1yO2wgmV4RfNVSPyOFcJdiutRjSfTbEfwkODJxcDySGQ_oZN1rYQbc2A/exec")
# ส่งเป็น plain text ในข้อความ (quickReply หายเมื่อข้ามวัน — lessons #62): สั้น ดูง่าย, ปลายทาง = เดียวกับข้างบน
# 3 ก.ย. 69: tinyurl ตายภายในวันเดียว (ตัวจริงยัง 200) → เปลี่ยนเป็น Vercel redirect ฟรี https://taicho-link.vercel.app
# (Hobby ไม่ต้องบัตร; vercel.json redirects 307 → exec URL เดิม; แก้ปลายทางที่ D:\GitHub\taicho-link\vercel.json แล้ว vercel deploy --prod)
SHORT_TAICHO_URL = "https://taicho-link.vercel.app"
STATE_FILE = os.path.join(TOOLS_DIR, "taicho_auto_state.json")
LOCK_FILE = os.path.join(TOOLS_DIR, ".taicho_auto.lock")
FORM_RE = re.compile(r"(\d{4})_千栄交通㈱_貸切バス手配依頼書(?:\(\d+\))?\.xlsx$")

MONTH_BLOCK = 16  # แถวต่อ 1 เดือนในตาราง台帳 (header 1 + ว่าง 2 + entry 1 + ว่าง 1 + sub 1 + ว่าง 1 + legend 3 + ว่าง 6)

# สีหัวเดือน: 30 วัน = โทนเย็น (ฟ้า/เขียว), 31 วัน = โทนอุ่น (เหลือง/ส้ม/ชมพู), ก.พ. = เทา
# (พี่เจสั่ง 31 ส.ค. 69: สีไม่มีนัยสำคัญ แค่ให้เดือนต่างกัน + แยก 30/31 วัน ดูง่าย)
HEADER_COLOR = {
    1: (1, 0.9, 0.4),      # เหลือง (31)
    2: (0.75, 0.75, 0.75), # เทา (28/29)
    3: (1, 0.65, 0.3),     # ส้ม (31)
    4: (0.6, 0.8, 1),      # ฟ้า (30)
    5: (1, 0.75, 0.8),     # ชมพู (31)
    6: (0.7, 0.9, 0.7),    # เขียว (30)
    7: (1, 0.9, 0.4),      # เหลือง (31)
    8: (1, 0.65, 0.3),     # ส้ม (31)
    9: (0.6, 0.8, 1),      # ฟ้า (30)
    10: (1, 0.75, 0.8),    # ชมพู (31)
    11: (0.7, 0.9, 0.7),   # เขียว (30)
    12: (1, 0.65, 0.3),    # ส้ม (31)
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(TOOLS_DIR, "taicho_auto.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout) if sys.stdout else logging.NullHandler(),
    ],
)
log = logging.getLogger("taicho_auto")


class FileLock:
    def __enter__(self):
        try:
            self.fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, str(os.getpid()).encode())
        except FileExistsError:
            log.info("Another instance is running, skipping.")
            sys.exit(0)
        return self

    def __exit__(self, *a):
        try:
            os.close(self.fd)
        except Exception:
            pass
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"processed": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_line_config():
    if os.path.exists(LINE_CONFIG):
        with open(LINE_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_line_token(cfg):
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cfg["channel_id"],
        "client_secret": cfg["channel_secret"],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/oauth/accessToken", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


def send_line(text):
    cfg = load_line_config()
    if not cfg.get("channel_id") or not cfg.get("channel_secret"):
        log.error("LINE config missing: %s", LINE_CONFIG)
        return False
    try:
        token = get_line_token(cfg)
        for uid in cfg.get("user_ids", []):
            body = json.dumps({
                "to": uid,
                "messages": [{"type": "text", "text": text}],
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.line.me/v2/bot/message/push", data=body,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
        log.info("LINE sent: %s", text)
        return True
    except Exception as e:
        log.error("LINE failed: %s", e)
        return False


def send_line_pdf(text, download_url):
    """ส่งข้อความ + quickReply ลิงก์เปิด台帳 Web App (LINE Messaging API ไม่รองรับ push ไฟล์ตรง).
    เดิม: ลิงก์ดาวน์โหลด PDF จาก Drive — เปลี่ยนเป็น Web App (emoji ติดทุกเบราว์เซอร์) 1 ก.ย. 69."""
    cfg = load_line_config()
    if not cfg.get("channel_id") or not cfg.get("channel_secret"):
        log.error("LINE config missing: %s", LINE_CONFIG)
        return False
    try:
        token = get_line_token(cfg)
        for uid in cfg.get("user_ids", []):
            body = json.dumps({
                "to": uid,
                "messages": [{
                    "type": "text",
                    "text": text,
                    "quickReply": {"items": [{
                        "type": "action",
                        "action": {"type": "uri",
                                   "label": "เปิด台帳 (Print)",
                                   "uri": download_url}}]},
                }],
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.line.me/v2/bot/message/push", data=body,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
        log.info("LINE pdf sent: %s", text)
        return True
    except Exception as e:
        log.error("LINE pdf failed: %s", e)
        return False


def find_all_forms():
    """คืน [(mmdd, path)] เรียงตามชื่อ จากเฉพาะปี/เดือนที่เกี่ยวข้อง."""
    found = []
    for year, months in YEAR_MONTHS.items():
        for mm in months:
            folder = os.path.join(BASE_PARENT, str(year), f"{mm}月")
            for path in sorted(glob.glob(os.path.join(folder, "*.xlsx"))):
                m = FORM_RE.match(os.path.basename(path))
                if m:
                    found.append((m.group(1), path))
    return sorted(found, key=lambda t: t[0])


def bootstrap_state(state, forms):
    """รอบแรก: mark ไฟล์เก่าทั้งหมด ยกเว้นไฟล์ใหม่สุด (ให้ตรวจ LINE เฉพาะไฟล์ล่าสุด)."""
    if not forms or state["processed"]:
        return
    newest = forms[-1][1]  # เรียง mmdd แล้ว ตัวสุดท้าย = ใหม่สุด
    for mmdd, path in forms:
        base = os.path.basename(path)
        if path == newest:
            continue
        state["processed"].append(base)
    log.info("bootstrap: marked %d old forms processed (จะตรวจเฉพาะ %s)",
             len(state["processed"]), os.path.basename(newest))


# ---------------------------------------------------------------- ตาราง 4 เดือนเลื่อน + flag ----------

def _sheets_batch(requests):
    """batchUpdate กับ tab 台帳 หลัก (dynamic)"""
    name, gid = tg.find_main_tab()
    if not name:
        raise RuntimeError("ไม่พบ tab 台帳 หลัก")
    body = json.dumps({"requests": requests}).encode()
    req = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}:batchUpdate",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {tg.get_token()}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60).read()
    return gid


def _sheets_batch_by_gid(gid, requests):
    """batchUpdate กับ tab ตาม gid ตรง (ใช้กับ tab ใหม่ชั่วคราวตอน rotate)"""
    body = json.dumps({"requests": requests}).encode()
    req = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}:batchUpdate",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {tg.get_token()}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60).read()


def _tab_update_tab(gid, rng, values):
    """เขียนค่าใน tab ตาม gid ตรง (ไม่มีชื่อ tab — ใช้ A1 ล้วน)"""
    tok = tg.get_token()
    quoted = urllib.parse.quote(f"{rng}")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}/values/{quoted}?valueInputOption=USER_ENTERED"
    body = json.dumps({"values": values}).encode()
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def _tab_values(tab, rng):
    tok = tg.get_token()
    quoted = urllib.parse.quote("'{0}'!{1}".format(tab, rng))
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}/values/{quoted}?majorDimension=ROWS"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(req, timeout=30)).get("values", [])


def _tab_update(tab, rng, values):
    tok = tg.get_token()
    quoted = urllib.parse.quote("'{0}'!{1}".format(tab, rng))
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}/values/{quoted}?valueInputOption=USER_ENTERED"
    body = json.dumps({"values": values}).encode()
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def clear_stale_flags(state):
    """ข้อ 1-2: flag 🟢/🟡 = เฉพาะวันที่อัปเดต — วันใหม่ ครั้งแรกของวัน ลบ flag ค้างทั้งหมดในตาราง
    (flag ที่ apply ใส่หลัง clear = ของวันนี้). ครั้งแรกที่ระบบ track (ไม่มี last_flag_date) = ไม่ clear
    (flag ที่มีอยู่ = สถานะจริง เริ่ม clear ตั้งแต่วันถัดไป)"""
    today = date.today().isoformat()
    if state.get("last_flag_date") == today:
        return 0
    if "last_flag_date" not in state:
        state["last_flag_date"] = today
        log.info("flag bootstrap: ตั้ง last_flag_date=%s (ไม่ clear วันแรก)", today)
        return 0
    t = tg.read_taicho()
    n = 0
    for month, info in t.items():
        row = info["row"]
        for day, v in info["cells"].items():
            if "🟢" in v or "🟡" in v:
                clean = tg.strip_flags(v)
                if clean != v:
                    tg.sheets_update(f"{tg.col_for_day(day)}{row}", [[clean]])
                    n += 1
    state["last_flag_date"] = today
    log.info("cleared %d stale flag(s) (วันใหม่)", n)
    return n


def rotate_table_if_needed():
    """ข้อ 3: ตาราง 4 เดือนเลื่อน — วันที่ 1 ของเดือน และเดือนแรกของตาราง != เดือนปัจจุบัน
    → **สร้าง tab ใหม่** `千栄1568 <M0>月-<M3>月(<ปี>)` (copy โครงสร้าง/ข้อมูล/format จาก tab ล่าสุด,
    ลบเดือนแรก, เพิ่มเดือนใหม่ต่อท้าย) — **tab เก่าเก็บไว้เป็นประวัติ ไม่แตะ** (พี่เจสั่ง 31 ส.ค. 69)
    วนจนกว่าเดือนแรกของ tab ล่าสุด == เดือนปัจจุบัน (ครอบค้างหลายเดือน)"""
    today = date.fromisoformat(os.environ.get("TEST_DATE", date.today().isoformat()))
    if today.day != 1:
        return False
    rotated = False
    while True:
        name, gid = tg.find_main_tab()
        if not name:
            break
        t = tg.read_taicho()
        if not t:
            break
        months = sorted(t.keys())
        first = months[0]
        last = months[-1]
        if first == today.month:
            break
        rotated = True
        first_entry = t[first]["row"]
        first_header = first_entry - 3
        last_header = t[last]["row"] - 3
        new_month = (last % 12) + 1
        new_year = 2027 if new_month == 1 else 2026
        year_label = 2027 if new_month < last else 2026  # ปีของเดือนสุดท้ายในชื่อ tab (ข้ามปีเมื่อ wrap)
        m0 = (first % 12) + 1
        m3 = new_month
        new_title = f"千栄1568 {m0}月-{m3}月({year_label})"

        # block จริงของเดือนแรก/สุดท้าย
        second_header = (t[months[1]]["row"] - 3) if len(months) > 1 else first_header + MONTH_BLOCK
        first_block = second_header - first_header
        prev_header = (t[months[-2]]["row"] - 3) if len(months) > 1 else last_header - MONTH_BLOCK
        last_block = last_header - prev_header

        # 1) duplicate tab ล่าสุด -> tab ใหม่ (ชื่อชั่วคราวกัน regex จับก่อน rename)
        tmp_title = "千栄1568 tmp"
        req = urllib.request.Request(
            f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}:batchUpdate",
            data=json.dumps({"requests": [{"duplicateSheet": {
                "sourceSheetId": gid, "insertSheetIndex": 0, "newSheetName": tmp_title}}]}).encode(),
            method="POST",
            headers={"Authorization": f"Bearer {tg.get_token()}", "Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
        new_gid = None
        for r in resp.get("replies", []):
            p = r.get("duplicateSheet", {}).get("properties", {})
            new_gid = p.get("sheetId")
        if new_gid is None:
            raise RuntimeError("duplicateSheet ล้มเหลว")

        # 2) ลบ block เดือนแรกใน tab ใหม่
        _sheets_batch_by_gid(new_gid, [{"deleteDimension": {
            "range": {"sheetId": new_gid, "dimension": "ROWS",
                      "startIndex": first_header - 1, "endIndex": first_header - 1 + first_block}}}])

        # 3) หา header จริงของเดือนสุดท้ายใน tab ใหม่ (หลังลบ — อ่านค่า ไม่คำนวณ กัน offset)
        #    values API ไม่มี sheet name = ใช้ sheet แรก (tmp อยู่ index 0)
        tok_now = tg.get_token()
        a_url = f"https://sheets.googleapis.com/v4/spreadsheets/{tg.SHEET_ID}/values/A1:A80?majorDimension=ROWS"
        a_req = urllib.request.Request(a_url, headers={"Authorization": f"Bearer {tok_now}"})
        a_rows = json.loads(urllib.request.urlopen(a_req, timeout=30).read().decode()).get("values", [])
        last_hdr_1based = None
        for i, row in enumerate(a_rows, start=1):
            a = row[0] if row else ""
            if re.search(r"\d+月", str(a)):
                last_hdr_1based = i
        if last_hdr_1based is None:
            raise RuntimeError("หา header เดือนสุดท้ายใน tab ใหม่ไม่เจอ")
        dest = last_hdr_1based - 1 + last_block          # 0-based: ท้าย block สุดท้าย (hdr 0-based + ขนาด block)
        src = dest - last_block                          # 0-based: เริ่ม block สุดท้าย (ก่อน block ใหม่)
        _sheets_batch_by_gid(new_gid, [{"copyPaste": {
            "source": {"sheetId": new_gid, "startRowIndex": src, "endRowIndex": dest,
                       "startColumnIndex": 0, "endColumnIndex": 33},
            "destination": {"sheetId": new_gid, "startRowIndex": dest, "endColumnIndex": 33},
            "pasteType": "PASTE_FORMAT"}}])

        # 4) เขียนค่าเดือนใหม่ (hdr = dest+1, entry +3, sub +5, legend +7..9)
        h = dest + 1
        days = list(range(1, 32))
        _tab_update_tab(new_gid, f"A{h}:AF{h + 9}", [
            [f"{new_year}年 {new_month}月"] + days,
            [None] * 33, [None] * 33,
            ["千栄1568"] + [None] * 32,
            [None] * 33,
            [None] + days,
            [None] * 33,
            ["変更は🟡"] + [None] * 32,
            ["新規は🟢"] + [None] * 32,
            ["経由地🔷"] + [None] * 32,
        ])

        # 5) rename tab ใหม่ (ก่อน format — จะได้อ่าน header จริงผ่าน find_main_tab)
        _sheets_batch_by_gid(new_gid, [{"updateSheetProperties": {
            "properties": {"sheetId": new_gid, "title": new_title}, "fields": "title"}}])

        # 6) format เดือนใหม่: สี header (30/31 วัน), entry height 300, แถบเทา, ซ่อนแถวหลัง block
        #    duplicate copy hidden เก่า (r71+ ของ tab เดิม) + ลบ block บน = hidden เลื่อนขึ้น -> unhide ทั้ง tab ก่อน
        t_new = tg.read_taicho()  # find_main_tab เลือก tab ใหม่ (M0 สูงสุด)
        reqs = [
            {"updateDimensionProperties": {
                "range": {"sheetId": new_gid, "dimension": "ROWS", "startIndex": 0, "endIndex": 956},
                "properties": {"hiddenByUser": False}, "fields": "hiddenByUser"}},
            {"updateDimensionProperties": {
                "range": {"sheetId": new_gid, "dimension": "ROWS",
                          "startIndex": h + 2, "endIndex": h + 3},
                "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
            {"repeatCell": {
                "range": {"sheetId": new_gid, "startRowIndex": h + 10, "endRowIndex": h + 11,
                          "startColumnIndex": 0, "endColumnIndex": 33},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}},
                "fields": "userEnteredFormat.backgroundColor"}},
            {"repeatCell": {
                "range": {"sheetId": new_gid, "startRowIndex": h + 13, "endRowIndex": h + 14,
                          "startColumnIndex": 0, "endColumnIndex": 33},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}},
                "fields": "userEnteredFormat.backgroundColor"}},
            {"updateDimensionProperties": {
                "range": {"sheetId": new_gid, "dimension": "ROWS",
                          "startIndex": h + 15, "endIndex": 956},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        ]
        # สี header ทุกเดือนใน tab ใหม่ (ตาม 30/31 วัน)
        for m, info in t_new.items():
            hdr = info["row"] - 3
            r, g, b = HEADER_COLOR.get(m, (0.9, 0.9, 0.9))
            reqs.append({"repeatCell": {
                "range": {"sheetId": new_gid, "startRowIndex": hdr - 1, "endRowIndex": hdr,
                          "startColumnIndex": 0, "endColumnIndex": 33},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                "fields": "userEnteredFormat.backgroundColor"}})
        _sheets_batch_by_gid(new_gid, reqs)
        log.info("rotate: สร้าง tab ใหม่ %s (ลบ %d月, เพิ่ม %d年%d月)", new_title, first, new_year, new_month)
    return rotated


def run(dry_run=False):
    state = load_state()
    if not dry_run:
        try:
            rotate_table_if_needed()
            clear_stale_flags(state)
            save_state(state)
        except Exception as e:
            log.error("rotate/clear flags failed: %s", e)
    forms = find_all_forms()
    bootstrap_state(state, forms)
    new_forms = [(mmdd, path) for mmdd, path in forms
                 if os.path.basename(path) not in state["processed"]]
    if not new_forms:
        log.info("No new form. done.")
        return
    for mmdd, path in new_forms:
        try:
            plan = tg.build_plan(tg.read_request_form(path))
            if not plan:
                msg = f"✅ 台帳を確認しました（{mmdd}）: 変更なし"
                log.info("no change for %s", path)
                if not dry_run:
                    # ส่งลิงก์台帳ด้วย (lessons #62: quickReply หายข้ามวัน — ต้องมี plain text URL + ปุ่มเปิด台帳)
                    send_line_pdf(f"{msg}\n{SHORT_TAICHO_URL}", TAICHO_WEBAPP_URL)
                    state["processed"].append(os.path.basename(path))
                else:
                    print(msg)
                continue
            if dry_run:
                print(f"--- {mmdd} (dry-run) ---")
                tg.apply_plan(plan, dry_run=True)
                continue
            tg.apply_plan(plan, dry_run=False)
            # label ไทย -> ญี่ปุ่น+emoji (ตรง legend 台帳: 変更🟡/新規🟢/削除) — พี่เจสั่ง 2 ก.ย. 69
            JA_REASON = {"ลงใหม่": "新規🟢", "แก้ไข": "変更🟡",
                         "ลบ (งานยกเลิก/ไม่มีแล้ว)": "削除"}
            lines = []
            total = 0
            for month in sorted(plan):
                for day in sorted(plan[month]):
                    target, reason, cur = plan[month][day]
                    # ค่าใน cell จริง = target + 🟢 (apply_plan เติม flag ให้งานวันนี้) — แสดงให้ตรง
                    disp = (target + "🟢") if target else target
                    lines.append(f"  - {month}月{day}日 [{JA_REASON.get(reason, reason)}]: {disp!r}")
                    total += 1
            msg = (f"📋 台帳を自動更新しました（{mmdd}、{total}箇所）:\n"
                   + "\n".join(lines))
            send_line(msg)
            # PDF → เก็บไฟล์ (fallback) + LINE ส่งลิงก์ Web App (emoji ติดทุกเครื่อง — 1 ก.ย. 69)
            try:
                mm = int(mmdd[0:2])  # 2 ตัวแรก = เดือน (เช่น 0831 → 08); เดิม [2:4] เอาวันมาเป็นเดือน ผิด (31月)
                pdf_dir = os.path.join(BASE_PARENT, "2026" if mm >= 8 else "2027", f"{mm}月")
                pdf_name = tg.pdf_filename(mm, mmdd)  # ชื่อตามเดือนไส้ใน (9月-12月, 10月-01月...) — แก้ 1 ก.ย. 69
                tg.export_pdf(pdf_name, pdf_dir)
                send_line_pdf(f"📄 台帳を開く（{mmdd}）\n{SHORT_TAICHO_URL}", TAICHO_WEBAPP_URL)
            except Exception as e:
                log.error("PDF/LINE step failed for %s: %s", mmdd, e)
            state["processed"].append(os.path.basename(path))
        except Exception as e:
            log.error("failed processing %s: %s", path, e)
            send_line(f"⚠️ 台帳更新に失敗（{mmdd}）: {e}")
            # ไม่ mark processed — รอบหน้าจะลองใหม่
    save_state(state)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    with FileLock():
        run(dry_run=dry)
