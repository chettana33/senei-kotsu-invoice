#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_taicho_rotate.py — เทสต์ pure logic ของ rotate 台帳 รายเดือน (regression 1 ต.ค. 69)

เคสจริงที่พัง: หน้าต่าง 10月-1月 → `sorted()` เรียงเป็น [1,10,11,12] ⇒ เดือนแรก = 1月 ≠ เดือนปัจจุบัน
⇒ ด่านจบลูปไม่จริง → rotate วนซ้ำไม่จบ + `HTTP 400` ทุก 5 นาทีทั้งวัน + ทิ้งแท็บ `千栄1568 tmp` ค้าง
(ดู rules `taicho.md` §6 · PC: taicho)

รัน: python tools/test_taicho_rotate.py   (exit 0 = ผ่านทั้งหมด)
"""
import datetime
import importlib.util
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taicho_gsheets as tg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} | {name}\n        got ={got!r}\n        want={want!r}")
    if not ok:
        FAILED.append(name)


def fake_t(months):
    """จำลอง read_taicho(): entry row เว้น 16 แถว (ตรงชีตจริง: 10月=12, 11月=28, 12月=44, 1月=60)"""
    return {m: {"row": 12 + i * 16, "cells": {}, "ndays": 31} for i, m in enumerate(months)}


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
    """พฤติกรรมเดิม (บั๊ก): sorted() + 2027 if new_month == 1 else 2026"""
    months = sorted(t.keys())
    first, last = months[0], months[-1]
    if first == today.month:
        return None
    return {"new_month": (last % 12) + 1}


def main():
    oct1 = datetime.date(2026, 10, 1)

    # 1) ลำดับเดือน = ลำดับแถวในชีต ไม่ใช่ sorted()
    check("window_months 10/11/12/1", tg.window_months(fake_t([10, 11, 12, 1])), [10, 11, 12, 1])

    # 2) 🔴 regression: หน้าต่างถูกต้องแล้ว (10月-1月) @ 1 ต.ค. → ต้องไม่ rotate (เดิมวนซ้ำไม่จบ)
    check("regression: 10月-1月 @ 1 ต.ค. = ไม่ rotate", tg.rotate_plan(fake_t([10, 11, 12, 1]), oct1), None)

    # 3) เคส rotate จริงของวันนี้: 9月-12月 @ 1 ต.ค. → 10月-1月(2027) + block 16 แถว
    p = tg.rotate_plan(fake_t([9, 10, 11, 12]), oct1)
    check("rotate 1 ต.ค.: title", p["title"], "千栄1568 10月-1月(2027)")
    check("rotate 1 ต.ค.: new_month", p["new_month"], 1)
    check("rotate 1 ต.ค.: new_year (ปีเดือนสุดท้าย)", p["new_year"], 2027)
    check("rotate 1 ต.ค.: first_block", p["first_block"], 16)
    check("rotate 1 ต.ค.: last_block", p["last_block"], 16)

    # 4) 🟡 บั๊กปี: 1 พ.ย. 69 → เดือนใหม่ = 2月 2027 (เดิมได้ 2026 ⇒ หัวเดือนเขียนผิด)
    p = tg.rotate_plan(fake_t([10, 11, 12, 1]), datetime.date(2026, 11, 1))
    check("rotate 1 พ.ย. 69: title", p["title"], "千栄1568 11月-2月(2027)")
    check("rotate 1 พ.ย. 69: new_year", p["new_year"], 2027)

    p = tg.rotate_plan(fake_t([11, 12, 1, 2]), datetime.date(2026, 12, 1))
    check("rotate 1 ธ.ค. 69: title", p["title"], "千栄1568 12月-3月(2027)")

    p = tg.rotate_plan(fake_t([12, 1, 2, 3]), datetime.date(2027, 1, 1))
    check("rotate 1 ม.ค. 70: title", p["title"], "千栄1568 1月-4月(2027)")

    p = tg.rotate_plan(fake_t([5, 6, 7, 8]), datetime.date(2026, 9, 1))
    check("rotate ไม่ข้ามปี (1 ก.ย.): title", p["title"], "千栄1568 6月-9月(2026)")

    # 5) ลูปต้องจบ (ครอบค้างหลายเดือน) — เดิม (sorted) ไม่มีทางจบ
    steps, final, runaway = simulate(tg.rotate_plan, [8, 9, 10, 11], oct1)
    check("catch-up 2 เดือน: จำนวนรอบ", steps, 2)
    check("catch-up: หน้าต่างสุดท้าย", final, [10, 11, 12, 1])
    check("catch-up: จบจริง (ไม่ runaway)", runaway, False)

    steps, _, runaway = simulate(tg.rotate_plan, [10, 11, 12, 1], oct1)
    check("หน้าต่างถูกต้อง: 0 รอบ", steps, 0)

    _, _, old_runaway = simulate(old_plan, [10, 11, 12, 1], oct1)
    check("🟡 หลักฐานบั๊กเดิม: sorted() ไม่มีทางจบ", old_runaway, True)

    # 6) cloud mirror ต้องให้ผลเท่ากับ tools/taicho_gsheets.py เป๊ะ (กันโค้ด 2 ที่เพี้ยนจากกัน)
    cloud = load_cloud()
    cases = [([10, 11, 12, 1], oct1), ([9, 10, 11, 12], oct1),
             ([10, 11, 12, 1], datetime.date(2026, 11, 1)),
             ([8, 9, 10, 11], oct1), ([12, 1, 2, 3], datetime.date(2027, 1, 1))]
    same = True
    for months, today in cases:
        if tg.rotate_plan(fake_t(months), today) != cloud.rotate_plan(fake_t(months), today):
            same = False
    check("cloud main.py = tools/taicho_gsheets.py (mirror ตรงกัน)", same, True)
    check("cloud: เรียงเดือนตามแถว", cloud.window_months(fake_t([10, 11, 12, 1])), [10, 11, 12, 1])

    # 7) ชื่อแท็บชั่วคราวต้องไม่ถูก find_main_tab จับเป็นแท็บหลัก + ค่าคงที่ตรงกัน 2 ที่
    check("TMP title ตรงกัน", (tg.TMP_TAB_TITLE, cloud.TMP_TAB_TITLE), ("千栄1568 tmp", "千栄1568 tmp"))
    check("tmp ไม่ match regex แท็บหลัก", bool(tg.re.match(r"^千栄1568 (\d+)月-\d+月", tg.TMP_TAB_TITLE)), False)

    print()
    if FAILED:
        print(f"❌ FAIL {len(FAILED)} เคส: {FAILED}")
        return 1
    print("✅ PASS ทุกเคส")
    return 0


if __name__ == "__main__":
    sys.exit(main())
