# -*- coding: utf-8 -*-
"""台帳 PDF (cloud, pure-Python) — reportlab renderer สำหรับ Cloud Function taicho-monitor.

ทำไม: function gen2 python = buildpacks (pip เท่านั้น, ไม่มี apt) — ใส่ chromium/ฟอนต์ระบบไม่ได้
(lessons #79-80). phase 2b เลยสร้าง PDF ด้วย reportlab ล้วน (เลือกของพี่เจ 6 ก.ย. 69):
- ฝัง emoji 🟡🟢🔷 = PNG (assets/emoji_*.png — render จาก Segoe UI Emoji ของเครื่อง = ตรงกับ
  PDF local HTML+Edge ที่พี่เจอนุมัติแล้ว; PNG ฝังลง PDF = viewer ทุกตัวเห็นสี)
- ฟอนต์ JP = IPAexGothic (fonts/ipaexg.ttf + license — เผยแพร่ได้ repo public)
- Layout เทียบ spec ของ tools/taicho_pdf.py render_html (local HTML+Edge):
  A4 landscape, 4 เดือน, title สีหัวเดือน 30/31 วัน, day-row, data-row (ช่องวัน), legend

API: render_taicho_pdf(taicho, mmdd, out_path) — taicho รูปเดียวกับ main.read_taicho():
      {month: {"row": int, "cells": {day: str}, "ndays": int}}
"""
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(_DIR, "fonts", "ipaexg.ttf")
FONT_NAME = "IPAex"
EMOJI_IMG = {
    "🟡": os.path.join(_DIR, "assets", "emoji_yellow.png"),
    "🟢": os.path.join(_DIR, "assets", "emoji_green.png"),
    "🔷": os.path.join(_DIR, "assets", "emoji_blue.png"),
}
# หน้าละเอียด A4 landscape 842x595, ขอบตาม HTML @page 7mm/6mm
PAGE_W, PAGE_H = landscape(A4)
MARGIN_LR = 6 * 2.83465   # 6mm
MARGIN_TB = 7 * 2.83465   # 7mm
AVAIL_W = PAGE_W - 2 * MARGIN_LR
FIRST_COL_W = 22.0

# สีหัวเดือน 30/31 วัน (ตรง tools/taicho_pdf.py HEADER_COLOR/MONTH_COLOR_IDX)
HEADER_COLOR = {
    30: ["#c7e3ff", "#eaf8ea"],                          # ฟ้า, เขียว
    31: ["#ffe5ea", "#fff2e7", "#ffe3c9"],               # ชมพู, ส้ม, เหลืองอ่อน
}
MONTH_COLOR_IDX = {9: 0, 10: 0, 11: 1, 12: 1}
GRID = colors.HexColor("#888888")
GRID_LIGHT = colors.HexColor("#bbbbbb")
DAY_BG = colors.HexColor("#fafafa")

_font_registered = False


def _ensure_font():
    global _font_registered
    if _font_registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
    _font_registered = True


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _emoji_ratio(name):
    """คืน (w_px, h_px) ของ PNG เพื่อคำนวณสัดส่วนตอน scale"""
    from PIL import Image
    with Image.open(EMOJI_IMG[name]) as im:
        return im.size


def _line_html(line, emoji_h):
    """แปลง 1 บรรทัดของเซลล์ → HTML สำหรับ Paragraph: emoji กลายเป็น <img> inline.
    emoji_h = ความสูงที่ต้องการแสดง (pt) — ความกว้างตามสัดส่วน PNG."""
    parts = re.split("([" + "".join(re.escape(e) for e in EMOJI_IMG) + "])", line)
    html = []
    for p in parts:
        if not p:
            continue
        if p in EMOJI_IMG:
            w, h = _emoji_ratio(p)
            wpt = emoji_h * w / h
            html.append(f'<img src="{EMOJI_IMG[p]}" width="{wpt:.2f}" height="{emoji_h:.2f}"/>')
        else:
            html.append(_esc(p))
    return "".join(html)


def _cell_parts(value):
    """แยกค่าเซลล์เป็นบรรทัด (เหมือน _cell_lines ใน tools/taicho_pdf.py)"""
    if not value:
        return []
    return [ln for ln in str(value).split("\n") if ln.strip() != ""]


def _order_months(months):
    """ลำดับเดือนตาม tab 4 เดือนเลื่อน: 9,10,11,12 หรือ 12,1,2,3 (wrap ปี)
    — พวก HTML local เรียง sorted แล้ว Dec ตกท้ายผิดตอนข้ามปี; cloud เรียงตามปฏิทิน"""
    ms = sorted(months)
    if 12 in ms and 1 in ms and len(ms) > 1 and ms[-1] == 12:
        # มีทั้ง 12 และ 1 → เริ่มที่ 12 แล้ว wrap (12,1,2,3...)
        head = [m for m in ms if m != 12]
        return [12] + head
    return ms


def _year_of(month):
    # งวด ใช้จริง ส.ค. 26 - ก.ค. 27: 8-12 = 2026, 1-7 = 2027 (ตรง pdf_filename)
    return 2026 if month >= 8 else 2027


def _month_flow(taicho, m):
    """สร้าง flowable ของ 1 เดือน: ตาราง (title/day/data) + legend"""
    info = taicho[m]
    ndays = info.get("ndays") or 30
    cells = info.get("cells", {})
    day_w = min(26.0, (AVAIL_W - FIRST_COL_W) / ndays)
    col_w = [FIRST_COL_W] + [day_w] * ndays
    n_cols = ndays + 1
    hdr = HEADER_COLOR[30 if ndays == 30 else 31][MONTH_COLOR_IDX.get(m, 0)]
    year = _year_of(m)

    st_title = ParagraphStyle("t", fontName=FONT_NAME, fontSize=8, leading=9,
                              alignment=TA_CENTER, textColor=colors.HexColor("#000000"))
    st_day = ParagraphStyle("d", fontName=FONT_NAME, fontSize=3.5, leading=4.2,
                            alignment=TA_CENTER, textColor=colors.HexColor("#333333"))
    st_data = ParagraphStyle("dd", fontName=FONT_NAME, fontSize=4, leading=5.2,
                             alignment=TA_CENTER)
    st_first = ParagraphStyle("f", fontName=FONT_NAME, fontSize=5, leading=6,
                              alignment=TA_CENTER)

    title = Paragraph(f"{year}年 {m}月", st_title)
    row0 = [title] + [Paragraph("", st_title)] * (n_cols - 1)
    row1 = [Paragraph("", st_day)]
    for d in range(1, ndays + 1):
        row1.append(Paragraph(str(d), st_day))
    row2 = [Paragraph("千栄1568", st_first)]
    for d in range(1, ndays + 1):
        v = cells.get(d, "")
        lines = _cell_parts(v)
        if not lines:
            row2.append(Paragraph("", st_data))
        else:
            html = "<br/>".join(_line_html(ln, 5.2) for ln in lines)
            row2.append(Paragraph(html, st_data))

    tbl = Table([row0, row1, row2], colWidths=col_w, hAlign="LEFT")
    style = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(hdr)),
        ("BACKGROUND", (1, 1), (-1, 1), DAY_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("LINEBEFORE", (0, 0), (0, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
        ("ROWBACKGROUNDS", (0, 2), (-1, 2), [None, None]),
    ]
    # แถว day (row1): เส้นจาง + ตัวเลขเล็ก
    if n_cols > 1:
        style.append(("LINEABOVE", (0, 1), (-1, 1), 0.4, GRID_LIGHT))
        style.append(("LINEBELOW", (0, 1), (-1, 1), 0.4, GRID_LIGHT))
    tbl.setStyle(TableStyle(style))

    st_leg = ParagraphStyle("leg", fontName=FONT_NAME, fontSize=5, leading=6.5)
    leg = Paragraph(
        "変更は" + _line_html("🟡", 7) +
        "&nbsp;&nbsp;新規は" + _line_html("🟢", 7) +
        "&nbsp;&nbsp;経由地" + _line_html("🔷", 7), st_leg)
    return KeepTogether([tbl, Spacer(1, 2), leg, Spacer(1, 4)])


def render_taicho_pdf(taicho, mmdd, out_path):
    """สร้าง PDF 台帳 A4 landscape จาก dict taicho (เดือนทั้งหมดใน tab หลัก).
    คืน path. อ่าน sheets เองไม่ได้ — caller (main.run_flow) ส่ง taicho มาให้"""
    _ensure_font()
    months = _order_months([m for m in taicho.keys() if taicho[m].get("cells") is not None]
                           or list(taicho.keys()))
    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=MARGIN_LR, rightMargin=MARGIN_LR,
                            topMargin=MARGIN_TB, bottomMargin=MARGIN_TB,
                            title=f"{mmdd}台帳 - 千栄1568")
    story = []
    for m in months:
        story.append(_month_flow(taicho, m))
    doc.build(story)
    return out_path
