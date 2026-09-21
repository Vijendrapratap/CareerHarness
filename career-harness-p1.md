# CareerHarness P1 Front-Face First Engine Plan

## Goal
Implement the core differentiator of CareerHarness: the Front-Face First Engine (F2–F5, F7). Ensure candidate resumes and LinkedIn profiles pass the 70+ Readiness Gate with zero open critical issues before any job scouting or automated applications can run.

## Tasks
- [x] Task 1: Add P1 database models (`RoleCatalog`, `RoleSelection`, `ResumeParse`, `LinkedInProfile`, `GapReport`, `TodoItem`, `ReadinessScore`, `Consent`) in `app/domain/models.py` → Verify: DB schema initializes tables and relationships.
- [x] Task 2: Implement Role Catalog & Selection service (`app/domain/roles.py`) enforcing max 3 roles without leadership flag, 4th slot unlock, and priority role persistence (`ON-01`, `ON-02`) → Verify: Unit tests for `ON-01` and `ON-02`.
- [x] Task 3: Implement Resume Parser with honesty-tagged skill list (`app/domain/resume_parser.py`) ensuring parsed skills are never auto-verified (`AT-06`, `ON-03`) → Verify: Unit tests for `AT-06` and `ON-03`.
- [x] Task 4: Implement LinkedIn Intake & Consent Tracker (`app/domain/linkedin.py`) supporting paste-as-text safe mode and URL fetch with prior consent timestamping (`LI-01`, `CT-04`) → Verify: Unit tests for `LI-01` and `CT-04`.
- [x] Task 5: Implement Gap Engine (`app/domain/gap_engine.py`) comparing resume↔role baselines and LinkedIn↔resume, emitting fix drafts that cite verified source bullets (`GE-01`, `GE-02`) → Verify: Unit tests for `GE-01` and `GE-02`.
- [x] Task 6: Implement Front-Face Scoring formula (0–100) and Critical-Dismiss Cap rule (`GE-03`) capping score at 69 on dismissed critical items → Verify: Unit tests for `GE-03`.
- [x] Task 7: Implement To-Do Action Lifecycle (Accept / Edit / Dismiss) with dynamic score recomputation and event emission (`GE-05`) → Verify: Unit tests for `GE-05`.
- [x] Task 8: Implement Readiness Gate Evaluator (`app/domain/readiness.py`) enforcing score ≥70 and 0 open criticals to unlock Scout scheduling (`RD-01`) → Verify: Unit tests for `RD-01`.
- [x] Task 9: Implement FastAPI routers for Roles, Resumes, LinkedIn, and Gaps (`app/api/routers/`) with tenant isolation → Verify: API client integration tests.
- [x] Task 10: Run Consolidated Phase 1 Test Contract (`ON-01..03`, `GE-01..05`, `LI-01`, `RD-01`, `CT-04`, `AT-06`) → Verify: `pytest app/tests/` passes all P0 and P1 test suites.

## Done When
- [x] All 10 tasks completed and checked.
- [x] Full test contract (`ON-01..03`, `GE-01..05`, `LI-01`, `RD-01`, `CT-04`, `AT-06`) passes green in pytest.
- [x] Readiness Gate strictly blocks Scout below 70 score or with open criticals.
- [x] Zero hallucinated skills in AI fix drafts.
