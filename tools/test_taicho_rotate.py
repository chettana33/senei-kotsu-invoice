#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_taicho_rotate.py — regression suite ของ "หน้าต่าง 4 เดือน" 台帳 (บั๊ก 1 ต.ค. 69)

บั๊กที่ suite นี้ล็อกไว้ (เคสจริงจาก Cloud Logging + ไฟล์ PDF ที่พี่เจเห็น):
  1. rotate วนซ้ำ: หน้าต่าง 10月-1月 → `sorted()` เรียง [1,10,11,12] ⇒ เดือนแรก = 1月 ≠ เดือนปัจจุบัน
     ⇒ ด่านจบลูปไม่จริง → `HTTP 400` ทุก 5 นาทีทั้งวัน + ทิ้งแท็บ `千栄1568 tmp` ค้าง
  2. เลือกแท็บหลักแบบ max M0 ไม่รู้ปี ⇒ 1 ม.ค. 70 จะเลือก `12月-3月(2027)` (แท็บเก่า) แล้วพังซ้ำ
  3. PDF/เว็บแอปกรองเดือนด้วย `month_start=9` ⇒ หน้าต่าง 10月-1月 แสดงแค่ 3 เดือน (1月 หาย)

รัน: python tools/test_taicho_rotate.py   (exit 0 = ผ่านทั้งหมด)
"""
import datetime
import importlib.util
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taicho_gsheets as tg  # noqa: E402
import taicho_pdf as tpdf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FAILED = []
TITLES_JAN = ["千栄1568 9月-12月(2026)", "千栄1568 10月-1月(2027)",
              "千栄1568 11月-2月(2027)", "千栄1568 12月-3月(2027)"]


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} | {name}")
    if not ok:
        print(f"        got ={got!r}\n        want={want!r}")
        FAILED.append(name)


def fake_t(months, years=None):
    """จำลอง read_taicho(): entry row เว้น 16 แถว (ตรงชีตจริง 12/28/44/60) + ปีจาก header"""
    ndays = {2: 28, 4: 30, 6: 30, 9: 30, 11: 30}
    out = {}
    for i, m in enumerate(months):
        out[m] = {"row": 12 + i * 16, "cells": {}, "ndays": ndays.get(m, 31),
                  "year": (years or {}).get(m)}
    return out


def load_cloud():
    """โหลด cloud main.py ด้วย stub firebase_functions (ไม่ต้องมี dependency ของ cloud)"""
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
        "taicho_cloud_main", REPO / "cloud-functions" / "taicho-monitor" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def simulate(plan_fn, months, today, max_iter=50):
    """เดินลูป rotate ด้วยแผนจาก plan_fn — คืน (จำนวนรอบ, หน้าต่างสุดท้าย, ไม่จบ?)"""
    steps = 0
    for _ in range(max_iter):
        plan = plan_fn(fake_t(months), today)
        if not plan:
            return steps, months, False
        steps += 1
        months = (months + [plan["new_month"]])[1:]
    return steps, months, True


def old_plan(t, today):
    """พฤติกรรมเดิม (บั๊ก 1): sorted() + 2027 if new_month == 1 else 2026"""
    months = sorted(t.keys())
    first, last = months[0], months[-1]
    if first == today.month:
        return None
    return {"new_month": (last % 12) + 1}


def old_pick_m0(titles):
    """พฤติกรรมเดิม (บั๊ก 2): เลือกแท็บหลัก = M0 (เดือนแรก) มากสุด"""
    best = None
    for t in titles:
        m = re.match(r"^千栄1568 (\d+)月-\d+月", t)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), t)
    return best[1] if best else None


def simulate_month_pick(pick_fn, titles, today, max_iter=50):
    """เดินลูป 'เลือกแท็บหลัก → rotate' — คืน (จำนวนรอบ, แท็บสุดท้าย, ไม่จบ?)"""
    titles = list(titles)
    steps = 0
    for _ in range(max_iter):
        name = pick_fn(titles)
        if not name:
            return steps, None, False
        months = [int(x) for x in re.findall(r"(\d+)月", name)]
        plan = tg.rotate_plan(fake_t(months), today)
        if not plan:
            return steps, name, False
        steps += 1
        if plan["title"] in titles:
            return steps, name, True          # ชื่อชน = rotate ไม่ได้อีก (อาการจริง 1 ต.ค. 69)
        titles.append(plan["title"])
    return steps, None, True


def main():
    oct1 = datetime.date(2026, 10, 1)

    print("--- A) ลำดับเดือน + rotate ---")
    check("window_months เรียงตามแถว (10,11,12,1)",
          tg.window_months(fake_t([10, 11, 12, 1])), [10, 11, 12, 1])
    check("🔴 regression: 10月-1月 @ 1 ต.ค. = ไม่ rotate",
          tg.rotate_plan(fake_t([10, 11, 12, 1]), oct1), None)

    p = tg.rotate_plan(fake_t([9, 10, 11, 12]), oct1)
    check("rotate 1 ต.ค.: title", p["title"], "千栄1568 10月-1月(2027)")
    check("rotate 1 ต.ค.: new_year = ปีของเดือนสุดท้าย", p["new_year"], 2027)
    check("rotate 1 ต.ค.: first_block", (p["first_block"], p["last_block"]), (16, 16))
    check("rotate 1 พ.ย. 69: title", tg.rotate_plan(fake_t([10, 11, 12, 1]),
          datetime.date(2026, 11, 1))["title"], "千栄1568 11月-2月(2027)")
    check("rotate 1 ธ.ค. 69: title", tg.rotate_plan(fake_t([11, 12, 1, 2]),
          datetime.date(2026, 12, 1))["title"], "千栄1568 12月-3月(2027)")
    check("rotate 1 ม.ค. 70: title", tg.rotate_plan(fake_t([12, 1, 2, 3]),
          datetime.date(2027, 1, 1))["title"], "千栄1568 1月-4月(2027)")
    check("rotate ไม่ข้ามปี (1 ก.ย. 69): title", tg.rotate_plan(fake_t([5, 6, 7, 8]),
          datetime.date(2026, 9, 1))["title"], "千栄1568 6月-9月(2026)")

    steps, final, runaway = simulate(tg.rotate_plan, [8, 9, 10, 11], oct1)
    check("catch-up 2 เดือน: จบใน 2 รอบ", (steps, final, runaway), (2, [10, 11, 12, 1], False))
    check("หน้าต่างถูกต้อง: 0 รอบ", simulate(tg.rotate_plan, [10, 11, 12, 1], oct1)[0], 0)
    check("🟡 หลักฐานบั๊กเดิม: sorted() ไม่มีทางจบ", simulate(old_plan, [10, 11, 12, 1], oct1)[2], True)

    print("--- B) เลือกแท็บหลักต้องรู้ปี (บั๊ก 2: ขึ้นปีใหม่) ---")
    check("main_tab_key 10月-1月(2027) เริ่มปี 2026",
          tg.main_tab_key("千栄1568 10月-1月(2027)"), (2026, 10))
    check("main_tab_key 1月-4月(2027) เริ่มปี 2027",
          tg.main_tab_key("千栄1568 1月-4月(2027)"), (2027, 1))
    check("ไม่จับแท็บ tmp/ประวัติ/sheet อื่น",
          [tg.main_tab_key(x) for x in ("千栄1568 tmp", "千栄1568 9月", "2024/10", "千栄1568 10月(2025)")],
          [None, None, None, None])
    check("ก่อน rotate 1 ม.ค. 70: ยังเลือก 12月-3月(2027)",
          tg.pick_main_tab(TITLES_JAN), "千栄1568 12月-3月(2027)")
    check("หลัง rotate 1 ม.ค. 70: ต้องเลือก 1月-4月(2027) ไม่ใช่แท็บเก่า",
          tg.pick_main_tab(TITLES_JAN + ["千栄1568 1月-4月(2027)"]), "千栄1568 1月-4月(2027)")
    steps, last, stuck = simulate_month_pick(tg.pick_main_tab, TITLES_JAN, datetime.date(2027, 1, 1))
    check("1 ม.ค. 70 ด้วยโค้ดใหม่: rotate 1 รอบแล้วจบ", (steps, last, stuck),
          (1, "千栄1568 1月-4月(2027)", False))
    steps, _, stuck = simulate_month_pick(old_pick_m0, TITLES_JAN, datetime.date(2027, 1, 1))
    check("🟡 หลักฐานบั๊กเดิม: max-M0 ขึ้นปีใหม่ไม่จบ (HTTP 400 ทุก 5 นาที)",
          stuck, True)

    print("--- C) PDF ต้องครบเดือนตามหน้าต่างจริง (บั๊ก 3) ---")
    t = fake_t([10, 11, 12, 1], years={10: 2026, 11: 2026, 12: 2026, 1: 2027})
    t[1]["cells"] = {1: "ホ 06:00 空"}
    heads = re.findall(r">(\d{4}年 \d+月)<", tpdf.render_html(t, "1001"))
    check("PDF หน้าต่าง 10月-1月: ครบ 4 เดือน + ปีถูก",
          heads, ["2026年 10月", "2026年 11月", "2026年 12月", "2027年 1月"])
    check("PDF: ข้อมูล 1月 ถูกพิมพ์จริง", "ホ" in tpdf.render_html(t, "1001"), True)
    t2 = fake_t([12, 1, 2, 3], years={12: 2026, 1: 2027, 2: 2027, 3: 2027})
    check("PDF หน้าต่าง 12月-3月: เรียงถูก ข้ามปี",
          re.findall(r">(\d{4}年 \d+月)<", tpdf.render_html(t2, "1201")),
          ["2026年 12月", "2027年 1月", "2027年 2月", "2027年 3月"])

    print("--- D) cloud mirror ต้องตรงกับ tools ---")
    cloud = load_cloud()
    cases = [([10, 11, 12, 1], oct1), ([9, 10, 11, 12], oct1),
             ([10, 11, 12, 1], datetime.date(2026, 11, 1)),
             ([8, 9, 10, 11], oct1), ([12, 1, 2, 3], datetime.date(2027, 1, 1))]
    same = all(tg.rotate_plan(fake_t(m), d) == cloud.rotate_plan(fake_t(m), d) for m, d in cases)
    check("rotate_plan: cloud = tools", same, True)
    check("window_months: cloud = tools",
          cloud.window_months(fake_t([10, 11, 12, 1])), tg.window_months(fake_t([10, 11, 12, 1])))
    check("pick_main_tab: cloud = tools",
          cloud.pick_main_tab(TITLES_JAN + ["千栄1568 1月-4月(2027)"]),
          tg.pick_main_tab(TITLES_JAN + ["千栄1568 1月-4月(2027)"]))
    check("TMP title ตรงกัน 2 ที่",
          (tg.TMP_TAB_TITLE, cloud.TMP_TAB_TITLE), ("千栄1568 tmp", "千栄1568 tmp"))
    check("tmp ไม่ถูกจับเป็นแท็บหลัก", tg.main_tab_key(tg.TMP_TAB_TITLE), None)

    print()
    if FAILED:
        print(f"❌ FAIL {len(FAILED)} เคส: {FAILED}")
        return 1
    print("✅ PASS ทุกเคส")
    return 0


if __name__ == "__main__":
    sys.exit(main())
