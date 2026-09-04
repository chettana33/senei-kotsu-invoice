#!/usr/bin/env python3
"""king-bus-taicho — สร้าง PDF 台帳 ผ่าน HTML + Edge headless print (เส้นทางหลัก 1 ก.ย. 69).

ทำไม: Sheets export/Excel COM/browser print หน้า Sheets = emoji 🟡🟢🔷 ไม่ติด (glyph ไม่ฝัง)
หรือ printer ใหญ่เกิน (lessons #55-58). HTML + Edge headless = ฝัง emoji เป็น Type3 font
(เหมือน -Jay print จากเบราว์เซอร์) → ทุก viewer เห็นสี (lessons #60).

Usage:
  python tools/taicho_pdf.py pdf --date 0901 [--month 9]
"""
import argparse
import os
import subprocess
import sys
import tempfile

import taicho_gsheets as tg

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# สีหัวเดือน 30/31 วัน (lessons #51; ตรง -Jay): 30 = โทนเย็น, 31 = โทนอุ่น
HEADER_COLOR = {
    30: ["#c7e3ff", "#eaf8ea"],   # ฟ้า, เขียว
    31: ["#ffe5ea", "#fff2e7", "#ffe3c9"],  # ชมพู, ส้ม, เหลืองอ่อน
}
# เดือน -> ดัชนีสี (สลับให้ 2 เดือนติดกันไม่ซ้ำ; 4 เดือนใน tab ต้องต่างกัน)
MONTH_COLOR_IDX = {9: 0, 10: 0, 11: 1, 12: 1}


def _html_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _html_escape_d2(s):
    """escape + ระบาย 空=ฟ้า ホ=ส้ม (D2 — พี่เจอนุมัติ 5 ก.ย. 69)"""
    out = []
    for ch in s:
        if ch == "空":
            out.append('<span style="color:#1f61d9">空</span>')
        elif ch == "ホ":
            out.append('<span style="color:#de6b0f">ホ</span>')
        else:
            out.append(_html_escape(ch))
    return "".join(out)


def _cell_lines(value):
    """แยกค่าเซลล์เป็นบรรทัด (ตัด \n ทิ้ง + ลบบรรทัดว่างปลาย). คืน list[str]."""
    if not value:
        return []
    lines = [ln for ln in value.split("\n") if ln.strip() != ""]
    return lines


def render_html(taicho, mmdd, month_start=9, month_count=4):
    """สร้าง HTML 台帳 4 เดือน (rotate จาก month_start). คืน str.

    ช่องวันกว้างตามเนื้อหา (table-layout auto) + แต่ละบรรทัด white-space nowrap
    → '🔷13:00 1H🟢' อยู่บรรทัดเดียว ไม่ตัดกลาง (พี่เจขอ 1 ก.ย. 69)."""
    months = sorted(m for m in taicho.keys() if month_start <= m < month_start + month_count)
    if not months:
        # tab rotate ข้ามปี (เช่น 12-03): เอาเดือนที่มี
        months = sorted(taicho.keys())[:month_count]
    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{mmdd}台帳 - 千栄1568</title>
<style>
  @page {{ size: A4 landscape; margin: 7mm 6mm; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "MS PGothic", "Yu Gothic", sans-serif; }}
  .month {{ margin-bottom: 6pt; page-break-inside: avoid; }}
  /* fixed layout + ทุกคอลัมน์กว้างเท่ากัน (26pt) — รวม ~802pt พอดี A4 landscape */
  table {{ border-collapse: collapse; width: auto; table-layout: fixed; }}
  .title-row td {{
    font-weight: bold; font-size: 8pt; text-align: center;
    padding: 1pt 0; border: 0.5pt solid #888; background: var(--hdr);
  }}
  .day-row td {{
    border: 0.5pt solid #bbb; text-align: center; font-size: 3.5pt;
    background: #fafafa; color: #333; padding: 0.5pt 0; white-space: nowrap;
    vertical-align: middle;
  }}
  .day-row td:first-child, .data-row td:first-child {{
    width: 22pt; min-width: 22pt; border-right: 1pt solid #888;
  }}
  /* คอลัมน์วัน (ยกเว้นอันแรก) = กว้างเท่ากัน พอดี A4 30 ช่อง (782/30 ≈ 26pt) */
  .day-row td:not(:first-child), .data-row td:not(:first-child) {{
    width: 26pt;
  }}
  .data-row td {{
    border: 0.5pt solid #888; height: auto; min-height: 20pt;
    vertical-align: middle; text-align: center; font-size: 4pt; font-weight: bold;
    padding: 1pt 0.5pt; white-space: nowrap; overflow: visible;
    line-height: 1.3;
  }}
  .data-row td:first-child {{
    font-size: 5pt; white-space: normal; text-align: center;
    padding-left: 0; vertical-align: middle;
  }}
  .legend {{ margin-top: 2pt; font-size: 5pt; font-weight: bold; display: flex; gap: 10pt; }}
  .legend .dot {{ margin-right: 3pt; }}
</style></head><body>""")
    for i, m in enumerate(months):
        ndays = taicho[m]["ndays"]
        cells = taicho[m].get("cells", {})
        hdr = HEADER_COLOR[30 if ndays == 30 else 31][MONTH_COLOR_IDX.get(m, 0)]
        parts.append(f'<div class="month"><table>')
        parts.append(f'<tr class="title-row"><td colspan="{ndays + 1}" style="--hdr:{hdr}">2026年 {m}月</td></tr>')
        # แถววัน
        days_html = "".join(f"<td>{d}</td>" for d in range(1, ndays + 1))
        parts.append(f'<tr class="day-row"><td></td>{days_html}</tr>')
        # แถวข้อมูล
        data_cells = []
        for d in range(1, ndays + 1):
            v = cells.get(d, "")
            lines = _cell_lines(v)
            if not lines:
                data_cells.append("<td></td>")
            else:
                inner = "<br>".join(_html_escape_d2(ln) for ln in lines)
                data_cells.append(f"<td>{inner}</td>")
        parts.append(f'<tr class="data-row"><td>千栄1568</td>{"".join(data_cells)}</tr>')
        parts.append("</table>")
        parts.append("</div>")
    # legend ชุดเดียวท้ายตาราง (พี่เจสั่ง 5 ก.ย. 69)
    parts.append('<div class="legend" style="display:block">'
                 '<span><span class="dot">🟡</span>変更は</span>'
                 '<span style="margin-left:14pt"><span class="dot">🟢</span>新規は</span></div>')
    parts.append('<div class="legend" style="display:block;margin-top:4pt">'
                 '<span style="color:#de6b0f">ホ</span>=ホテル（橙）　'
                 '<span style="color:#1f61d9">空</span>=空港（青）　左=出発　右=行先'
                 '<br/><span style="color:#de6b0f">ホ</span> 09:00 1H '
                 '<span style="color:#1f61d9">空</span> ＝ ホテルから空港（1H 経由）</div>')
    parts.append("</body></html>")
    return "\n".join(parts)


def build_pdf(out_path, month_dir):
    """อ่าน台帳 จาก Sheets → เขียนทับ HTML เดิม (เดือนนั้น) → Edge headless print → PDF.
    คืน path เต็ม. ล้ม = raise (caller fallback)."""
    taicho = tg.read_taicho()
    mmdd = os.path.basename(out_path).split("(")[1].split(")")[0]
    html = render_html(taicho, mmdd)
    os.makedirs(month_dir, exist_ok=True)
    # เขียนทับ HTML เดิม (พี่เจขอ 1 ก.ย. 69: ไม่ลบ-สร้างใหม่ทุกครั้ง — แก้ดูได้ ณ เดือนนั้น)
    html_path = os.path.join(month_dir, f"_taicho_{mmdd}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    full = os.path.join(month_dir, out_path)
    url = "file:///" + html_path.replace("\\", "/")
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--print-to-pdf=" + full, "--no-pdf-header-footer", url]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.exists(full) or os.path.getsize(full) == 0:
        raise RuntimeError(f"Edge print failed: {proc.stderr[-300:]}")
    print(f"PDF saved (html+edge): {full} ({os.path.getsize(full)} bytes)")
    print(f"HTML เก็บไว้: {html_path}")
    return full


def main():
    ap = argparse.ArgumentParser(description="taicho PDF ผ่าน HTML + Edge headless")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pdf")
    p.add_argument("--date", required=True, help="MMDD เช่น 0901")
    p.add_argument("--month", help="MM (default: เดือนของ MMDD)")
    p.set_defaults(fn=lambda a: build_pdf(
        tg.pdf_filename(int(a.month or a.date[0:2]), a.date),
        os.path.join(tg.FORM_BASE, f"{int(a.month or a.date[0:2])}月")))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
