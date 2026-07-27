# CURRENT STATE — SENEI KOTSU Invoice Management System

อัปเดต: 2026-07-27 (Asia/Bangkok)

## Production

- Version: V13.3 Reports
- Status: Production
- Branch/tag: `main` / `v13.3.0`
- Repository commit at inventory: `fca05bb223b2ff17e223a7979e8d5f859618c947`
- Production remains unchanged by this documentation checkpoint.
- `index.html` and `senei_kotsu_invoice_v13_3_reports.html` were verified byte-identical with SHA-256 `f2c8e7fa9ddc7d10ae256d14a9cdfe5743c8839997d49887ffc651a990417558`.
- `SHA256SUMS.txt` was corrected to reference and hash the actual repository-root Production artifacts rather than obsolete package-directory paths.

## Candidate

- Version: V13.4 Outstanding/Aging Candidate
- Status: Candidate / Owner acceptance pending
- Candidate executable: recorded in a prior ChatGPT session but not present in this repository
- Candidate checksum: Pending artifact recovery

## Recorded Candidate Scope

- outstanding and aging summary by customer
- selectable As-of Date
- 0–30, 31–60, 61–90 and over 90 day buckets
- Aging CSV export

## Recorded Validation

- Aging tests: 14/14 passed
- V13.3 Reports regression: 12/12 passed
- V13.3 Production was not overwritten

These results are historical handoff evidence. They must be linked to the recovered exact Candidate before promotion.

## Pending

1. Recover the exact V13.4 Candidate HTML and original checkpoint package from the prior ChatGPT artifact.
2. Calculate and record SHA-256.
3. Verify that the Candidate contains no customer data or secrets.
4. Test Reports and Outstanding Aging on the owner PC.
5. Confirm CSV output and all aging boundaries.
6. Obtain explicit owner approval before Production promotion.

## Blocker

The exact V13.4 executable is not currently available in the GitHub repository or local workspace. Do not recreate it from a textual summary.

## Next Action

Import the exact Candidate artifact into a non-production candidate path, then verify its checksum and execute the acceptance checklist.
