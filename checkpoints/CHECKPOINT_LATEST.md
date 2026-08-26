# CHECKPOINT LATEST — SENEI KOTSU

อัปเดต: 2026-08-06 (Asia/Bangkok)

## Production Baseline

- Version: V13.3 Reports
- Branch/tag: `main` / `v13.3.0`
- Commit: `fca05bb223b2ff17e223a7979e8d5f859618c947`
- Status: Production and unchanged
- Production app SHA-256: `f2c8e7fa9ddc7d10ae256d14a9cdfe5743c8839997d49887ffc651a990417558`

## Candidate Handoff

- Version: V13.4 Outstanding/Aging Candidate
- Exact artifact recovered and imported: `candidates/V13.4-aging/` (10-file artifact package)
- Candidate executable SHA-256: `f46ffcf2481e284ff66f943ccfeeb67297308804484920c44bc2ee170277ae74`
- Candidate checksum list: `candidates/V13.4-aging/SENEI_KOTSU_V13_4_AGING_CANDIDATE/SHA256SUMS.txt` — verified all 8 files byte-identical
- Recorded validation: Aging 14/14; Reports regression 12/12
- Promotion: Not approved
- Old local folders (V11/V12/V13/V13.1/V13.2) deleted from `G:\Other computers\My Laptop (1)\เอกสาร\SENEI KOTSU\` per owner instruction; the V13.4 candidate folder was kept.

## Completed in This Checkpoint

- Recovered the exact V13.4 Candidate artifact from the local backup and imported it into the repository.
- Verified all candidate file SHA-256 checksums against the recorded sums.
- Updated `SHA256SUMS.txt` to include the Candidate artifact paths.
- Preserved `main`, `index.html` and tag `v13.3.0`.
- Recorded the removal of superseded local versions (V11–V13.2).

## Next Action

Open the Candidate (`candidates/V13.4-aging/SENEI_KOTSU_V13_4_AGING_CANDIDATE/senei_kotsu_invoice_v13_4_aging_candidate.html`) with both renderer files and complete the manual acceptance checklist. Do not deploy V13.4 or publish `v13.4.0` before explicit owner approval.
