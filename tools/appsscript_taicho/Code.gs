/**
 * king-bus-taicho — Google Apps Script Web App (1 ก.ย. 69)
 * 台帳 4 เดือน (rotate จาก main tab) → HTML สำหรับ print (emoji 🟡🟢🔷 ติดในเบราว์เซอร์)
 * Port จาก tools/taicho_pdf.py render_html() — ต้องแก้ 2 ที่ให้ตรงกัน.
 *
 * Deploy: Web App, executeAs=USER_DEPLOYING, access=ANYONE_ANONYMOUS
 * LINE ส่งลิงก์ web app แทนไฟล์ PDF (พี่เจขอ 1 ก.ย. 69).
 */
var SHEET_ID = "1H2WE2D8ZXrAI4jdOUm2N6DYGCWVD1SrYy9BqAfRFdC0";  // master จริง
var MONTH_START = 9;   // เดือนแรกของรอบ (rotate รายเดือน)
var MONTH_COUNT = 4;
var YEAR = 2026;

// สีหัวเดือน 30/31 วัน (lessons #51; ตรง -Jay): 30 = โทนเย็น, 31 = โทนอุ่น
var HEADER_COLOR = {
  30: ["#c7e3ff", "#eaf8ea"],   // ฟ้า, เขียว
  31: ["#ffe5ea", "#fff2e7", "#ffe3c9"],  // ชมพู, ส้ม, เหลืองอ่อน
};
// เดือน -> ดัชนีสี (สลับให้ 2 เดือนติดกันไม่ซ้ำ)
var MONTH_COLOR_IDX = {9: 0, 10: 0, 11: 1, 12: 1};
var DAYS_IN_MONTH = {1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31};

/** Web App entry: คืน HTML 台帳 ปัจจุบัน (อ่านสดจาก Sheets ทุกครั้งที่เปิด). */
function doGet() {
  var taicho = readTaicho();
  var html = renderHtml(taicho);
  // SandboxMode.NATIVE: ไม่มี iframe sandbox → window.print() ทำงานบนมือถือด้วย
  // (IFRAME mode = sandbox ไม่มี allow-modals → print โดน ignore — 1 ก.ย. 69)
  return HtmlService.createHtmlOutput(html)
      .setTitle("台帳 - 千栄1568")
      .setSandboxMode(HtmlService.SandboxMode.NATIVE)
      .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

/** หา tab 台帳 หลัก: '千栄1568 <M0>月-<M3>月(<ปี>)' — เลือก M0 (เดือนแรก) มากสุด. */
function findMainTab() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sheets = ss.getSheets();
  var best = null;
  for (var i = 0; i < sheets.length; i++) {
    var t = sheets[i].getName();
    var m = t.match(/^千栄1568 (\d+)月-\d+月/);
    if (m) {
      var m0 = parseInt(m[1], 10);
      if (best === null || m0 > best.m0) best = {m0: m0, name: t};
    }
  }
  if (best === null) throw new Error("ไม่พบ tab 台帳 หลัก (千栄1568 <M>月-<M>月)");
  return best.name;
}

/** อ่านตาราง: {month: {cells: {day: value}, ndays}} — layout เดียวกับ read_taicho() ใน Python. */
function readTaicho() {
  var name = findMainTab();
  var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(name);
  var rows = sheet.getRange(1, 1, 80, 33).getDisplayValues();  // A1:AG80 (display text — time cells เป็น "07:00" ไม่ใช่ Date)
  // month sections: แถวที่มี 'N月' ในคอลัมน์ A → entry แถว = header + 3
  var sections = {};
  for (var i = 0; i < rows.length; i++) {
    var a = rows[i][0];
    if (a && typeof a === "string") {
      var m = a.match(/(\d+)月/);
      if (m) sections[parseInt(m[1], 10)] = i + 4;  // 1-based entry row
    }
  }
  var taicho = {};
  for (var month in sections) {
    month = parseInt(month, 10);
    var idx = sections[month] - 1;  // 0-based
    var entry = rows[idx] || [];
    var cells = {};
    for (var day = 1; day <= 31; day++) {
      var v = entry[day];  // col B(1)..AF(31) → index = day
      if (v !== null && v !== undefined && String(v) !== "") cells[day] = String(v);
    }
    var ndays = DAYS_IN_MONTH[month] || 30;
    var hidx = idx - 3;  // header แถว (0-based)
    if (hidx >= 0) {
      var hdr = rows[hidx] || [];
      var nums = [];
      for (var j = 1; j < hdr.length; j++) {
        var n = parseInt(hdr[j], 10);
        if (!isNaN(n) && n >= 1 && n <= 31) nums.push(n);
      }
      if (nums.length) ndays = Math.max.apply(null, nums);
    }
    taicho[month] = {cells: cells, ndays: ndays};
  }
  return taicho;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** escape + ระบาย D2: 空=ฟ้า(#1f61d9) ホ=ส้ม(#de6b0f) — พี่เจอนุมัติ 5 ก.ย. 69. */
function escapeHtmlD2(s) {
  var out = [];
  var str = String(s);
  for (var i = 0; i < str.length; i++) {
    var ch = str.charAt(i);
    if (ch === "\u7a7a") { // 空
      out.push('<span class="d2-air">空</span>');
    } else if (ch === "\u30db") { // ホ
      out.push('<span class="d2-hotel">ホ</span>');
    } else {
      out.push(escapeHtml(ch));
    }
  }
  return out.join("");
}

/** ค่าเซลล์ → บรรทัด (ตัด \n + ลบบรรทัดว่าง). */
function cellLines(value) {
  if (!value) return [];
  var lines = [];
  var parts = String(value).split("\n");
  for (var i = 0; i < parts.length; i++) {
    if (parts[i].trim() !== "") lines.push(parts[i]);
  }
  return lines;
}

/** สร้าง HTML 台帳 4 เดือน — port จาก render_html() ใน taicho_pdf.py. */
function renderHtml(taicho) {
  var months = [];
  var keys = Object.keys(taicho).map(Number).sort(function (a, b) { return a - b; });
  for (var k = 0; k < keys.length; k++) {
    if (keys[k] >= MONTH_START && keys[k] < MONTH_START + MONTH_COUNT) months.push(keys[k]);
  }
  if (!months.length) months = keys.slice(0, MONTH_COUNT);  // rotate ข้ามปี (12-03)

  var p = [];
  p.push('<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">');
  p.push('<title>台帳 - 千栄1568</title><style>');
  p.push('@page { size: A4 landscape; margin: 7mm 6mm; }');
  p.push('* { margin: 0; padding: 0; box-sizing: border-box; }');
  p.push('body { font-family: "MS PGothic", "Yu Gothic", sans-serif; }');
  p.push('.print-btn { position: fixed; top: 6px; right: 6px; z-index: 9;');
  p.push('  padding: 8px 16px; font-size: 14px; border: none; border-radius: 6px;');
  p.push('  background: #1a73e8; color: #fff; cursor: pointer; }');
  // แจ้งหมุนจอแนวนอน: แสดงเฉพาะมือถือ portrait — ซ่อนตอน print
  p.push('.rotate-hint { display: none; position: fixed; top: 6px; left: 6px; z-index: 9;');
  p.push('  padding: 6px 10px; font-size: 11px; border-radius: 6px; background: #fff3cd;');
  p.push('  color: #856404; border: 1px solid #ffeeba; }');
  p.push('@media (orientation: portrait) and (pointer: coarse) {');
  p.push('  .rotate-hint { display: block; } }');
  p.push('.month { margin-bottom: 6pt; page-break-inside: avoid; }');
  p.push('table { border-collapse: collapse; width: auto; table-layout: fixed; }');
  p.push('.title-row td { font-weight: bold; font-size: 8pt; text-align: center;');
  p.push('  padding: 1pt 0; border: 0.5pt solid #888; background: var(--hdr); }');
  p.push('.day-row td { border: 0.5pt solid #bbb; text-align: center; font-size: 3.5pt;');
  p.push('  background: #fafafa; color: #333; padding: 0.5pt 0; white-space: nowrap;');
  p.push('  vertical-align: middle; }');
  p.push('.day-row td:first-child, .data-row td:first-child { width: 22pt; min-width: 22pt;');
  p.push('  border-right: 1pt solid #888; }');
  p.push('.day-row td:not(:first-child), .data-row td:not(:first-child) { width: 26pt; }');
  p.push('.data-row td { border: 0.5pt solid #888; height: auto; min-height: 20pt;');
  p.push('  vertical-align: middle; text-align: center; font-size: 4pt; font-weight: bold;');
  p.push('  padding: 1pt 0.5pt; white-space: nowrap; overflow: visible; line-height: 1.3; }');
  p.push('.data-row td:first-child { font-size: 5pt; white-space: normal; text-align: center;');
  p.push('  padding-left: 0; vertical-align: middle; }');
  p.push('.d2-air { color: #1f61d9; } .d2-hotel { color: #de6b0f; }');
  p.push('.legend { margin-top: 2pt; font-size: 5pt; font-weight: bold; display: flex; gap: 10pt; }');
  p.push('.legend .dot { margin-right: 3pt; }');
  p.push('@media print { .print-btn { display: none; } .rotate-hint { display: none !important; } }');
  // มือถือ (touch device): ซ่อนปุ่ม print ทุกทิศทาง (ใช้เมนูเบราว์เซอร์ print แทน — พี่เจขอ 1 ก.ย. 69)
  // pointer:coarse = แตะจอ (มือถือ/แท็บเล็ต) — กัน landscape width>768px โผล่กลับ
  p.push('@media (hover: none) and (pointer: coarse) { .print-btn { display: none; } }');
  p.push('</style></head><body>');
  p.push('<button class="print-btn" onclick="window.print()">印刷 / Print</button>');
  p.push('<div class="rotate-hint">横向きにしてご覧ください（印刷は横向き推奨）</div>');

  for (var i = 0; i < months.length; i++) {
    var m = months[i];
    var ndays = taicho[m].ndays;
    var cells = taicho[m].cells;
    var hdr = HEADER_COLOR[ndays === 30 ? 30 : 31][MONTH_COLOR_IDX[m] || 0];
    p.push('<div class="month"><table>');
    p.push('<tr class="title-row"><td colspan="' + (ndays + 1) + '" style="--hdr:' + hdr + '">' +
           YEAR + '年 ' + m + '月</td></tr>');
    var daysHtml = "";
    for (var d = 1; d <= ndays; d++) daysHtml += "<td>" + d + "</td>";
    p.push('<tr class="day-row"><td></td>' + daysHtml + '</tr>');
    var dataCells = [];
    for (var d2 = 1; d2 <= ndays; d2++) {
      var lines = cellLines(cells[d2]);
      if (!lines.length) dataCells.push("<td></td>");
      else {
        var inner = [];
        for (var li = 0; li < lines.length; li++) inner.push(escapeHtmlD2(lines[li]));
        dataCells.push("<td>" + inner.join("<br>") + "</td>");
      }
    }
    p.push('<tr class="data-row"><td>千栄1568</td>' + dataCells.join("") + '</tr>');
    p.push('</table>');
    p.push('</div>');
  }
  // legend ชุดเดียวท้ายตาราง (พี่เจสั่ง 5 ก.ย. 69)
  p.push('<div class="legend" style="display:block">' +
         '<span><span class="dot">🟡</span>変更は</span>' +
         '<span style="margin-left:14pt"><span class="dot">🟢</span>新規は</span></div>');
  p.push('<div class="legend" style="display:block;margin-top:4pt">' +
         '<span class="d2-hotel">ホ</span>=ホテル（橙）　' +
         '<span class="d2-air">空</span>=空港（青）　左=出発　右=行先<br/>' +
         '<span class="d2-hotel">ホ</span> 09:00 1H <span class="d2-air">空</span> ＝ ホテルから空港（1H 経由）</div>');
  p.push('</body></html>');
  return p.join("");
}
