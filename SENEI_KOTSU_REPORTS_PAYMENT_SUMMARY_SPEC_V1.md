# SENEI KOTSU — Reports & Payment Summary Specification V1

Date: 14 July 2026  
Base production: `v13.2.0`  
Candidate: `senei_kotsu_invoice_v13_3_reports_candidate.html`

## Goal

ให้พี่เจดูภาพรวม Invoice และ Payment จากข้อมูลจริงใน Browser โดยรายงานเป็น **read-only** และไม่แก้ไข Invoice History, Payment records, Receipt numbers หรือ Running numbers

## Included in V1

- Current total invoiced and outstanding JPY
- Received JPY and THB for a selected Payment date range
- Invoice status table: Unpaid, Deposit Paid, Partially Paid, Paid, Overpaid
- Search by Invoice No., Customer, Tour name or Tour date
- Status filter
- Monthly Payment activity by JPY and THB
- Status summary and outstanding amount
- CSV export of the filtered Invoice Status table

## Data rules

- Invoice source: `senei_invoice_history_v10`
- Payment source: `senei_payment_records_v13`
- THB is converted to JPY using the rate stored in each Invoice
- Reports create no new Local Storage key
- Reports never call `localStorage.setItem`
- Invoice A4 and Payment Receipt Renderer remain unchanged

## Acceptance checklist

1. Reports opens from the sidebar.
2. All Time totals match Payment Tracking.
3. This Month filters Payment activity correctly.
4. Status and search filters return the expected Invoices.
5. THB conversion matches the Invoice rate.
6. CSV opens correctly in Excel and contains the filtered rows.
7. Opening Reports does not change Invoice, Payment or Receipt data.
8. Invoice Print and Payment Receipt Print still work.
