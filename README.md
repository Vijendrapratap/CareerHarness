# CareerHarness

> **Standalone AI Career Agent Platform**  
> *BYOK Economics • Front-Face First Readiness • DeepSeek-Adapted Thin Harness • Multi-Tier ATS Fallback Ladder*

[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14.2%20App%20Router-black.svg)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/tests-79%20passing-brightgreen.svg)]()
[![Code Quality](https://img.shields.io/badge/linter-ruff%20clean-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-purple.svg)]()

---

## 🌟 Overview & Core Principles

**CareerHarness** is an autonomous AI career platform designed to discover, tailor, submit, and track high-conviction job applications at scale while upholding strict candidate data isolation, factual honesty, and carrier bot resilience.

### Architectural Invariants:
1. **BYOK Key Economics (Bring-Your-Own-Key):**
   - Candidates supply their own LLM API credentials (OpenRouter, OpenAI, Anthropic, Gemini, DeepSeek).
   - Keys are envelope-encrypted with **AES-256-GCM** using per-tenant **HKDF-SHA256** derived Data Encryption Keys (DEKs).
   - Decryption occurs strictly in-memory per task execution; keys are masked everywhere in logs and UI.
   - Upstream `402 Payment Required` or `429 Rate Limit` errors mark keys as `no_credits` and park tenant runs fail-closed with **zero platform key fallback**.
2. **Strict Identity & Authentication (Zero Social Login):**
   - Identity is strictly Email/Password with **Argon2id (RFC 9106)** password hashing.
   - Session tokens delivered in cryptographically signed, `HttpOnly`, `SameSite=Lax`, `Secure` cookies and Bearer tokens.
   - Passwordless recovery supported via cryptographically random one-time magic links.
3. **Front-Face First Spine (Readiness Gate):**
   - Automated discovery (Scout) and application execution remain **strictly locked** until the candidate's Front-Face score reaches $\ge 70$ with **zero open critical items**.
   - Dismissing a critical to-do permanently caps the candidate's score at 69 until resolved.
4. **DeepSeek Harness Core (5-Stage Loop & Capability Seams):**
   - Strict `Plan → Act → Observe → Reflect → Checkpoint` execution cycle.
   - **Reflect-on-Tool-Result:** Evaluates every observation against domain honesty invariants. If hallucination or empty output occurs, reflection injects `system_correction` before the next step.
   - **Capability Seams:** Pluggable ATS providers (Greenhouse, Lever, Ashby) with automated 3-tier fallback ladder.
   - **Guarded Tool Execution Pipeline:** Fail-closed tenant isolation and pre/post interceptors.
5. **Modern Next.js 14 App Router Monorepo:**
   - Unified developer experience with FastAPI backend alongside modern Next.js 14 App Router frontend under `frontend/` with 6 dedicated views: **Today**, **Pipeline**, **Documents**, **Outreach**, **Insights**, and **Settings**.

---

## 🔄 End-to-End Pipeline & Flow

The lifecycle of an application in CareerHarness follows an orchestrated 5-phase progression:

```mermaid
flowchart TD
    %% Phase 1
    subgraph P1 ["Phase 1: Candidate Onboarding & Front-Face Gate"]
        Start([Candidate Onboarding]) --> F1[1. Ingest Master Resume & LinkedIn Profile]
        F1 --> F2[2. Select 3-4 Target Roles from Role Catalog]
        F2 --> F3[3. Gap Engine: 2-Way Audit & Metric Verification]
        F3 --> F4[4. Calculate Front-Face Readiness Score (0-100)]
        
        F4 --> GateCheck{Readiness Gate\nScore >= 70 AND\n0 Critical Todos?}
        GateCheck -- NO --> Blocked[Scout & Apply Locked\nDisplay Actionable Fixes\nDismissing critical caps score at 69]
        Blocked -->|Candidate Resolves Todos| F3
        GateCheck -- YES --> Unlocked[Readiness Gate Cleared]
    end

    %% Phase 2
    subgraph P2 ["Phase 2: Discovery & Batch Planning"]
        Unlocked --> F5[5. Auto-Schedule Scout Scan\nDaily Free / Hourly Pro]
        F5 --> F6[6. Ingest & Deduplicate Job Listings\nGhost-Job Heuristics Filter]
        F6 --> F7[7. Analyst Agent Match Scoring (0-10)]
        F7 --> F8[8. Formulate Batch Group & Interactive Preview\nLineage Diff, ATS Channels & Risk Preview]

        F8 --> ApprovalGate{Human Gate or\nTrusted Mode?}
        ApprovalGate -- Reject --> BatchCancelled[Batch Item Dismissed]
        ApprovalGate -- Approve --> ExecuteBatch[Batch Fan-Out Execution\nMax Concurrency: 3 Tailor, 1 Apply]
    end

    %% Phase 3
    subgraph P3 ["Phase 3: 5-Stage Application Pipeline"]
        ExecuteBatch --> S1[Stage 1: Resume Tailoring\nStrict factual constraint of master]
        S1 --> S2[Stage 2: Adversarial Reviewer Sub-Agent\nHonesty Audit against master facts]
        S2 -->|Hallucination Detected| Regenerate[Regenerate Draft with Penalties] --> S1
        S2 -->|Honesty Verified| S3[Stage 3: Tailored Cover Letter]
        S3 --> S4[Stage 4: ATS Scan & Format Validation\nSingle-column, standard headings, parse test]
        S4 --> S5[Stage 5: Screening Questions Answering\nStrictly from candidate-verified facts]
    end

    %% Phase 4
    subgraph FallbackLadder ["Phase 4: 3-Tier ATS Bot Mitigation Fallback Ladder"]
        S5 --> T1{Tier 1: Automated ATS\nPlaywright stealth autofill}
        T1 -- Success --> Done[Status: Applied via Portal]
        T1 -- Bot Shield / CAPTCHA / 403 --> T2{Tier 2: Connected Mailbox\nCompany direct email found?}
        T2 -- Found & Consent OK --> EmailSent[Status: Applied via Direct Mailbox]
        T2 -- None / Bounce --> T3[Tier 3: 1-Click Candidate Handoff Bundle\nPre-filled web forms + tailored PDF + checklist]
    end

    %% Phase 5
    subgraph P4 ["Phase 5: Vault Lineage & Post-Submission Loops"]
        Done --> Lineage[Create Immutable DocumentVersion\nUpdate ApplicationAuditLog & Lineage Tree]
        EmailSent --> Lineage
        T3 --> Lineage
        
        Lineage --> Track[Track Status: applied]
        Track --> Silence{Silence > 10 Days?}
        Silence -- Yes --> Ghosted[Mark Status: ghosted]
        
        Track --> Inbound[Sync Connected Mailbox for Inbound Replies]
        Inbound --> Classify{AI Reply Classification}
        Classify -- Interview --> StatusInterview[Status: interview\nIncrement DocumentVersion Score]
        Classify -- Assessment --> StatusAssessment[Status: assessment]
        Classify -- Rejection --> StatusRejection[Status: rejected]
        Classify -- Request Info --> StatusInfo[Status: request_info]

        Track --> Outreach[Hiring Manager Outreach Drafting]
        Outreach --> OutreachCap{Daily Send <= 15\nAND Outreach Consent?}
        OutreachCap -- Allowed --> SendOutreach[Email Sent via Mailbox]
        OutreachCap -- Exceeded --> OutAbort[Paused with 429 Rate Limit]

        StatusInterview --> Analytics[Funnel & Conversion Analytics\nGrouped by Portal, Role & Document Version]
    end
```

---

## 🏛️ System Architecture

```
CareerHarness/
├── app/
│   ├── api/                     # FastAPI presentation layer
│   │   ├── main.py              # Application entry point & security headers
│   │   ├── deps.py              # DB & fail-closed tenant injection
│   │   └── routers/             # 14 domain router modules
│   │       ├── applications.py  # 5-stage application pipeline
│   │       ├── batches.py       # Batch grouping & preview
│   │       ├── gaps.py          # Gap Engine & to-do resolver
│   │       ├── health.py        # Service health check
│   │       ├── insights.py      # Funnel analytics & settings
│   │       ├── jobs.py          # Job catalog & match ranking
│   │       ├── keys.py          # BYOK key management
│   │       ├── linkedin.py      # Profile paste & consent
│   │       ├── resumes.py       # Resume intake & skill extraction
│   │       ├── roles.py         # Role catalog & selection
│   │       ├── runs.py          # Agent harness runs
│   │       ├── scout.py         # Scout scheduler
│   │       ├── tenants.py       # Tenant registration & demo tenant
│   │       ├── tracker.py       # Status lifecycle & inbound emails
│   │       └── vault.py         # Version lineage & outcomes
│   ├── core/                    # Security, encryption & core infrastructure
│   │   ├── config.py            # Pydantic v2 settings
│   │   ├── database.py          # AsyncSession & RLS parameter binding
│   │   ├── keyvault.py          # AES-256-GCM + HKDF BYOK Key Vault
│   │   ├── model_router.py      # OpenRouter (DeepSeek Flash v4.1) router
│   │   ├── outbox.py            # Transactional outbox pattern
│   │   └── security.py          # Cryptographic primitives
│   ├── domain/                  # Business domain engines
│   │   ├── application_engine.py# 5-stage pipeline & adversarial reviewer
│   │   ├── batches.py           # Concurrency-controlled batch executor
│   │   ├── email_connect.py     # Mailbox OAuth & token encryption
│   │   ├── gap_engine.py        # Two-way gap audit & readiness score
│   │   ├── insights.py          # Funnel metrics & trusted mode gate
│   │   ├── jobs.py              # Ghost-job scoring & deduplication
│   │   ├── linkedin.py          # LinkedIn intake & timestamp consent
│   │   ├── memory.py            # Agent context blackboard
│   │   ├── models.py            # SQLAlchemy Declarative Models
│   │   ├── readiness.py         # Readiness Gate service
│   │   ├── resume_parser.py     # Honesty skill parsing (AT-06)
│   │   ├── roles.py             # Role catalog management
│   │   ├── scout.py             # Scout scheduler & rate limits
│   │   ├── tracker.py           # Inbound email classifier & outreach
│   │   └── vault.py             # Immutable DocumentVersion DAG
│   ├── harness/                 # Thin Agent Harness (DeepSeek-adapted)
│   │   ├── checkpointer.py      # Postgres session snapshots
│   │   ├── gate.py              # HITL approval gates
│   │   ├── loop.py              # AgentLoop state machine
│   │   ├── pipeline.py          # Guarded tool execution interceptors
│   │   ├── projections.py       # SessionEvent pure projection streams
│   │   ├── registry.py          # Tool registry & tenant checks
│   │   ├── seams.py             # Capability seams (ATS providers & ladder)
│   │   └── teams.py             # Agent teams, TaskBoard & Mailbox
│   └── templates/
│       └── dashboard.html       # Interactive Single-Page Control Center
├── scripts/
│   └── test_walkthrough.py      # Automated 8-phase end-to-end CLI tester
├── CODE_KNOWLEDGE_GRAPH.md      # Graphify Architecture & JSON-LD Schema
└── pyproject.toml               # Poetry / pip configuration
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.12+
- SQLite (default for development/testing) or PostgreSQL 15+ (production)
- Git

### 2. Installation
```bash
# Clone repository
git clone https://github.com/Vijendrapratap/CareerHarness.git
cd CareerHarness

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Launch the Server
```bash
# Run FastAPI server on port 8000 with auto-reload
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testing & Verification

### Option A: Interactive Web Console (Zero Setup)
Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.
- Click **"▶ Run Full Flow"** to execute all 8 phases end-to-end and watch live streaming API results.
- Test BYOK Key Vault encryption, Front-Face readiness, Scout discovery, 5-stage application pipeline, and ATS fallback simulation.

### Option B: Automated CLI Walkthrough
Run the end-to-end Python walkthrough script:
```bash
python scripts/test_walkthrough.py
```
This script exercises all 8 phases against the live server:
1. Health check & demo tenant context
2. BYOK key vault storage (OpenRouter DeepSeek Flash v4.1)
3. Role selection, resume intake, skill extraction, gap engine, and readiness score
4. Job ingestion & Scout match scoring
5. Batch formulation & pre-approval preview
6. 5-stage application pipeline with 3-tier ATS fallback ladder
7. Application tracking & inbound recruiter email classification
8. Funnel analytics & Trusted Mode settings

### Option C: Pytest Test Suite
```bash
# Run all 60 unit and integration tests
pytest -v

# Run linter
ruff check app
```

---

## 🔑 Model Router & OpenRouter Configuration

CareerHarness uses a multi-provider LLM abstraction that routes tasks based on computational tier to the candidate's decrypted BYOK key:

| Tier | Default OpenRouter Model | Use Cases |
|---|---|---|
| **`cheap`** | `deepseek/deepseek-chat-v4.1` | Resume parsing, keyword matching, screening question answering |
| **`mid`** | `deepseek/deepseek-chat-v4.1` | Resume tailoring, cover letter writing, match scoring |
| **`frontier`** | `deepseek/deepseek-r1` | Adversarial hallucination review, complex strategy, gap analysis |

```python
# Save an OpenRouter key via API
POST /api/keys
Headers: { "X-Tenant-ID": "<tenant-id>" }
Body: {
  "provider": "openrouter",
  "api_key": "sk-or-v1-..."
}
```

---

## 📖 Complete API Reference

| Router | Prefix | Key Endpoints | Purpose |
|---|---|---|---|
| **Health** | `/health` | `GET /health` | Service liveness & environment status |
| **Auth** | `/api/auth` | `POST /signup`, `POST /login`, `POST /magic-link` | Argon2id email/password auth, HttpOnly cookies & magic link recovery |
| **Dashboard**| `/` | `GET /` | Interactive single-page test console |
| **Tenants** | `/api/tenants` | `POST /`, `GET /demo`, `GET /{id}` | Multi-tenant onboarding & demo sandbox |
| **Keys** | `/api/keys` | `POST /`, `GET /`, `DELETE /{id}` | BYOK Key Vault with AES-256-GCM envelope encryption |
| **Roles** | `/api/roles` | `GET /catalog`, `POST /`, `GET /` | Role catalog & candidate target role slots |
| **Resumes** | `/api/resumes` | `POST /upload`, `POST /{id}/skills/{s}/confirm` | Resume parser with honest skill tagging (AT-06) |
| **LinkedIn**| `/api/linkedin` | `POST /paste`, `POST /consent` | Profile intake & explicit consent timestamp |
| **Gaps** | `/api/gaps` | `POST /compute`, `GET /readiness` | Two-way gap audit & Front-Face Readiness Gate (F7) |
| **Todos** | `/api/todos` | `GET /`, `POST /{id}/action` | Actionable fix cards (accept, edit, dismiss) |
| **Scout** | `/api/scout` | `POST /scan-now`, `POST /auto-schedule`| Autonomous & on-demand job discovery |
| **Jobs** | `/api/jobs` | `POST /ingest`, `GET /` | Deduplication, ghost-job scoring & match ranking |
| **Batches** | `/api/batches` | `POST /`, `GET /{id}/preview`, `POST /{id}/approve` | Batch application groups with safety preview |
| **Vault** | `/api/vault` | `POST /master`, `GET /lineage`, `POST /promote` | Immutable document versions & conversion lineage |
| **Applications** | `/api/applications` | `POST /tailor`, `POST /ats-check`, `POST /submit` | 5-stage pipeline with 3-tier ATS fallback ladder |
| **Tracker** | `/api/tracker` | `POST /track`, `POST /inbound-email`, `POST /{id}/outreach` | Status lifecycle, email classification & HM outreach |
| **Insights** | `/api/insights` | `GET /funnel`, `POST /trusted-mode`, `PATCH /cadence` | Conversion metrics & settings management |

For the complete machine-readable knowledge graph and JSON-LD schema, refer to [`CODE_KNOWLEDGE_GRAPH.md`](CODE_KNOWLEDGE_GRAPH.md).

---

## 🔒 Security & Privacy

- **Zero Plaintext at Rest:** All provider keys are encrypted using AES-256-GCM.
- **Fail-Closed Isolation:** Every request verifies `X-Tenant-ID`. Database queries enforce tenant scoping and Postgres Row-Level Security (RLS).
- **Zero Log Leakage:** Key masking filters (`sk-...1234`) prevent sensitive tokens from appearing in console, transcript, or log outputs.
- **Hardened HTTP Headers:** `nosniff`, `DENY` framing, `Strict-Transport-Security`, and customized Content Security Policies prevent XSS and clickjacking.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.