# START HERE — SENEI KOTSU Invoice Management System

เอกสารนี้เป็นจุดเริ่มต้นสำหรับ AI, Codex และผู้รับช่วงงาน SENEI KOTSU

## Scope Boundary

- Repository นี้ใช้เฉพาะ SENEI KOTSU Invoice Management System
- ห้ามปะปนกับ JLOS, KIMONO Land Operation หรือ Ichinotour Quotation
- Pha Tiao Core: `chettana33/phathiao-work-system`

## Read Order

1. Pha Tiao Core `START_HERE.md`
2. Project `START_HERE.md`
3. `MASTER_CONTEXT.md`
4. `CURRENT_STATE.md`
5. `checkpoints/CHECKPOINT_LATEST.md`
6. Active specification and affected source files
7. `README.md` and `SHA256SUMS.txt`

## Current Handoff

- Production: V13.3 Reports
- Production branch/tag: `main` / `v13.3.0`
- Candidate: V13.4 Outstanding/Aging
- Candidate source status: imported into this repository at `candidates/V13.4-aging/`
- Candidate promotion status: not approved

## Start Rule

1. Verify that `main`, tag `v13.3.0`, `index.html` and the V13.3 named file remain the Production baseline.
2. Never reconstruct a Candidate executable from chat summaries.
3. Use the recovered V13.4 artifact in `candidates/V13.4-aging/` for product testing or code review.
4. Do not commit customer data, Local Storage exports, Backup JSON, passwords, tokens or secrets.
5. Promotion to Production requires owner acceptance and a separate release checkpoint.
