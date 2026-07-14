# SENEI KOTSU Invoice Management System

Production web application for creating invoices, rendering one-page A4 documents, tracking payments, and backing up local business data.

## Current production

- Version: **SENEI Flow V13.2 Payment Receipt**
- Production URL: https://senei-kotsu-invoice.chettana33.chatgpt.site
- Entry point: `index.html`
- A4 renderer: `senei_kotsu_a4_renderer_v1.html`
- Receipt renderer: `senei_kotsu_receipt_renderer_v1.html`

## Main features

- Invoice creation and customer database
- Invoice history and running invoice number
- Responsive A4 preview and Print / Save PDF
- Deposit, Final, Partial, Full, and Adjustment payments
- JPY and THB payment tracking
- Deposit amount auto-fill with editable received amount
- Stable Payment Receipt numbering and one-page A4 receipts
- Backup All / Restore All

## Data and privacy

The application stores invoices, customers, running numbers, and payments in the browser's Local Storage. Repository source code does **not** contain live customer data.

Never commit exported Backup JSON files, customer lists, invoices, payment exports, credentials, or `.env` files.

## Release workflow

- `main`: approved production source only
- Feature work: use a `feature/...` branch
- Test Payment, Backup/Restore, responsive layout, and A4 Print before merging
- Create a release tag after production acceptance

## Backup reminder

GitHub backs up the application source, not browser Local Storage. Use **Backup All** regularly and store the downloaded JSON securely outside this repository.
