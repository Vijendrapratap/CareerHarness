# CareerHarness Master Build Manifesto: Step-by-Step Execution Plan

> **Scope:** Clean-slate rebuild & deep upgrade strictly following the Master Build Manifesto.  
> **Key Tenets:** Zero stubs in production • No social login (Email/Password + Argon2id + Sessions) • DeepSeek Loop (`Plan -> Act -> Observe -> Reflect -> Checkpoint`) • Capability Seams • Dual-Engine Docker & local development • Next.js 14 App Router in `frontend/`.

---

## 1. Execution Roadmap

```mermaid
flowchart TD
    P0["Phase 0: Foundation & Real Infrastructure\n- docker-compose.yml (Postgres 16, Redis, MinIO, Mailhog)\n- Alembic RLS migrations (set_tenant_id)\n- Users & Argon2id Auth (/auth/signup, /auth/login, /auth/magic-link)"]
    P1["Phase 1: BYOK Vault & DeepSeek Harness Core\n- Real AES-256-GCM + HKDF DEK Vault\n- Real httpx ModelRouter (401/402/429 handling, usage parsing)\n- AgentLoop: Plan -> Act -> Observe -> Reflect -> Checkpoint"]
    P2["Phase 2: Front-Face Engine & Consulting Agent\n- Profiler Consulting Agent with reflection loop\n- Real PDF parser (pypdf) + LinkedIn Seam\n- Gap Engine & Strict Code-Level Readiness Gate"]
    P3["Phase 3: Discovery, Scout & Batches\n- Public ATS APIs (Greenhouse/Ashby/Lever) + Aggregators\n- Analyst Match Scoring (0-10) & Ghost-Job Filter\n- Batch Engine with Redis Semaphore Concurrency"]
    P4["Phase 4: 5-Stage Pipeline & ATS Fallback Ladder\n- Tailor & Reviewer (Adversarial Hallucination Check)\n- Real ReportLab ATS PDF generation\n- 3-Tier ATS Ladder (Playwright Stealth -> SMTP Mailbox -> Handoff)"]
    P5["Phase 5: Tracker, Outreach & Next.js UI\n- IMAP/Graph sync & Interview Reminders (T-24h, T-1h)\n- Outreach Agent with 15/day rate limit\n- Next.js 14 App Router in frontend/ (6 Views)"]

    P0 --> P1 --> P2 --> P3 --> P4 --> P5
```

---

## 2. Phase-by-Phase Implementation Contract

### Phase 0: Foundation & Real Infrastructure
- [ ] `docker-compose.yml`: PostgreSQL 16 + pgvector/pg_cron, Redis 7, MinIO, Mailhog.
- [ ] Dependencies: Add `passlib[argon2]`, `argon2-cffi`, `python-jose`, `python-multipart`, `alembic`, `pypdf`, `reportlab`, `vcrpy`.
- [ ] Alembic setup: `alembic/` with PostgreSQL RLS functions (`set_tenant_id`) and migrations for all tables.
- [ ] Models: Add `User` (id, email, password_hash, tenant_id, is_active).
- [ ] Auth Service & Security: Argon2id password hashing, signed session cookie / JWT token generation.
- [ ] API Routers: `/api/auth/signup`, `/api/auth/login`, `/api/auth/magic-link`, `/api/auth/me`.
- [ ] RLS Middleware: Ensure `SET LOCAL app.current_tenant_id` is executed per request.
- [ ] Test Suite: IT-02 isolation and authentication tests.

### Phase 1: BYOK Vault & DeepSeek Harness Core
- [ ] BYOK Key Vault: AES-256-GCM with per-tenant HKDF DEK derivation. Zero plaintext leakage.
- [ ] Model Router: Real `httpx` client implementation for OpenAI, Anthropic, Gemini, OpenRouter (DeepSeek Flash v4.1).
- [ ] Quota & Key Exhaustion: Intercept 401, 402, 429, update key status, raise `KeyExhaustedError`, pause run without platform fallback.
- [ ] DeepSeek Loop (`app/harness/loop.py`):
  - `Plan`: Build prompts from scoped blackboard context.
  - `Act`: Invoke LLM with tool definitions.
  - `Observe`: Execute tool implementations via Capability Seams.
  - `Reflect`: Agent reviews its own observations/outputs against constraints. If correction is needed, injects feedback.
  - `Checkpoint`: Postgres session snapshot.
- [ ] Test Suite: KY-04 (key failure & run pause) and Harness loop reflection tests.

### Phase 2: Front-Face Engine & Consulting Agent
- [ ] Profiler Consulting Agent: DeepSeek loop with tools (`ask_user`, `extract_story`, `update_blackboard`).
- [ ] Real Resume Parser: `pypdf` text extraction + structured LLM extraction.
- [ ] LinkedIn Seam: Public profile HTML / Proxycurl / BrightData interface with consent.
- [ ] Gap Engine: Compare resume/LinkedIn vs target roles.
- [ ] Readiness Gate: Hard code-level lock of Scout and applications if score < 70 or open criticals > 0.
- [ ] Test Suite: GE-01..05, RD-01 gate lockouts.

### Phase 3: Discovery, Scout & Batches
- [ ] Scout Seam: Public Greenhouse, Lever, Ashby JSON APIs + jobspy aggregator interface.
- [ ] Celery Beat: Scheduled discovery scans.
- [ ] Analyst Agent: 0-10 match score + ghost-job risk heuristics.
- [ ] Batch Engine: Fan-out child runs with Redis semaphore concurrency (max 3 concurrent Tailor agents).
- [ ] Test Suite: Batch idempotency and concurrency tests.

### Phase 4: 5-Stage Application Pipeline
- [ ] Tailor Agent: Strict factual constraint to master resume facts.
- [ ] Reviewer Agent: Adversarial hallucination check (AT-02).
- [ ] PDF Generator: Real ATS-parseable single-column PDF using `reportlab`.
- [ ] ATS Fallback Ladder:
  - Tier 1: Playwright stealth autofill.
  - Tier 2: Connected mailbox direct email apply (Hunter/Apollo).
  - Tier 3: 1-click candidate handoff bundle.
- [ ] Test Suite: AT-01..05, AT-07, and RT-01 crash resume idempotency.

### Phase 5: Tracker, Outreach & Next.js 14 Frontend
- [ ] Mailbox Sync: IMAP / Graph API background syncing.
- [ ] Inbound Classifier: Categorize interview, assessment, rejection.
- [ ] Reminders: Interview reminders at T-24h and T-1h.
- [ ] Outreach Agent: Story-bank email generator with 15/day cap and gate approval.
- [ ] Next.js 14 Frontend (`frontend/`):
  1. Today (Conversational feed)
  2. Pipeline (Kanban board)
  3. Documents (Version Vault tree)
  4. Outreach (Gate Outbox)
  5. Insights (Funnel analytics)
  6. Settings (BYOK keys, OAuth, Trusted Mode)
