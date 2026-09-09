#!/usr/bin/env python3
"""taicho_pdf_auto.py — สร้าง PDF 台帳 อัตโนมัติหลัง cloud apply (เพิ่ม 8 ก.ย. 69)

Task Scheduler: PaTeaw-TaichoPdf (จ-ศ 19:15) — cloud taicho-monitor ทำ apply+LINE แล้ว (16-19:00);
สคริปต์นี้สแกนใบขอรถใน Drive → ใบที่: (1) ยังไม่มี PDF หรือ PDF เก่ากว่าใบ (2) master มีข้อมูลวันนั้น
(apply เสร็จ) → สร้าง PDF (HTML+Edge) + QA (taicho_qa.py)

PDF = สร้างที่เครื่องเท่านั้น (HTML+Edge, rule taicho.md §2) — ไม่แทรก apply / ไม่แตะ cloud / ไม่แตะใบเก่า
ล้ม = exit 1 → task_health alert ผ่าน LastResult (log ลงไฟล์เท่านั้น — รันด้วย pythonw)
"""
import datetime as dt
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import taicho_gsheets as tg  # noqa: E402

LOG = os.path.join(TOOLS, "taicho_pdf_auto.log")
STATE = os.path.join(TOOLS, "taicho_pdf_auto_state.json")
FORM_BASE = tg.FORM_BASE


def log(msg):
    line = f"{dt.datetime.now().isoformat()} {msg}"
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_baseline():
    """baseline_ts = เวลาติดตั้งรอบแรก (กัน rebuild ใบเก่าที่เคยทำ PDF ไว้แล้ว);
    ใบใหม่หลังติดตั้ง + ใบของวันนี้ = สร้างได้เสมอ"""
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh).get("baseline_ts", 0.0)
    except (OSError, ValueError):
        return 0.0


def save_baseline(ts):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump({"baseline_ts": ts}, fh, ensure_ascii=False, indent=2)


def find_python_exe():
    """QA child รันด้วย python.exe (ไม่ใช่ pythonw — กัน stdout หาย)"""
    exe = sys.executable or "python"
    alt = exe.replace("pythonw.exe", "python.exe")
    return alt if os.path.exists(alt) else exe


def main():
    # Task รันทุก 10 นาที (24/7) — ทำงานเฉพาะ จ-ศ 16:00-19:40 (ใบ 千栄 มา 16-19 + เผื่อสาย)
    # นอก window/วันหยุด = ออกเงียบ กันอ่าน master นอกเวลา (429) — 9 ก.ย. 69
    now_t = dt.datetime.now().time()
    if dt.datetime.now().weekday() >= 5:  # เสาร์-อาทิตย์
        return 0
    if not (dt.time(16, 0) <= now_t <= dt.time(19, 40)):
        return 0
    baseline = load_baseline()
    if baseline <= 0:  # รอบแรก = ตั้ง baseline ตอนนี้ (ไม่ rebuild ใบเก่า)
        baseline = dt.datetime.now().timestamp()
        save_baseline(baseline)
        log(f"baseline ตั้งแล้ว: {dt.datetime.fromtimestamp(baseline).isoformat()}")
    today = dt.date.today().day
    now_mm = dt.date.today().month
    # master อ่านครั้งเดียว (กัน 429) — keys = เดือนที่ active ใน tab ปัจจุบัน (เลื่อน 4 เดือน)
    try:
        taicho = tg.read_taicho()
    except Exception as e:  # noqa: BLE001
        log(f"FAIL read master: {type(e).__name__}: {e}")
        return 1
    made = []  # (mmdd, pdf_path)
    for mm in sorted(k for k in taicho.keys() if isinstance(k, int)):
        month_dir = os.path.join(FORM_BASE, f"{mm}月")
        if not os.path.isdir(month_dir):
            continue
        cells = (taicho.get(mm) or {}).get("cells", {})
        try:
            names = sorted(os.listdir(month_dir))
        except OSError:
            continue
        for fn in names:
            # ใบขอรถ: MMDD_千栄交通㈱_貸切バス手配依頼書.xlsx
            if not (fn.endswith(".xlsx") and len(fn) >= 4 and fn[:4].isdigit()
                    and "_千栄交通" in fn and int(fn[:2]) == mm):
                continue
            mmdd = fn[:4]
            leaf = os.path.join(month_dir, fn)
            leaf_mtime = os.path.getmtime(leaf)
            # ใบเก่าที่เคยทำ PDF ไว้แล้ว (ก่อนติดตั้ง) = ไม่แตะ — สร้างเฉพาะใบใหม่/ใบวันนี้
            is_today = (int(mmdd[2:]) == today and int(mmdd[:2]) == now_mm)
            if leaf_mtime < baseline and not is_today:
                continue
            pdf_name = tg.pdf_filename(mm, mmdd)
            pdf_path = os.path.join(month_dir, pdf_name)
            # มี PDF แล้วและใหม่กว่า/เท่าใบ = สร้างไปแล้ว
            if os.path.exists(pdf_path) and os.path.getmtime(pdf_path) >= leaf_mtime:
                continue
            day = int(mmdd[2:])
            if day not in cells:
                if is_today:
                    # ใบวันนี้: 千栄 อาจยังไม่ลงรายการวันที่ตัวเอง (เช่น 9/9/69) แต่ master เปลี่ยน
                    # จากรายการวันอื่นในใบแล้ว → สร้าง PDF snapshot รายวันได้ (9 ก.ย. 69)
                    log(f"BUILD {mmdd} (snapshot ใบวันนี้ — ใบไม่มี cell {mm}月{day:02d})")
                else:
                    log(f"SKIP {mmdd}: ยังไม่ apply ลง master (ไม่มี cell {mm}月{day:02d}) — รอรอบหน้า")
                    continue
            log(f"BUILD {mmdd}: ใบ {fn} -> {pdf_name}")
            try:
                tg.export_pdf(pdf_name, month_dir)  # HTML+Edge primary (taicho_pdf.build_pdf)
            except Exception as e:  # noqa: BLE001
                log(f"BUILD FAIL {mmdd}: {type(e).__name__}: {e}")
                return 1
            made.append((mmdd, pdf_path))
    fails = 0
    py = find_python_exe()
    qa = os.path.join(TOOLS, "taicho_qa.py")
    for mmdd, pdf_path in made:
        try:
            r = subprocess.run([py, qa, pdf_path], capture_output=True, text=True, timeout=240)
            out = r.stdout + r.stderr
        except Exception as e:  # noqa: BLE001
            log(f"QA ERROR {pdf_path}: {type(e).__name__}: {e}")
            fails += 1
            continue
        if r.returncode == 0 and "QA PASS" in out:
            log(f"QA PASS {pdf_path}")
        else:
            fails += 1
            log(f"QA FAIL {pdf_path}: {out[-300:]}")
    if not made:
        log("ไม่มีใบใหม่ (PDF ล่าสุดครบทุกใบ) — exit 0")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
