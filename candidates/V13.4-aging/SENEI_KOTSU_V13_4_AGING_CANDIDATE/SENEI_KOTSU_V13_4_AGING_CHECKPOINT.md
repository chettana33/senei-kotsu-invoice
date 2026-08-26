# SENEI KOTSU — V13.4 Outstanding/Aging Candidate Checkpoint

Date: 14 July 2026  
Status: **Candidate prepared — waiting for พี่เจ review tomorrow**  
Protected production baseline: GitHub Release `v13.3.0`

## Candidate files

- `senei_kotsu_invoice_v13_4_aging_candidate.html`
- `senei_kotsu_a4_renderer_v1.html`
- `senei_kotsu_receipt_renderer_v1.html`
- `SENEI_KOTSU_AGING_REPORT_SPEC_V1.md`
- `aging_regression_test.mjs`
- `aging_regression_results.json`

## Implemented

- Read-only Outstanding Aging inside Reports
- Adjustable As-of Date
- Six buckets: Not Due, 0–30, 31–60, 61–90, 90+ and No Due Date
- Customer Outstanding aggregation
- Aging CSV export
- Explicit rule: never infer a due date from Date of Issue

## Automated verification

- V13.4 Aging regression: **14/14 passed**
- Existing V13.3 Reports regression: **12/12 passed**
- Protected Invoice/A4 script remains byte-identical to V13.3
- Existing Local Storage keys and production data behavior remain unchanged
- No deployment or GitHub Release was performed for this Candidate

## Resume point tomorrow

พี่เจ opens the Candidate with both renderer files and performs the eight manual checks in the specification. Fix only reported issues. Do not deploy V13.4 or publish GitHub `v13.4.0` before explicit acceptance.

Resume command:

`ทำ SENEI KOTSU ต่อจาก V13.4 Outstanding/Aging Candidate Checkpoint ล่าสุด`
