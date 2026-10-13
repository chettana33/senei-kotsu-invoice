"""เทสต์: การอ่านช่อง経由地ของใบขอรถ — รวมเคส '→経由なし' (ยกเลิก経由地)

ที่มา 13 ต.ค. 69 (รอบ 152): ใบ 1013 แถว KIKO FD261018 เขียน `成田山(1H)／→経由なし`
แต่โค้ดอ่านแค่ `(1H)` ⇒ 台帳 ยังโชว์ `1H` และ diff ตอบ "ไม่มีความต่าง" (คำสั่งถูกกลืนเงียบ)
พี่เจสั่ง "แก้" ⇒ hours_from ต้องคืน None เมื่อเจอ 経由なし/経由無し

รัน: python tools/test_taicho_keiyu.py   (ไม่ยิงเน็ต · ไม่แตะชีต)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taicho_gsheets as tgs  # noqa: E402

FAIL = 0


def check(label: str, got, want) -> None:
    global FAIL
    ok = got == want
    if not ok:
        FAIL += 1
    print(f"{'✅' if ok else '❌'} {label}: got={got!r} want={want!r}")


# ---- 1) hours_from: เคสพื้นฐาน (ต้องไม่พังของเดิม) ----
check("hours_from('AEON(2H)')", tgs.hours_from("AEON(2H)"), "2H")
check("hours_from('成田山(1H)')", tgs.hours_from("成田山(1H)"), "1H")
check("hours_from(None)", tgs.hours_from(None), None)
check("hours_from('')", tgs.hours_from(""), None)

# ---- 2) hours_from: เคสใหม่ = ยกเลิก経由地 ----
check("hours_from('成田山(1H)\\n→経由なし')", tgs.hours_from("成田山(1H)\n→経由なし"), None)
check("hours_from('経由なし')", tgs.hours_from("経由なし"), None)
check("hours_from('AEON(2H) →経由なし')", tgs.hours_from("AEON(2H) →経由なし"), None)
check("hours_from('成田山(1H)\\n→経由無し')", tgs.hours_from("成田山(1H)\n→経由無し"), None)

# ---- 3) ใบจริง 1013: 18 ต.ค. ต้องได้ h = None (ไม่ใช่ '1H') ----
FORM = (r"H:\My Drive\チェー（個人）\King BUS\台帳入力（配車時間入力）"
        r"\2026\10月\1013_千栄交通㈱_貸切バス手配依頼書.xlsx")
if os.path.exists(FORM):
    out = tgs.read_request_form(FORM)
    d = next((k for k in out if getattr(k, "isoformat", lambda: "")() == "2026-10-18"), None)
    if d is None:
        check("ใบ 1013 มีวัน 2026-10-18", False, True)
    else:
        hs = [e.get("h") for e in out[d]]
        check("ใบ 1013 · 18 ต.ค. · h ของทุกเที่ยว", hs, [None])
        check("ใบ 1013 · 18 ต.ค. · เวลาออกตัว", [e.get("t") for e in out[d]], ["13:55"])
else:
    print("⚠️ ไม่พบไฟล์ใบ 1013 (ข้ามเทสต์ข้อมูลจริง)")

print()
if FAIL:
    print(f"❌ ไม่ผ่าน {FAIL} ข้อ")
    raise SystemExit(1)
print("✅ ผ่านทุกข้อ")
