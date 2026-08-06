# MASTER CONTEXT — SENEI KOTSU Invoice Management System

อัปเดต: 2026-07-27 (Asia/Bangkok)

## Purpose

ระบบสำหรับสร้าง Invoice, ติดตาม Payment, ออก Receipt, ดู Reports และสำรอง/กู้คืนข้อมูลการใช้งานของ SENEI KOTSU

## Architecture and Data

- Browser-based application
- Business data is stored in Browser Local Storage
- GitHub stores application source and documentation, not live business data
- Invoice and Receipt use dedicated one-page A4 renderers
- Backup All/Restore All is the user-controlled business-data backup mechanism

## Production Baseline

- Version: SENEI Flow V13.3 Reports
- Branch: `main`
- Tag: `v13.3.0`
- Entry point: `index.html`
- Named source: `senei_kotsu_invoice_v13_3_reports.html`
- Invoice renderer: `senei_kotsu_a4_renderer_v1.html`
- Receipt renderer: `senei_kotsu_receipt_renderer_v1.html`

## Candidate Line

V13.4 Outstanding/Aging Candidate was recovered from the local backup and imported into this repository at `candidates/V13.4-aging/`. Its package includes:

- outstanding balance grouped by customer
- aging buckets: 0–30, 31–60, 61–90 and over 90 days
- selectable As-of Date
- Aging CSV export
- Aging validation: 14/14 passed
- V13.3 Reports regression: 12/12 passed

Candidate executable SHA-256: `f46ffcf2481e284ff66f943ccfeeb67297308804484920c44bc2ee170277ae74` — verified against the recorded `SHA256SUMS.txt` in the package.

## Permanent Rules

- V13.3 remains Production until explicit owner approval of a later release.
- Candidate files must use distinct filenames and must not overwrite `index.html`.
- Reports and Aging views must remain read-only with respect to Invoice, Payment and Receipt business records.
- Never commit customer records, exported Backup JSON, credentials, environment secrets or Local Storage contents.
- A Production promotion requires exact source identification, checksum, regression evidence, owner acceptance, tag and release notes.
