# SENEI KOTSU Invoice Management System

Production web application for creating invoices, rendering one-page A4 documents, tracking payments, issuing receipts, and reviewing business reports.

## Current production

- Version: **SENEI Flow V13.3 Reports**
- Production URL: https://senei-kotsu-invoice.chettana33.chatgpt.site
- Entry point: `index.html`
- Invoice renderer: `senei_kotsu_a4_renderer_v1.html`
- Receipt renderer: `senei_kotsu_receipt_renderer_v1.html`

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
