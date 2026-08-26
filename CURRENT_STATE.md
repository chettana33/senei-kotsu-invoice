# CURRENT STATE — SENEI KOTSU Invoice Management System

อัปเดต: 2026-08-06 (Asia/Bangkok)

## Production

- Version: V13.3 Reports
- Status: Production
- Branch/tag: `main` / `v13.3.0`
- Repository commit at inventory: `fca05bb223b2ff17e223a7979e8d5f859618c947`
- Production remains unchanged by this checkpoint.
- `index.html` and `senei_kotsu_invoice_v13_3_reports.html` were verified byte-identical with SHA-256 `f2c8e7fa9ddc7d10ae256d14a9cdfe5743c8839997d49887ffc651a990417558`.
- `SHA256SUMS.txt` was corrected to reference and hash the actual repository-root Production artifacts.

## Candidate

- Version: V13.4 Outstanding/Aging Candidate
- Status: Candidate / Owner acceptance pending
- Candidate executable: **recovered and imported** at `candidates/V13.4-aging/SENEI_KOTSU_V13_4_AGING_CANDIDATE/senei_kotsu_invoice_v13_4_aging_candidate.html`
- Candidate checksum: SHA-256 `f46ffcf2481e284ff66f943ccfeeb67297308804484920c44bc2ee170277ae74` (all 8 package files verified against `SHA256SUMS.txt` inside the package)

## Recorded Candidate Scope

- outstanding and aging summary by customer
- selectable As-of Date
- 0–30, 31–60, 61–90 and over 90 day buckets
- Aging CSV export

## Recorded Validation

- Aging tests: 14/14 passed
- V13.3 Reports regression: 12/12 passed
- V13.3 Production was not overwritten

These results are recorded in the recovered package (`aging_regression_results.json`, `reports_regression_results.json`) and must be re-verified on the owner PC against the recovered artifact before promotion.

## Pending

1. Open the recovered Candidate with both renderer files on the owner PC.
2. Test Reports and Outstanding Aging on the owner PC.
3. Confirm CSV output and all aging boundaries (0/30/31/60/61/90/91 days).
4. Confirm candidate contains no customer data or secrets.
5. Obtain explicit owner approval before Production promotion.
6. Production promotion requires a separate release checkpoint, updated `index.html`, tag and rollback reference.

## Completed

- Exact V13.4 executable recovered from local backup and imported into the repository.
- SHA-256 recorded for all candidate files in `SHA256SUMS.txt`.
- Superseded local versions (V11/V12/V13/V13.1/V13.2) removed from the local SENEI KOTSU folder per owner instruction. The V13.4 candidate folder was kept.

## Next Action

Execute the acceptance checklist in `SENEI_KOTSU_AGING_REPORT_SPEC_V1.md` against the recovered Candidate artifact.
