# SENEI KOTSU — Outstanding/Aging Report Specification V1

Date: 14 July 2026  
Protected production baseline: GitHub Release `v13.3.0`  
Candidate: `senei_kotsu_invoice_v13_4_aging_candidate.html`

## Goal

ช่วยติดตาม Invoice ที่ยังมียอดค้าง แยกตามอายุหนี้และลูกค้า โดยอ่านข้อมูลเดิมเท่านั้นและไม่แก้ไข Invoice, Payment หรือ Receipt

## Aging rules

- As-of Date ปรับได้และเริ่มต้นเป็นวันที่ปัจจุบัน
- ใช้ `Deposit Due Date` เฉพาะ Invoice ที่เปิดระบบ Deposit
- ไม่ใช้ Date of Issue เดาเป็นวันครบกำหนด
- Invoice ที่ไม่มี Due Date อยู่ในกลุ่ม `No Due Date`
- ช่วงอายุหนี้: Not Due, 0–30, 31–60, 61–90 และ 90+ วัน
- Invoice ที่ชำระครบแล้วไม่อยู่ใน Outstanding Aging

## Included

- Aging summary cards พร้อมจำนวน Invoice และยอดค้าง JPY
- Aging Invoice table
- Customer Outstanding summary
- Oldest Due Date และ Aging Risk ของลูกค้า
- ใช้ Search และ Invoice Status filter เดียวกับ Reports
- Export Aging CSV สำหรับ Excel

## Protection

- No new Local Storage key
- No `localStorage.setItem` in Aging functions
- V13.3 Reports, Backup/Restore and all V13.2 renderers remain unchanged

## Manual acceptance for tomorrow

1. Open Reports and change As-of Date.
2. Verify an Invoice with enabled Deposit Due appears in the correct bucket.
3. Verify a future Due Date shows Not Due.
4. Verify an Invoice without Due Date shows No Due Date.
5. Verify Paid Invoices are excluded.
6. Verify Customer Outstanding equals the sum of open Invoices.
7. Export Aging CSV and open it in Excel.
8. Confirm Invoice, Payment, Receipt, Reports and Backup/Restore still work.
