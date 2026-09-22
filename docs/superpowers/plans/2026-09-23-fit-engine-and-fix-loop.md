# Fit Engine, Candidate Facts & Fix Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score every scouted job against its real job description and the candidate's confirmed facts, turn gaps into one-click profile/resume fixes whose impact is visible ("confirm Docker → 9 more jobs clear the apply line"), and only allow applying to jobs at or above 4.0/5.

**Architecture:** A pure, deterministic fit engine (`app/domain/fit.py`) evaluates `(job, candidate snapshot) → FitReport`: hard gates first (location/remote, sponsorship, blacklist, deal-breakers, seniority), then a requirement table extracted from the JD (skill + importance + evidence), then weighted dimension scores combined in code. Reports are persisted per tenant+job and recomputed whenever the candidate's facts or skills change. The counsellor collects structured candidate facts one question at a time. The apply step refuses jobs below the line.

**Tech Stack:** FastAPI, SQLAlchemy async (SQLite dev / Postgres prod), pytest-asyncio, Next.js 14 client pages, Tailwind.

**Spec:** Research synthesis in the session (career-ops two-stage evaluation + requirement table with evidence tiers; AI-Job-Search hard gates before scoring, arithmetic in code; ApplyPilot structured apply profile). Product decisions from the user: open job sources only; browser auto-fill + approve for apply (Plan 3); score honestly and gate apply at 4.0/5.

## Status (2026-09-23)

Plan 1 implemented: Tasks 1–8 done, 145 backend tests passing, verified end to end in the browser.
Changes from the plan, found on real job descriptions:
- JD sections are classified (requirements / nice-to-have / responsibilities / company-benefits); company and benefits text yields no requirements.
- A skill with no requirement wording counts as preferred, not high.
- Years are read only in "N years … experience" context, and a range uses its lower bound ("2–12+ years" = 2).
- Thin evidence (few requirements) pulls the skill score toward neutral, so one missing skill can't sink a job.
- Added a resume-skill checklist after upload (`POST /api/fit/fixes/confirm-skills`), and "Biggest wins" puts skills already in the resume first.
- `job_fits` migration: `alembic/versions/d91f3a6c2e40_job_fits.py`.
Next: Plan 2 (scout sources), then Plan 3 (browser auto-fill + approve).

## Global Constraints

- Apply line: **4.0 / 5**. Verdicts: `apply` ≥ 4.0, `stretch` 3.5–3.99, `skip` < 3.5. A failed hard gate caps the score at **2.0** with verdict `skip`.
- `JobMatch.match_score` stays on the existing 0–10 scale (= fit score × 2) because trusted mode compares it to 9.0.
- Never invent candidate facts. A skill counts as *verified* only after the candidate confirms it; "In resume but unconfirmed" is shown as a partial match.
- Deterministic scoring only in this plan (no LLM calls in the score path), so fixes can be simulated instantly for the impact numbers.
- New tables only (no new columns on existing tables): `init_db`'s `create_all` creates new tables in dev without a migration.
- Tests must not touch the network or the real `career_harness.db` (conftest already disables the background scout).

---

## File Structure

| File | Responsibility |
|---|---|
| `app/domain/skills.py` (new) | Canonical skill vocabulary + aliases; `find_skills(text)` |
| `app/domain/resume_parser.py` | Use `find_skills`; add `verify_skill(session, tenant_id, skill)` (moved from gap_engine) |
| `app/domain/candidate_facts.py` (new) | Fact questions, get/update facts, next question, completeness |
| `app/domain/fit.py` (new) | Pure fit engine: JD cleaning, requirement extraction, gates, scoring, fixes |
| `app/domain/fit_service.py` (new) | DB glue: candidate snapshot, persist `JobFit`, re-evaluate tenant, fix impact |
| `app/domain/models.py` | `JobFit` table |
| `app/api/routers/fit.py` (new) | `/api/profile/facts`, `/api/fit/fixes`, `/api/fit/fixes/confirm-skill`, `/api/fit/fixes/decline-skill` |
| `app/api/routers/jobs.py` | `/api/jobs` includes fit report |
| `app/domain/scout.py` | Evaluate new matches after a scan |
| `app/domain/apply_choice.py` | Refuse below the apply line (`FitGateError`) |
| `frontend/app/jobs/page.tsx` | Fit card, gates, fixes, apply gate, "Top fixes" panel |
| `frontend/app/counsel/page.tsx` | Guided fact questions replace the preferences panel |

---

### Task 1: Skill vocabulary

**Files:** Create `app/domain/skills.py`; modify `app/domain/resume_parser.py`; test `app/tests/test_fit_engine.py`.

**Interfaces — Produces:** `SKILLS: dict[str, list[str]]` (canonical → aliases); `find_skills(text: str) -> list[str]` (canonical names, in vocabulary order, word-boundary matched, case-insensitive).

- [ ] Test: `find_skills("5+ yrs Postgres, k8s and node")` → contains `PostgreSQL`, `Kubernetes`, `Node.js`; `find_skills("reactive java")` does not contain `React`; `find_skills("C++ and Go (golang)")` contains `C++`, `Go`.
- [ ] Implement `SKILLS` (~120 entries across languages, frameworks, data, cloud, devops, AI/ML, practices, product/management) and `find_skills` using a precompiled regex per skill with `(?<![\w+#.])alias(?![\w+#])` boundaries.
- [ ] `resume_parser.extract_skills_unverified` uses `find_skills`; keep `KNOWN_SKILLS = list(SKILLS)` for existing imports.
- [ ] Run `pytest app/tests -q` → all green.

### Task 2: Candidate facts

**Files:** Create `app/domain/candidate_facts.py`; test `app/tests/test_candidate_facts.py`.

**Interfaces — Produces:**
- `FACT_QUESTIONS: list[dict]` each `{id, prompt, kind: "choice"|"multi"|"text"|"number"|"list", options?: list[str]}` for ids: `years_experience`, `seniority`, `work_mode`, `locations`, `needs_sponsorship`, `salary_min`, `notice_weeks`, `deal_breakers`, `blacklist_companies`.
- `async get_facts(session, tenant_id) -> dict` (stored in `ProfileSection` step `"facts"`).
- `async update_facts(session, tenant_id, patch: dict) -> dict` — validates ids/types, merges, returns facts.
- `next_question(facts) -> dict | None`; `completeness(facts) -> tuple[int, int]` (answered, total).

- [ ] Tests: empty facts → first question is `years_experience`; patch `{years_experience: 6}` → next is `seniority`; unknown id raises `ValueError`; `needs_sponsorship` must be bool; lists are de-duplicated and trimmed; completeness counts.
- [ ] Implement.

### Task 3: Fit engine (pure)

**Files:** Create `app/domain/fit.py`; test `app/tests/test_fit_engine.py`.

**Interfaces — Produces:**
```python
@dataclass
class CandidateSnapshot:
    role_titles: list[str]          # priority first
    verified_skills: set[str]       # canonical names
    resume_skills: set[str]         # found in resume text, unverified
    declined_skills: set[str]       # candidate said "I don't have this"
    facts: dict                     # candidate_facts

@dataclass
class Requirement:
    skill: str
    importance: str   # "critical" | "high" | "preferred"
    match: str        # "verified" | "unconfirmed" | "gap"

@dataclass
class FitReport:
    score: float                   # 1.0–5.0, 1 decimal
    verdict: str                   # apply | stretch | skip
    dimensions: dict[str, float]   # skills, experience, role, logistics (1–5)
    requirements: list[Requirement]
    gates: list[str]               # failed hard-gate reasons (empty = passed)
    strengths: list[str]           # ≤3
    gaps: list[str]                # ≤3
    fixes: list[dict]              # {kind: "confirm_skill", skill, gain}  (gain = score delta if fixed)

def clean_jd(html_or_text: str) -> str
def extract_requirements(title: str, jd: str) -> list[tuple[str, str]]   # (skill, importance)
def required_years(jd: str) -> int | None
def evaluate(title: str, company: str, location: str, jd: str, cand: CandidateSnapshot) -> FitReport
APPLY_LINE = 4.0
```

Scoring rules (all in code):
- Importance: skill in the title → `critical`; in a sentence/bullet containing required/must/you have/experience with/proficien → `high`; in one containing nice to have/preferred/bonus/plus → `preferred`; otherwise `high`. Max 12 requirements, critical first.
- Match weights: verified 1.0, unconfirmed 0.5, gap 0; importance weights critical 3, high 2, preferred 1. `skills = 1 + 4 × weighted_match_ratio` (no requirements found → 3.0).
- Experience: JD years vs `facts.years_experience`: meets → 5; short by 1 → 4; by 2 → 3; more → 2; unknown either side → 3.5.
- Role: best overlap between job-title words and any role title (seniority words ignored): full → 5, ≥50% → 4, any → 3, none → 2.
- Logistics: remote job or `work_mode` any → 5; `remote_only` candidate + onsite job → gate; location listed in `facts.locations` → 5; unknown → 3.5.
- Overall = 0.45 skills + 0.20 experience + 0.20 role + 0.15 logistics, rounded to 1 decimal.
- Hard gates (cap 2.0, verdict skip): company in `blacklist_companies`; any `deal_breakers` phrase in the JD; `needs_sponsorship` and JD says no sponsorship/must be authorized/citizens only; `remote_only` and JD is onsite-only; JD requires ≥ candidate years + 4.
- Fixes: for each `unconfirmed` or `gap` requirement not in `declined_skills`, `gain` = score recomputed with that skill verified − current score; keep gain > 0, sorted desc, ≤5.

- [ ] Tests (one per rule): requirement importance from title/required/preferred; verified vs unconfirmed vs gap scoring order; each hard gate caps at 2.0 with a reason; experience bands; role overlap; fix gain > 0 and applying it raises the score; `clean_jd` strips tags and unescapes `&lt;p&gt;`.
- [ ] Implement.

### Task 4: Persist fits and wire into scout and jobs API

**Files:** Modify `app/domain/models.py` (`JobFit`), create `app/domain/fit_service.py`, modify `app/domain/scout.py`, `app/api/routers/jobs.py`; test `app/tests/test_fit_service.py`.

**Interfaces — Produces:**
- `JobFit(id, tenant_id, job_id, score, verdict, report JSON, updated_at)`; unique `(tenant_id, job_id)`.
- `async candidate_snapshot(session, tenant_id) -> CandidateSnapshot`
- `async evaluate_tenant(session, tenant_id, job_ids: list[str] | None = None) -> int` — upserts `JobFit`, sets `JobMatch.match_score = score*2`, `why_matched` = first strength or gap.
- `async get_fit(session, tenant_id, job_id) -> JobFit | None`

- [ ] Tests: evaluating a job that needs Docker (unverified) gives `stretch`/`skip`; after `verify_skill(..., "Docker")` + `evaluate_tenant` the score rises and `match_score` updates; `/api/jobs` rows include `fit.score`, `fit.verdict`, `fit.fixes`.
- [ ] `run_scout` calls `evaluate_tenant(session, tenant_id, new_job_ids)` before its final flush.

### Task 5: Fix loop API + facts API

**Files:** Create `app/api/routers/fit.py`, register in `app/api/main.py`; move `_verify_skill` from gap_engine to `resume_parser.verify_skill`; add `decline_skill` (stored in facts `declined_skills`); test `app/tests/test_fit_api.py`.

**Interfaces — Produces:**
- `GET /api/profile/facts` → `{facts, next_question, answered, total}`; `PATCH /api/profile/facts` body = partial facts → same shape, then re-evaluates tenant.
- `GET /api/fit/fixes` → `[{skill, jobs_unlocked, jobs_improved, avg_gain}]` — for each candidate skill fix across all fits: how many jobs would cross the apply line if confirmed. Sorted by `jobs_unlocked`, then `jobs_improved`.
- `POST /api/fit/fixes/confirm-skill {skill}` → verifies, re-evaluates, returns `{unlocked: int, apply_ready: int}`.
- `POST /api/fit/fixes/decline-skill {skill}` → records honest gap, re-evaluates.

- [ ] Tests for each endpoint incl. that confirm increases `apply_ready` count and decline removes the skill from fixes.

### Task 6: Apply gate

**Files:** Modify `app/domain/apply_choice.py`, `app/api/routers/applications.py`; test in `app/tests/test_fit_api.py`.

- [ ] `prepare_application` raises `FitGateError(score, reasons)` when the job's `JobFit.score < APPLY_LINE` (or no fit exists → evaluate first). Router maps to 403 `{detail: "Fit 3.4/5 is below the 4.0 apply line. Fix: confirm Docker (+0.6)"}`.
- [ ] Update existing `/choose` tests that use jobs without fits: give them a passing fit via `evaluate_tenant` on data that clears the line, or seed `JobFit` directly.

### Task 7: Frontend — jobs fit cards + top fixes

**Files:** Modify `frontend/app/jobs/page.tsx`.

- [ ] Card: score `x.x/5` + verdict badge (apply = teal, stretch = rope, skip = granite), gates in a red line, strengths/gaps lists, requirement chips (verified ✓ / unconfirmed ? / gap ✕), "Fix to unlock" chips: *I have X* (confirm) / *Not yet* (decline).
- [ ] Apply buttons disabled below 4.0 with the reason.
- [ ] Top panel "Biggest wins": `/api/fit/fixes` top 3 — "Confirm Docker → unlocks 9 jobs".
- [ ] Filter tabs: Ready to apply · Stretch · Skipped.

### Task 8: Frontend — counsellor collects facts

**Files:** Modify `frontend/app/counsel/page.tsx`.

- [ ] Replace the Search Preferences panel with a "Counsellor question" card driven by `GET /api/profile/facts` (`next_question`), rendering chips/inputs per `kind`, a progress meter (answered/total), and "Skip" (moves on without saving). Answers `PATCH` facts.
- [ ] Chat `detected_attributes` map onto facts (`management`→`seniority` hint, `location`→`locations`, `authorization`→`needs_sponsorship`).

---

## Follow-on plans (to be expanded when started)

- **Plan 2 — Scout sources:** Workday CXS JSON API (employer registry), RemoteOK, Remotive, Himalayas, Arbeitnow, HN "Who is hiring"; company-name → ATS auto-discovery (probe Greenhouse/Lever/Ashby slugs); layered dedupe (canonical URL, company+title, JD SimHash); `posted_at` + max age; per-source backoff; title exclude list and location accept patterns from candidate facts.
- **Plan 3 — Browser auto-fill + approve:** Playwright worker per application; per-ATS form adapters (Greenhouse, Lever, Ashby first); fills fields from candidate facts + tailored resume; screenshots + field list sent to the candidate; submit only after explicit approval; result codes (submitted / needs_login / captcha / blocked / expired) split permanent vs retryable; NEVER list (payments, IDs/biometrics, SSO-only); per-day cap.
