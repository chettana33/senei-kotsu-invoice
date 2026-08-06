# SENEI KOTSU Invoice Management System

Production web application for creating invoices, rendering one-page A4 documents, tracking payments, issuing receipts, and reviewing business reports.

## Current production

- Version: **SENEI Flow V13.3 Reports**
- Production URL: https://senei-kotsu-invoice.chettana33.chatgpt.site
- Entry point: `index.html`
- Invoice renderer: `senei_kotsu_a4_renderer_v1.html`
- Receipt renderer: `senei_kotsu_receipt_renderer_v1.html`

## Development candidate

- Version: **V13.4 Outstanding/Aging Candidate**
- Status: Candidate only; not Production. Recovered exact artifact at `candidates/V13.4-aging/`
- Recorded features: customer outstanding summary, aging buckets, selectable As-of Date and Aging CSV export
- Recorded validation: Aging 14/14 and Reports regression 12/12
- Next gate: complete owner acceptance on the owner PC, then approve promotion explicitly

Start continuity work at [`START_HERE.md`](START_HERE.md). The production entry point remains V13.3 until the owner approves a later release.

## Main features

- Invoice creation, customer database and Invoice History
- Responsive one-page A4 Invoice preview and Print / Save PDF
- Deposit, Final, Partial, Full and Adjustment payments
- JPY and THB Payment Tracking
- Stable Payment Receipt numbers and one-page A4 receipts
- Read-only Reports & Payment Summary
- Invoice status, outstanding balance and monthly payment activity
- CSV report export for Excel
- Backup All / Restore All

## Data and privacy

Business data is stored in the browser's Local Storage. Repository source code does not contain live customer data. Never commit exported Backup JSON, customer data, credentials or environment files.

## Backup reminder

GitHub backs up the application source, not browser Local Storage. Use **Backup All** regularly and store the downloaded JSON securely outside this repository.
