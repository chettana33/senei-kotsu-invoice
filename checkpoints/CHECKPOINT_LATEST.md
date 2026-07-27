# CHECKPOINT LATEST — SENEI KOTSU

อัปเดต: 2026-07-27 (Asia/Bangkok)

## Production Baseline

- Version: V13.3 Reports
- Branch/tag: `main` / `v13.3.0`
- Commit: `fca05bb223b2ff17e223a7979e8d5f859618c947`
- Status: Production and unchanged
- Production app SHA-256: `f2c8e7fa9ddc7d10ae256d14a9cdfe5743c8839997d49887ffc651a990417558`

## Candidate Handoff

- Version: V13.4 Outstanding/Aging Candidate
- Recorded validation: Aging 14/14; Reports regression 12/12
- Promotion: Not approved
- Exact executable in repository: No
- Checksum: Pending artifact recovery

## Completed in This Checkpoint

- Recorded the separation between V13.3 Production and V13.4 Candidate.
- Added a mandatory start path and permanent project context.
- Added the Aging acceptance specification.
- Preserved `main`, `index.html` and tag `v13.3.0`.
- Corrected `SHA256SUMS.txt` so it verifies the actual repository-root Production artifacts.

## Next Action

Recover the exact Candidate artifact from the prior ChatGPT development package. Do not recreate it from summaries and do not replace Production.
