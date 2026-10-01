#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_taicho_rotate_e2e.py — ทดสอบ rotate รายเดือน "ของจริง" บน **สำเนา** ของชีต master

ทำไมต้องมี: `tools/test_taicho_rotate.py` พิสูจน์แค่ pure logic — "เส้นทางเขียนชีตจริง"
(duplicateSheet → ลบ block เดือนแรก → copyPaste format → เขียนหัวเดือน → rename → จัด format)
ไม่มีอะไรพิสูจน์ได้เลยถ้าไม่ยิง API จริง · สคริปต์นี้คัดลอกไฟล์ master ทั้งไฟล์ แล้วรัน rotate จริง
บนสำเนา (ไฟล์จริงไม่ถูกแตะ) แล้วลบสำเนาทิ้ง

ทดสอบ 2 ฝาแฝด (โค้ดเดียวกัน คนละสำเนา):
  A) `tools/taicho_auto.py` (ตัวรัน local) @ 1 พ.ย. 69
  B) `cloud-functions/taicho-monitor/main.py` (ตัวที่รันจริงบน cloud) @ 1 ธ.ค. 69 + ปลูกแท็บ tmp ค้าง

รัน: python tools/test_taicho_rotate_e2e.py        (~1 นาที · ต้องมีเน็ต + creds Sheets)
หมายเหตุ: อ่าน creds จากไฟล์ local (ไม่พิมพ์ค่า) · ใช้ Drive scope เดียวกันใน creds เดียวกัน
"""
import datetime
import importlib.util
import json
import os
import sys
import types
import urllib.parse
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import taicho_gsheets as tg  # noqa: E402

SRC = "1H2WE2D8ZXrAI4jdOUm2N6DYGCWVD1SrYy9BqAfRFdC0"  # master จริง (ต้นทางที่คัดลอก)
COPY_NAME = "TEST-COPY 台帳 rotate e2e (ลบอัตโนมัติ)"
FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} | {name}")
    if not ok:
        print(f"        got ={got!r}\n        want={want!r}")
        FAILED.append(name)


def api(method, url, tok, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
    return json.loads(raw) if raw.strip() else {}


def read_tab(sheet_id, name, rng, tok):
    q = urllib.parse.quote(f"'{name}'!{rng}")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{q}?majorDimension=ROWS"
    return api("GET", url, tok).get("values", [])


def load_cloud():
    """โหลดโมดูล cloud ด้วย stub firebase_functions (ไม่ต้องมี dependency ของ cloud)"""
    if "firebase_functions" not in sys.modules:
        class _Any:
            def __getattr__(self, k):
                return k

        ff = types.ModuleType("firebase_functions")
        ff.https_fn = types.SimpleNamespace(on_request=lambda **kw: (lambda f: f),
                                            Request=object, Response=object)
        opts = types.ModuleType("firebase_functions.options")
        opts.SupportedRegion = _Any()
        ff.options = opts
        sys.modules["firebase_functions"] = ff
        sys.modules["firebase_functions.options"] = opts
    spec = importlib.util.spec_from_file_location(
        "cloud_main_e2e", REPO / "cloud-functions" / "taicho-monitor" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_date(today):
    """แทนคลาส date ของโมดูล cloud — ให้ date.today() คืนวันทดสอบ (cloud ไม่มี TEST_DATE)"""
    class _D(datetime.date):
        @classmethod
        def today(cls):
            return cls(today.year, today.month, today.day)
    return _D


def fresh_copy(tok):
    d = api("POST", f"https://www.googleapis.com/drive/v3/files/{SRC}/copy?fields=id", tok,
            {"name": COPY_NAME})
    return d["id"]


def drop_copy(tok, fid):
    api("DELETE", f"https://www.googleapis.com/drive/v3/files/{fid}", tok)


def phase_a_local(tok):
    """A) rotate ด้วย tools/taicho_auto.py บนสำเนา — 1 พ.ย. 69"""
    print("--- A) taicho_auto.py (local) @ 1 พ.ย. 69 ---")
    copy_id = fresh_copy(tok)
    print(f"    copy id = {copy_id}")
    try:
        tg.SHEET_ID = copy_id
        assert tg.SHEET_ID != SRC, "กันพลาด: ต้องไม่ใช่ไฟล์จริง"
        import taicho_auto as ta
        tabs0 = tg.list_tabs()
        main0 = tg.find_main_tab()[0]
        check("A: แท็บหลักตั้งต้น", main0, "千栄1568 10月-1月(2027)")
        check("A: ไม่มี tmp ตั้งต้น", tg.TMP_TAB_TITLE in tabs0, False)
        cells0 = {m: dict(tg.read_taicho()[m]["cells"]) for m in (10, 11, 12, 1)}

        os.environ["TEST_DATE"] = "2026-11-01"
        ta.rotate_table_if_needed()
        tabs1 = tg.list_tabs()
        check("A: แท็บใหม่ 11月-2月(2027)", tg.find_main_tab()[0], "千栄1568 11月-2月(2027)")
        check("A: แท็บเก่าเก็บเป็นประวัติ", "千栄1568 10月-1月(2027)" in tabs1, True)
        check("A: ไม่มี tmp ค้าง", tg.TMP_TAB_TITLE in tabs1, False)
        check("A: จำนวนแท็บ +1", len(tabs1), len(tabs0) + 1)
        t1 = tg.read_taicho()
        check("A: ลำดับเดือน", tg.window_months(t1), [11, 12, 1, 2])
        check("A: ปีของแต่ละเดือน", [t1[m]["year"] for m in (11, 12, 1, 2)], [2026, 2026, 2027, 2027])
        heads = [read_tab(copy_id, "千栄1568 11月-2月(2027)", f"A{r}:A{r}", tok)[0][0]
                 for r in (9, 25, 41, 57)]
        check("A: หัวเดือนในชีตจริง", heads,
              ["2026年 11月", "2026年 12月", "2027年 1月", "2027年 2月"])
        check("A: แถว entry ต่อเดือน", [t1[m]["row"] for m in (11, 12, 1, 2)], [12, 28, 44, 60])
        check("A: ข้อมูล 11/12/1月 ยกมาครบ", [t1[m]["cells"] for m in (11, 12, 1)],
              [cells0[m] for m in (11, 12, 1)])
        check("A: 2月 ว่าง", t1[2]["cells"], {})
        check("A: จำนวนเดือนในแท็บใหม่", len(t1), 4)
        return copy_id, t1
    finally:
        pass  # ลบสำเนาที่ main() — ห้าม `return` ใน finally


def phase_b_cloud(tok, t1):
    """B) rotate ด้วยโค้ด cloud (ตัวที่รันจริง) บนสำเนาใหม่ — 1 ธ.ค. 69 + ปลูก tmp ค้าง"""
    print("--- B) cloud main.py (ตัวรันจริง) @ 1 ธ.ค. 69 ---")
    c = json.load(open(tg.CRED, encoding="utf-8"))
    os.environ["SHEETS_CLIENT_ID"] = c["client_id"]
    os.environ["SHEETS_CLIENT_SECRET"] = c["client_secret"]
    os.environ["SHEETS_REFRESH_TOKEN"] = c["refresh_token"]
    cm = load_cloud()
    copy_id = fresh_copy(tok)
    print(f"    copy id = {copy_id}")
    try:
        cm.SHEET_ID = copy_id
        assert cm.SHEET_ID != SRC, "กันพลาด: ต้องไม่ใช่ไฟล์จริง"
        tb = cm.read_taicho()
        check("B: read_taicho อ่านปีจาก header", [tb[m]["year"] for m in (10, 11, 12, 1)],
              [2026, 2026, 2026, 2027])
        cells0 = {m: dict(tb[m]["cells"]) for m in (10, 11, 12, 1)}

        cm.date = fake_date(datetime.date(2026, 11, 1))
        check("B: rotate 1 พ.ย. คืน True", cm.rotate_table_if_needed(), True)
        check("B: แท็บใหม่ 11月-2月(2027)", cm.find_main_tab()[0], "千栄1568 11月-2月(2027)")
        t1c = cm.read_taicho()
        check("B: ข้อมูล 11/12/1月 ยกมาครบ", [t1c[m]["cells"] for m in (11, 12, 1)],
              [cells0[m] for m in (11, 12, 1)])
        heads = [read_tab(copy_id, "千栄1568 11月-2月(2027)", f"A{r}:A{r}", tok)[0][0]
                 for r in (9, 25, 41, 57)]
        check("B: หัวเดือนในชีตจริง", heads,
              ["2026年 11月", "2026年 12月", "2027年 1月", "2027年 2月"])

        print("    ปลูกแท็บ tmp ค้าง แล้ว rotate 1 ธ.ค. 69 ...")
        tabs1 = cm.list_tabs()
        api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{copy_id}:batchUpdate", tok,
            {"requests": [{"duplicateSheet": {"sourceSheetId": tabs1["千栄1568 11月-2月(2027)"],
                                             "insertSheetIndex": 0,
                                             "newSheetName": cm.TMP_TAB_TITLE}}]})
        check("B: ปลูก tmp สำเร็จ", cm.TMP_TAB_TITLE in cm.list_tabs(), True)

        cm.date = fake_date(datetime.date(2026, 12, 1))
        cm.rotate_table_if_needed()
        tabs2 = cm.list_tabs()
        check("B: แท็บใหม่ 12月-3月(2027)", cm.find_main_tab()[0], "千栄1568 12月-3月(2027)")
        check("B: ลบ tmp ที่ค้างแล้ว", cm.TMP_TAB_TITLE in tabs2, False)
        check("B: จำนวนแท็บ +1 จากรอบก่อน", len(tabs2), len(tabs1) + 1)
        t2 = cm.read_taicho()
        check("B: ลำดับเดือน", cm.window_months(t2), [12, 1, 2, 3])
        check("B: ปีของแต่ละเดือน", [t2[m]["year"] for m in (12, 1, 2, 3)], [2026, 2027, 2027, 2027])
        check("B: ข้อมูล 12/1/2月 ยกมาครบ", [t2[m]["cells"] for m in (12, 1, 2)],
              [t1c[m]["cells"] for m in (12, 1, 2)])

        n = len(cm.list_tabs())
        check("B: rotate ซ้ำวันเดิม คืน False", cm.rotate_table_if_needed(), False)
        check("B: rotate ซ้ำไม่เพิ่มแท็บ", len(cm.list_tabs()), n)
        cm.date = fake_date(datetime.date(2026, 12, 15))
        check("B: วันที่ไม่ใช่ 1 คืน False", cm.rotate_table_if_needed(), False)
    finally:
        # B ลบสำเนาตัวเอง (ห้าม `return` ใน finally — SyntaxWarning + กลืน exception)
        drop_copy(tok, copy_id)
        print(f"ลบสำเนาแล้ว {copy_id}")
    return None


def main():
    tok = tg.get_token()
    copies = []
    try:
        cid_a, t1 = phase_a_local(tok)
        copies.append(cid_a)
        cid_b = phase_b_cloud(tok, t1)
        if cid_b:
            copies.append(cid_b)
    finally:
        for cid in copies:
            try:
                drop_copy(tok, cid)
                print(f"ลบสำเนาแล้ว {cid}")
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ ลบสำเนาไม่สำเร็จ ต้องลบเอง: id={cid} ({e})")
    print()
    if FAILED:
        print(f"❌ FAIL {len(FAILED)} เคส: {FAILED}")
        return 1
    print("✅ PASS ทุกเคส — rotate จริง (local + cloud) ผ่านบนสำเนา")
    return 0


if __name__ == "__main__":
    sys.exit(main())
