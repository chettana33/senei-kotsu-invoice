# SENEI KOTSU — Outstanding/Aging Report Specification V1

สถานะ: Candidate acceptance specification

## Objective

เพิ่มมุมมองยอดค้างและอายุหนี้โดยไม่แก้ไข Invoice, Payment, Receipt หรือ Production V13.3

## Required Output

- Outstanding balance grouped by customer
- Invoice-level traceability from each customer total
- User-selectable As-of Date
- Aging buckets:
  - 0–30 days
  - 31–60 days
  - 61–90 days
  - over 90 days
- Aging CSV export suitable for Excel

## Data Rules

- Aging is calculated from the selected As-of Date.
- Paid invoices must not contribute to outstanding totals.
- Partial payments reduce the outstanding amount without altering the original invoiced amount.
- Currency totals must not be silently mixed.
- Reports are read-only and must not call business-record write paths.

## Acceptance Checklist

- [ ] Exact Candidate file recovered and SHA-256 recorded
- [ ] Candidate contains no customer data, Backup JSON, credentials or secrets
- [ ] 0, 30, 31, 60, 61, 90 and 91-day boundaries verified
- [ ] Full, partial, overpaid and unpaid records verified
- [ ] Customer totals equal the sum of visible invoice outstanding amounts
- [ ] As-of Date changes all affected buckets consistently
- [ ] Aging CSV matches the on-screen filtered result
- [ ] V13.3 Reports regression rerun
- [ ] Invoice A4 renderer unchanged
- [ ] Receipt renderer unchanged
- [ ] Backup All/Restore All unchanged
- [ ] Owner acceptance recorded

## Promotion Gate

Passing automated or static checks does not make the Candidate Production. Promotion requires explicit approval from พี่เจ, a Production checkpoint, updated `index.html`, tag, release notes and rollback reference.
