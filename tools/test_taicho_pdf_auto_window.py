#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_taicho_pdf_auto_window.py — เทสต์ `in_window()` ใน taicho_pdf_auto.py

ทำไม (22 ต.ค. 69 · review มุมคนนอก): หน้าต่าง 16:00-20:00 → 23:30 ถูกแก้เพราะเคสจริง
(เครื่อง sleep 17:05-20:27 · ใบ 1022 เข้า 17:20 · task รัน 20:33 = เลยหน้าต่าง → คืนนั้นไม่มี PDF)
แต่ `main()` เดิมเรียก `dt.datetime.now()` ตรง ๆ = เกณฑ์นี้ไม่มีอะไรพิสูจน์เลย

รัน: python tools/test_taicho_pdf_auto_window.py   (exit 0 = ผ่าน · ไม่ยิงเน็ต/ไม่แตะ Drive)
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taicho_pdf_auto as auto  # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} | {name}")
    if not ok:
        print(f"        got ={got!r}\n        want={want!r}")
        FAILED.append(name)


THU = (2026, 10, 22)   # พฤหัสบดี
SAT = (2026, 10, 24)   # เสาร์

check("พฤ. 20:33 (เคสจริง 22 ต.ค. — ตื่นสาย) = ทำงาน",
      auto.in_window(dt.datetime(*THU, 20, 33)), True)
check("พฤ. 20:41 (รอบแรกหลังตื่น) = ทำงาน",
      auto.in_window(dt.datetime(*THU, 20, 41)), True)
check("พฤ. 16:00 (ขอบหน้า) = ทำงาน",
      auto.in_window(dt.datetime(*THU, 16, 0)), True)
check("พฤ. 15:59 (ก่อนหน้าต่าง) = ไม่ทำงาน",
      auto.in_window(dt.datetime(*THU, 15, 59)), False)
check("พฤ. 23:30 (ขอบหลัง) = ทำงาน",
      auto.in_window(dt.datetime(*THU, 23, 30)), True)
check("พฤ. 23:31 (เลยหน้าต่าง) = ไม่ทำงาน",
      auto.in_window(dt.datetime(*THU, 23, 31)), False)
check("เสาร์ 17:00 = ไม่ทำงาน",
      auto.in_window(dt.datetime(*SAT, 17, 0)), False)

print(f"\n{'PASS ครบ' if not FAILED else f'FAIL {len(FAILED)}: ' + ', '.join(FAILED)}")
raise SystemExit(1 if FAILED else 0)
