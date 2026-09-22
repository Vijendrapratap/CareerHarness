# Scout Sources Implementation Plan (Plan 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find more, fresher, better-targeted jobs: add open no-login sources (Workday, RemoteOK, Remotive, Himalayas, Arbeitnow, HN "Who is hiring"), discover the job boards of companies the candidate names, drop stale and duplicate postings, and pre-filter by the candidate's work mode and locations.

**Architecture:** `app/domain/sources.py` holds one small async fetcher per source, each returning the same normalized posting dict. `run_scout` gathers ATS boards + open sources + discovered boards concurrently (bounded by a semaphore, with retry/backoff), then applies freshness, location and duplicate filters before the existing role-title matching, fit scoring and company interleaving. Scan-now runs in the background so the request never outlives the dev proxy's ~30s timeout.

**Tech Stack:** httpx (MockTransport in tests), FastAPI BackgroundTasks, existing fit engine.

**Spec:** Plan 1 follow-on section + live probes on 2026-09-23 (all endpoints below returned data).

## Status (2026-09-23)

Implemented and verified live: one browser run produced 100 matches from 8 sources across 92 companies
(Greenhouse 17, Ashby 4, RemoteOK 5, Arbeitnow 15, HN 42, Remotive 2, Himalayas 13, Workday 2).
Target-company discovery found and cached Notion/Linear (Ashby). First scored matches arrived 16s after roles were saved.
Additions beyond the plan: board display names (OpenAI, GitLab…); Counsel finalize triggers a rescan so the
candidate's new work-mode/location facts apply (the first scan runs before those facts exist).
155 backend tests pass.

## Global Constraints

- Open, no-login, ToS-friendly sources only. No LinkedIn/Indeed/Glassdoor scraping.
- Identify politely: `User-Agent: CareerHarness/1.0 (+job scout)`; ≤ 8 concurrent requests; retry 429/5xx twice with backoff (1s, 2s).
- Normalized posting: `{"title", "company", "url", "location", "description", "portal_type", "posted_at": datetime | None}`.
- Freshness: drop postings with `posted_at` older than 30 days; keep unknown dates.
- Location pre-filter (only when facts say so): `remote_only` keeps remote postings; a `locations` list (with work_mode ≠ `any`) keeps remote postings or ones whose location mentions a listed place.
- Duplicate key: normalized `company + title` (lowercase alphanumerics); first source wins; existing tenant matches count as seen.
- Tests never hit the network.

## Sources (verified live)

| Source | Request | Notes |
|---|---|---|
| RemoteOK | `GET https://remoteok.com/api` | first element is a legal notice; `position`, `company`, `location`, `date`, `url`, `description` |
| Remotive | `GET https://remotive.com/api/remote-jobs?search={q}&limit=50` | `candidate_required_location`, `publication_date` |
| Himalayas | `GET https://himalayas.app/jobs/api/search?q={q}&limit=50` | `locationRestrictions[]`, `pubDate` epoch, `applicationLink` |
| Arbeitnow | `GET https://www.arbeitnow.com/api/job-board-api` | page 1 (250 latest), `remote` bool, `created_at` epoch |
| HN Who is hiring | Algolia: latest `author_whoishiring` "Who is hiring?" story → `GET /api/v1/items/{id}` | top-level comments; first line `Company \| Role \| Location \| …` |
| Workday | `POST https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{site}/jobs` `{searchText, limit, offset, appliedFacets}`; detail `GET …/job/{path}` | registry of employers; "Posted N Days Ago"; details only for title matches (≤ 8 per employer) |
| Company boards | probe `greenhouse /v1/boards/{slug}/jobs`, `lever /v0/postings/{slug}?mode=json&limit=1`, `ashby posting-api/job-board/{slug}` | for candidate-named target companies; results cached in facts `company_boards` |

## Tasks

### Task 1: Normalizers + fetchers (`app/domain/sources.py`, test `app/tests/test_sources.py`)
- [ ] `fetch_json(client, method, url, **kw)` with retry/backoff; returns parsed JSON or `None`.
- [ ] `remoteok(client)`, `remotive(client, query)`, `himalayas(client, query)`, `arbeitnow(client)`, `hn_who_is_hiring(client)`, `workday(client, employer, query)` → `List[posting]`; each parses dates to aware UTC datetimes.
- [ ] `WORKDAY_EMPLOYERS` registry (nvidia, salesforce, adobe, intel, workday + more verified).
- [ ] Tests: one MockTransport payload per source asserting normalized fields and `posted_at`; HN line parsing picks company/role/location; Workday "Posted 30+ Days Ago" → ~30 days; retry succeeds after one 429.

### Task 2: Filters + dedupe (`app/domain/sources.py`)
- [ ] `is_fresh(posting, now, max_age_days=30)`, `passes_location(posting, facts)`, `dedupe_key(posting)`.
- [ ] Tests for each rule, incl. unknown date kept and remote-only filtering.

### Task 3: Company board discovery
- [ ] Fact question `target_companies` ("Any companies you'd love to work at?").
- [ ] `discover_boards(client, companies) -> Dict[str, Optional[str]]` ("portal:org" or None), slug variants (`"Acme Labs"` → `acmelabs`, `acme-labs`).
- [ ] Tests with MockTransport: greenhouse hit, lever hit, miss → None.

### Task 4: Wire into `run_scout` + background scan-now
- [ ] `run_scout(..., sources=None)` gathers ATS boards, open sources (queries = up to 3 role titles), discovered boards; filters; dedupe; existing matching; returns `{"sources": n, "new_matches": n}`.
- [ ] Workday details fetched only for title-matched postings.
- [ ] `POST /api/scout/scan-now` counts the scan, then runs in the background; response `{"status": "scanning", ...}`; Jobs page polls.
- [ ] Tests: cross-source duplicate becomes one match; stale posting dropped; remote-only facts drop onsite postings; existing scout tests still pass.
