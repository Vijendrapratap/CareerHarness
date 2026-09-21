# CareerHarness P2 Discovery & Batch Engine Plan

## Goal
Implement Phase 2 (Discovery): Email Connect with outreach consent (F6), automated Scout scheduling with tier-based rate limiting (F7), and the Job Dashboard with batch fan-out, concurrency caps, ghost-job flags, and crash-resilient batch execution (F8).

## Tasks
- [ ] Task 1: Add Phase 2 database models (`ConnectedEmail`, `JobListing`, `JobMatch`, `Batch`, `BatchItem`, `ScoutSchedule`) in `app/domain/models.py` → Verify: Database tables and relationships initialize cleanly.
- [ ] Task 2: Implement Email Connect service with outreach consent verification and token expiry handling (`app/domain/email_connect.py`) (`CT-03`, `RT-06`) → Verify: Unit tests for `CT-03` and `RT-06`.
- [ ] Task 3: Implement Scout Scheduler with auto-schedule on gate pass and rate-limiting (`app/domain/scout.py`) (`RD-02`, `RD-03`) → Verify: Unit tests for `RD-02` and `RD-03` (3/day Free, 10/day Pro).
- [ ] Task 4: Implement Job Catalog, Deduplication, and Analyst Legitimacy/Ghost-Job scoring (`app/domain/jobs.py`) → Verify: Job deduplication and scam/ghost-job flagging tests.
- [ ] Task 5: Implement Batch Preview Generation displaying per-job versions, channels, and risks (`app/domain/batches.py`) (`BA-04`) → Verify: Unit test for `BA-04`.
- [ ] Task 6: Implement Batch Execution Engine with per-tenant concurrency caps (tailor ×3, apply ×1) (`BA-01`) → Verify: Concurrency semaphore and fairness tests (`BA-01`).
- [ ] Task 7: Implement Isolated Child Failure handling with retry ×2 (`BA-02`) → Verify: Unit test proving child failure never kills the parent batch (`BA-02`).
- [ ] Task 8: Implement Idempotent Apply and Mid-Batch Checkpoint Recovery (`BA-03`, `RT-01`) → Verify: Crash-resume test ensuring zero double-apply submissions.
- [ ] Task 9: Implement FastAPI routers for Email Connect, Scout, Jobs, and Batches (`app/api/routers/`) with Handoff Fallback → Verify: API client integration tests.
- [ ] Task 10: Run Consolidated Phase 2 Test Contract (`RD-02/03`, `CT-03`, `RT-06`, `BA-01..04`, `RT-01`) → Verify: `pytest app/tests/` passes all P0, P1, and P2 tests with 100% green.

## Done When
- [ ] All 10 tasks completed and checked.
- [ ] Full test contract (`RD-02/03`, `CT-03`, `RT-06`, `BA-01..04`, `RT-01`) passes green in pytest.
- [ ] Batch execution strictly isolates child failures and prevents double-applies.
- [ ] Scout respects 3/day (Free) and 10/day (Pro) limits.
