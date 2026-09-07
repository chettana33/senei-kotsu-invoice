#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""taicho QA — golden gate ตรวจ PDF 台帳 ก่อนรายงานเสร็จ (กันพลาด renderer ซ้ำ lessons #82).

พี่เจ approve 7 ก.ย. 69: PDF ต้อง HTML+Edge (emoji ตัวจริง) ไม่ใช่ reportlab PNG.
เกณฑ์เทียบ golden: 9月-12月(0905).pdf / (0907).pdf = Skia/PDF + emoji เป็น text + font JP.

Usage:
  python tools/taicho_qa.py "path/to/台帳....pdf"   # exit 0 = ผ่าน, 1 = ไม่ผ่าน
  python tools/taicho_qa.py --list-golden
"""
import argparse
import os
import sys

GOOD_PRODUCER = ("Skia/PDF", "HeadlessChrome", "Edg/", "Chrome/")
BAD_PRODUCER = ("ReportLab",)
EMOJI = ("🟡", "🟢", "🔷")
GOLDEN = {
    "0905": r"H:\My Drive\チェー（個人）\King BUS\台帳入力（配車時間入力）\2026\9月\2026台帳 - 千栄1568 - 9月-12月(0905).pdf",
    "0907": r"H:\My Drive\チェー（個人）\King BUS\台帳入力（配車時間入力）\2026\9月\2026台帳 - 千栄1568 - 9月-12月(0907).pdf",
}

# ข้อความเส้นเดียวต่อช่อง: รูปแบบเวลาที่ไม่ควรโดนตัดกลางบรรทัด (wrap = เอาเนื้อหาไปบรรทัดใหม่)
# เช็ค: ทุก "HH:MM" ที่อยู่ในบรรทัดเดียวกับ 空/ホ/千栄 ต้องไม่ถูกแยก y เกินเกณฑ์
import re

_WRAP_RE = re.compile(r"\d{1,2}:\d{2}")


def qa_pdf(path):
    """คืน (ผ่านไหม, list ปัญหา, dict ข้อมูล)."""
    import pymupdf  # main python มี (ตรวจแล้ว 7 ก.ย. 69)
    problems = []
    info = {}
    if not os.path.exists(path):
        return False, [f"file not found: {path}"], info
    info["size_bytes"] = os.path.getsize(path)
    if info["size_bytes"] < 100_000:
        problems.append(f"ขนาด {info['size_bytes']}B < 100KB (HTML+Edge ฝัง font ควร ~165KB; reportlab ~34KB)")
    d = pymupdf.open(path)
    info["pages"] = d.page_count
    if d.page_count != 1:
        problems.append(f"pages={d.page_count} (ต้อง 1)")
    info["producer"] = (d.metadata or {}).get("producer", "")
    if any(b in info["producer"] for b in BAD_PRODUCER):
        problems.append(f"producer={info['producer']!r} = ReportLab (ห้าม — พี่เจ reject emoji PNG)")
    elif not any(g in info["producer"] for g in GOOD_PRODUCER):
        problems.append(f"producer={info['producer']!r} ไม่รู้จัก (คาด Skia/Chrome/Edge)")
    pg = d[0]
    info["page_w"] = round(pg.rect.width, 1)
    info["page_h"] = round(pg.rect.height, 1)
    if abs(pg.rect.width - 841.9) > 3 or abs(pg.rect.height - 595.0) > 3:
        problems.append(f"ขนาด {info['page_w']}x{info['page_h']} ไม่ใช่ A4 landscape 842x595")
    txt = pg.get_text()
    info["emoji"] = {ch: txt.count(ch) for ch in EMOJI}
    if sum(info["emoji"].values()) == 0:
        problems.append("emoji 🟡🟢🔷 ไม่เป็น text (reportlab ฝัง PNG = ผิด; HTML+Edge = เป็นตัวอักษรจริง)")
    fonts = {f[3] for f in pg.get_fonts()}
    info["fonts"] = sorted(fonts)[:10]
    if any("IPAex" in f for f in fonts) and not any("Skia" in info["producer"] for g in []):
        pass  # IPAex เองไม่ผิด ถ้า producer เป็น browser; ด่าน producer ครอบคลุมแล้ว
    # wrap เช็ค: เส้นเนื้อหา (มีเวลา) ที่ถูกตัดกลาง = เส้นเวลาเดียวกันตกคนละ y
    # ใช้ y ของ token "HH:MM" — ถ้า "HH:MM" กับ "H" (ชั่วโมงต่อไป) อยู่ y เดียวกันปกติ; วัดเส้นเวลาไม่ซ้ำ y เกิน 1.5 เท่าเส้นจำนวนช่อง (กัน wrap หลายชั้นเกิน)
    ys = {}
    for b in pg.get_text("dict").get("blocks", []):
        for ln in b.get("lines", []):
            y = round(ln["bbox"][1], 1)
            s = "".join(sp["text"] for sp in ln["spans"]).strip()
            if s and _WRAP_RE.search(s):
                ys.setdefault(y, []).append(s)
    info["content_lines"] = len(ys)
    if len(ys) > 60:
        problems.append(f"content y-lines={len(ys)} เกิน 60 (wrap เยอะผิดปกติ — golden ~33-39)")
    return (len(problems) == 0), problems, info


def main():
    ap = argparse.ArgumentParser(description="taicho PDF golden QA")
    ap.add_argument("path", nargs="?", help="path ไฟล์ PDF ที่จะตรวจ")
    ap.add_argument("--list-golden", action="store_true", help="แสดง golden file paths")
    a = ap.parse_args()
    if a.list_golden:
        for k, v in GOLDEN.items():
            print(f"{k}: {v} (มีอยู่จริง={os.path.exists(v)})")
        return 0
    if not a.path:
        ap.error("ต้องระบุ path PDF")
    ok, problems, info = qa_pdf(a.path)
    print(f"QA {'PASS ✅' if ok else 'FAIL ❌'} — {os.path.basename(a.path)}")
    for k, v in info.items():
        print(f"  {k}: {v}")
    if problems:
        print("  ปัญหา:")
        for p in problems:
            print(f"    - {p}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
