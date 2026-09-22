# Candidate Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn CareerHarness into a light neumorphic candidate product whose first screen is login, then a counsellor interview, a fix list, a connected mailbox, a job board, a chosen apply path, recruiter email, and a calendar of interviews.

**Architecture:** Keep the existing FastAPI modular app, OpenRouter harness, readiness gate, scout, drafter-reviewer packet, and tracker. Add one `CandidateJourney` stage per tenant and route the Next.js app by that stage. New agent behavior is a new tool on the existing roster, not a new service. Job discovery stays on the public Greenhouse, Lever, and Ashby scout. Browser automation stays the existing Playwright apply seam in `app/harness/seams.py`. Recruiter email is sent only to an address already printed on the job posting, through the mailbox the candidate connected, after they approve the packet.

**Tech Stack:** Next.js 14 App Router, Tailwind 3, FastAPI, SQLAlchemy async, Alembic, pytest, the existing OpenRouter model router, Web Speech API in the browser.

**Spec:** This file. The journey and the global constraints below are the spec. Executors implement the tasks in order and do not reopen the product decisions in those sections.

## Global Constraints

- Git author for every commit in this repo: `git config user.name "Vijendrapratap"` and `git config user.email "44225657+Vijendrapratap@users.noreply.github.com"`.
- Auth stays email and password with Argon2id. No social login. Session cookie name remains `session_token`.
- Agents call the candidate's OpenRouter key. No platform model key fallback.
- A tailored resume may not add a company, date, metric, or skill that is absent from the master resume. `review_tailored_honesty` stays the enforcing gate.
- Scout and recruiter send stay locked while `ReadinessGateService.evaluate_readiness` returns `is_ready` false (score under 70 or any open critical todo).
- Do not scrape LinkedIn people, guess personal emails, or buy address lists. A recruiter address is valid only when it is a literal email in `JobListing.description` or `JobListing.url` text already stored on the row.
- Do not store microphone audio. The browser transcribes speech and posts the transcript as text with `input_mode` of `mic` or `text`.
- Mail sending goes through `email_service.send_outreach_email`. That function already requires outreach consent and the 15-per-day cap. Do not add a second SMTP client.
- The dashboard dev server for this repo is `http://127.0.0.1:3010`. Port 3000 is another project. The API is `http://127.0.0.1:8000`.
- Python tests: `/home/pratap/work/CareerHarness/.venv/bin/python -m pytest`.
- Frontend check after UI edits: `cd frontend && npx tsc --noEmit`.
- Visual theme is light neumorphism. Page wash `#e7edf4`. Ink `#243044`. Accent `#3d6b8c`. Raised shadow `6px 6px 14px #c5ced8, -6px -6px 14px #ffffff`. Inset shadow `inset 4px 4px 8px #c5ced8, inset -4px -4px 8px #ffffff`. No dark slate backgrounds, no purple.

---

## Refined journey

The candidate moves through one stage. The UI shows only the stage they are in, plus Settings.

| Stage | What the candidate sees | What unlocks the next stage |
|---|---|---|
| `counsel` | Career counsellor asks eight questions. Answers may be typed or spoken. | LinkedIn, resume, and all eight answers are saved. |
| `todos` | Checklist from the gap engine for the roles they chose. | Readiness gate is ready: score at least 70 and zero open critical todos. |
| `mailbox` | Connect the mailbox the agent may send from, then record outreach consent. | `email_service` has a mailbox and a consent row. |
| `hunt` | Scout lists matching jobs. Each job offers "Use my resume" or "Refine for this job". | The candidate submits at least one application. |
| `active` | Applications, recruiter threads, and the interview calendar. Hunt stays available. | Stage does not move backward. |

Counsellor questions, in order:

1. `linkedin` — "Paste your LinkedIn URL or the About and Experience text."
2. `resume` — "Upload your resume PDF."
3. `target_work` — "What kind of work do you want next?" The server calls `roles_service.suggest_roles` and shows at most three roles, or four when they say they have managed people.
4. `priority_role` — "Which of these is the priority role?"
5. `management` — "Have you managed people or a program?"
6. `location` — "Where do you want to work, and is remote acceptable?"
7. `authorization` — "Are you authorized to work in the country you are targeting, and do you need sponsorship?"
8. `preferences` — "What do you want more of, and what do you want to avoid?"

Profile sections written from those answers: `identity`, `target_roles`, `resume`, `linkedin`, `preferences`, `stories`.

Apply choice:

- `original` — submit the master resume version. Still draft a cover letter from the master facts. Do not rewrite bullets.
- `refine` — call `draft_application_packet`. Show the honest draft and the cover letter. The candidate confirms before submit.

Recruiter hunter runs after a successful apply. If the posting contains an email, draft one message with the resume version and cover letter attached as text, status `pending_approval`. If it does not, record `no_public_email` and leave the application on the portal path. The candidate presses Send. Trusted mode may send only when the existing harness rule already allows it: trusted mode on, match score at least 9, and under the daily cap.

Interview reminders: when an inbound email is classified `interview` and a datetime is present, create an `InterviewEvent`. A reminder is due at 24 hours before and at 1 hour before. The reminder is an `OutreachMessage` to the candidate's own account email with status `sent` once the worker has emitted it. Tests use a fixed clock and do not send real mail.

---

## File map

| File | Responsibility |
|---|---|
| `frontend/app/globals.css` | Neumorphic tokens and `neo-raised`, `neo-inset`, `neo-pressed` classes. |
| `frontend/app/layout.tsx` | Light document shell. Remove `className="dark"`. |
| `frontend/tailwind.config.js` | Light color tokens. |
| `frontend/lib/api.ts` | `api(path, init)` that sends `credentials: "include"` and JSON. |
| `frontend/lib/speech.ts` | `listenOnce(): Promise<string>` wrapping `webkitSpeechRecognition`. |
| `frontend/app/login/page.tsx` | Login form. |
| `frontend/app/register/page.tsx` | Registration form. |
| `frontend/app/counsel/page.tsx` | One question at a time, text or mic. |
| `frontend/app/todos/page.tsx` | Gap to-do list. |
| `frontend/app/mailbox/page.tsx` | Mailbox connect and consent. |
| `frontend/app/jobs/page.tsx` | Scout results and the two apply actions. |
| `frontend/app/applications/page.tsx` | Tracked applications. |
| `frontend/app/inbox/page.tsx` | Recruiter threads. |
| `frontend/app/calendar/page.tsx` | Interview events. |
| `frontend/components/Shell.tsx` | Light nav. Replaces the dark `Navbar` usage on journey pages. |
| `app/domain/journey.py` | Stage storage and the transition rules. |
| `app/domain/counsel.py` | The eight-step counsellor and profile sections. |
| `app/domain/apply_choice.py` | `original` versus `refine`. |
| `app/domain/recruiter_hunter.py` | Public-email extraction and the pending outreach draft. |
| `app/domain/calendar.py` | Interview events and reminder selection. |
| `app/api/routers/journey.py` | `GET /api/journey`. |
| `app/api/routers/counsel.py` | `GET /api/counsel` and `POST /api/counsel/answer`. |
| `app/mcp/tools.py` | Tool definitions the agents call. Handlers delegate to existing services. |
| `alembic/versions/b7e1c2a9d4f0_candidate_journey.py` | `candidate_journeys`, `profile_sections`, `interview_events`. |

Existing code the tasks must call, not reimplement:

- `POST /api/auth/signup` and `POST /api/auth/login` in `app/api/routers/auth.py`. Body fields are `email`, `password`, `name` on signup.
- `roles_service.suggest_roles(background: str, mgmt_experience: bool) -> list[dict]` in `app/domain/roles.py`.
- `roles_service.select_roles(session, tenant_id, role_ids, mgmt_experience, priority_role_id)`.
- `gap_engine.compute_gaps(session, tenant_id)` and `GET /api/todos`.
- `readiness_gate.evaluate_readiness(session, tenant_id)`.
- `email_service.connect_mailbox`, `grant_outreach_consent`, `send_outreach_email`.
- `scout_scheduler.trigger_manual_scan(session, tenant_id)`. The live route is `POST /api/scout/scan-now`, not `/api/scout/manual-scan`.
- `draft_application_packet(...)` in `app/domain/application_engine.py`.
- `AGENT_ROSTER` in `app/harness/roster.py`.

---

### Task 1: Light neumorphic shell

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/tailwind.config.js`
- Create: `frontend/components/Shell.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: none.
- Produces: CSS classes `neo-raised`, `neo-inset`, `neo-pressed`. `Shell` props `{ title: string; children: React.ReactNode }`.

- [x] **Step 1: Replace the dark tokens**

Replace the contents of `frontend/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --wash: #e7edf4;
  --ink: #243044;
  --muted: #5c6b7d;
  --accent: #3d6b8c;
  --shadow-dark: #c5ced8;
  --shadow-light: #ffffff;
}

body {
  background: var(--wash);
  color: var(--ink);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
  margin: 0;
  min-height: 100vh;
}

.neo-raised {
  background: var(--wash);
  border-radius: 18px;
  box-shadow: 6px 6px 14px var(--shadow-dark), -6px -6px 14px var(--shadow-light);
}

.neo-inset {
  background: var(--wash);
  border-radius: 14px;
  box-shadow: inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light);
}

.neo-pressed {
  background: var(--wash);
  color: var(--accent);
  border-radius: 14px;
  box-shadow: inset 3px 3px 7px var(--shadow-dark), inset -3px -3px 7px var(--shadow-light);
}
```

In `frontend/tailwind.config.js`, set `darkMode` to `"class"` and replace the color block with:

```js
colors: {
  wash: "#e7edf4",
  ink: "#243044",
  muted: "#5c6b7d",
  accent: "#3d6b8c",
},
```

In `frontend/app/layout.tsx`, change the html and body to:

```tsx
<html lang="en">
  <body className="bg-wash text-ink min-h-screen">{children}</body>
</html>
```

- [x] **Step 2: Add the shell**

Create `frontend/components/Shell.tsx`:

```tsx
import Link from "next/link";

const links = [
  ["Counsel", "/counsel"],
  ["To-dos", "/todos"],
  ["Mailbox", "/mailbox"],
  ["Jobs", "/jobs"],
  ["Applications", "/applications"],
  ["Inbox", "/inbox"],
  ["Calendar", "/calendar"],
  ["Settings", "/settings"],
];

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="neo-raised mb-6 flex items-center justify-between px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted">CareerHarness</p>
          <h1 className="text-xl font-semibold">{title}</h1>
        </div>
        <nav className="flex flex-wrap gap-2">
          {links.map(([label, href]) => (
            <Link key={href} href={href} className="neo-raised px-3 py-2 text-sm">
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
```

Point `frontend/app/page.tsx` at login instead of the dark dashboard:

```tsx
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/login");
}
```

- [x] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0. Existing view components may still mention dark classes. That is allowed until later tasks stop importing them from `page.tsx`. If `Shell` fails because `React` is not in scope, add `import React from "react"`.

- [x] **Step 4: Commit**

```bash
git add frontend/app/globals.css frontend/app/layout.tsx frontend/tailwind.config.js frontend/components/Shell.tsx frontend/app/page.tsx
git commit -m "feat: switch the shell to a light neumorphic theme"
```

---

### Task 2: Login and registration

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/register/page.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/login` body `{ email, password }`. `POST /api/auth/signup` body `{ email, password, name }`. Both set `session_token`.
- Produces: `api<T>(path: string, init?: RequestInit): Promise<T>`. After a 200 login or signup, the page navigates to `/counsel`.

- [x] **Step 1: Write the API helper**

Create `frontend/lib/api.ts`:

```ts
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data as T;
}
```

- [x] **Step 2: Write the two pages**

`frontend/app/login/page.tsx` is a client component. One `neo-raised` card, email input, password input, both `neo-inset`, and a submit button `neo-pressed`. On submit:

```ts
await api("/api/auth/login", {
  method: "POST",
  body: JSON.stringify({ email, password }),
});
window.location.assign("/counsel");
```

Show `error.message` under the button. Link to `/register`.

`frontend/app/register/page.tsx` adds a name field and posts:

```ts
await api("/api/auth/signup", {
  method: "POST",
  body: JSON.stringify({ email, password, name }),
});
window.location.assign("/counsel");
```

Password input `minLength={8}`. Link back to `/login`.

- [x] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [x] **Step 4: Commit**

```bash
git add frontend/lib/api.ts frontend/app/login/page.tsx frontend/app/register/page.tsx
git commit -m "feat: add light login and registration screens"
```

---

### Task 3: Journey stage

**Files:**
- Create: `app/domain/journey.py`
- Create: `app/api/routers/journey.py`
- Modify: `app/api/main.py` to `include_router` the journey router
- Modify: `app/domain/models.py` to add `CandidateJourney`
- Create: `alembic/versions/b7e1c2a9d4f0_candidate_journey.py`
- Test: `app/tests/test_journey.py`

**Interfaces:**
- Consumes: `AsyncSession`, `tenant_id: str`.
- Produces:

```python
Stage = Literal["counsel", "todos", "mailbox", "hunt", "active"]

async def get_or_create_journey(session: AsyncSession, tenant_id: str) -> CandidateJourney: ...
async def set_stage(session: AsyncSession, tenant_id: str, stage: Stage) -> CandidateJourney: ...
```

`GET /api/journey` returns `{ "stage": "counsel" }` for a tenant with no row yet. A later stage never writes an earlier stage. `set_stage(..., "counsel")` while the row is `todos` raises `JourneyRegressionError`.

- [x] **Step 1: Write the failing test**

Create `app/tests/test_journey.py`:

```python
import pytest

from app.domain.journey import JourneyRegressionError, get_or_create_journey, set_stage


@pytest.mark.asyncio
async def test_new_tenant_starts_in_counsel(db_session, sample_tenant):
    journey = await get_or_create_journey(db_session, sample_tenant.id)
    assert journey.stage == "counsel"


@pytest.mark.asyncio
async def test_stage_does_not_move_backward(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")
    with pytest.raises(JourneyRegressionError):
        await set_stage(db_session, sample_tenant.id, "counsel")
```

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py -q`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `app.domain.journey`.

- [x] **Step 3: Implement the model, service, migration, and route**

Add this model next to `User` in `app/domain/models.py`:

```python
class CandidateJourney(Base):
    __tablename__ = "candidate_journeys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="counsel")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
```

`app/domain/journey.py`:

```python
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import CandidateJourney

Stage = Literal["counsel", "todos", "mailbox", "hunt", "active"]
_ORDER = ("counsel", "todos", "mailbox", "hunt", "active")


class JourneyRegressionError(Exception):
    pass


async def get_or_create_journey(session: AsyncSession, tenant_id: str) -> CandidateJourney:
    row = (
        await session.execute(select(CandidateJourney).where(CandidateJourney.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row:
        return row
    row = CandidateJourney(tenant_id=tenant_id, stage="counsel")
    session.add(row)
    await session.flush()
    return row


async def set_stage(session: AsyncSession, tenant_id: str, stage: Stage) -> CandidateJourney:
    row = await get_or_create_journey(session, tenant_id)
    if _ORDER.index(stage) < _ORDER.index(row.stage):
        raise JourneyRegressionError(f"Cannot move from {row.stage} back to {stage}.")
    row.stage = stage
    await session.flush()
    return row
```

Alembic revision `b7e1c2a9d4f0`, `down_revision = "27889c9aff99"`, creates `candidate_journeys` with those columns and a unique index on `tenant_id`.

`GET /api/journey` uses `get_tenant_id` and returns `{ "stage": journey.stage }`. Register the router in `app/api/main.py`.

SQLite tests create tables from `Base.metadata.create_all` in `app/tests/conftest.py`, so the new model is picked up without running Alembic in pytest. Still add the migration for Postgres.

- [x] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/domain/models.py app/domain/journey.py app/api/routers/journey.py app/api/main.py alembic/versions/b7e1c2a9d4f0_candidate_journey.py app/tests/test_journey.py
git commit -m "feat: store the candidate journey stage"
```

---

### Task 4: Counsellor interview and profile sections

**Files:**
- Create: `app/domain/counsel.py`
- Create: `app/api/routers/counsel.py`
- Modify: `app/domain/models.py` with `ProfileSection`
- Modify: `app/harness/roster.py` to add agent name `counsellor`
- Modify: `alembic/versions/b7e1c2a9d4f0_candidate_journey.py` and add `profile_sections` to that same `upgrade()`. Task 3 created the file and it has not been applied.
- Create: `frontend/lib/speech.ts`
- Create: `frontend/app/counsel/page.tsx`
- Test: `app/tests/test_counsel.py`

**Interfaces:**
- Consumes: `roles_service.suggest_roles`, `roles_service.select_roles`, `set_stage`.
- Produces:

```python
COUNSEL_STEPS = (
    "linkedin", "resume", "target_work", "priority_role",
    "management", "location", "authorization", "preferences",
)

async def record_answer(
    session: AsyncSession,
    tenant_id: str,
    step: str,
    text: str,
    input_mode: Literal["text", "mic"],
) -> dict:
    """Returns {"step": next_or_same, "prompt": str, "choices": list, "done": bool}."""
```

`POST /api/counsel/answer` body `{ "step": str, "text": str, "input_mode": "text" | "mic" }`.
`GET /api/counsel` returns the current prompt for the first step that has no `ProfileSection`.

Section map:

| Step | Section key | Stored value |
|---|---|---|
| `linkedin` | `linkedin` | the raw text |
| `resume` | `resume` | the raw text, or the parsed resume id when the client uploads a PDF first |
| `target_work` | `target_roles` | `{ "background": text, "suggestions": [role ids] }` |
| `priority_role` | `target_roles` | updated with `priority_role_id` |
| `management` | `preferences` | `{ "management": true/false }` |
| `location` | `preferences` | merged `location` |
| `authorization` | `preferences` | merged `authorization` |
| `preferences` | `preferences` | merged `more_of` and `avoid` from the same sentence, split on "avoid" if present, otherwise the whole text is `more_of` |

When `preferences` is saved, call `set_stage(session, tenant_id, "todos")`.

Resume PDF upload keeps using `POST /api/resumes/upload`. The counsel page uploads the file first, then posts the returned resume id as the `resume` answer text.

The counsellor agent spec uses provider `openrouter`, tier `mid`, tools `("blackboard_read", "blackboard_write")`, and `hands_off_to` `None`. Its prompt says it may only store the candidate's words.

- [x] **Step 1: Write the failing test**

```python
import pytest

from app.domain.counsel import record_answer
from app.domain.journey import get_or_create_journey


@pytest.mark.asyncio
async def test_counsel_walks_eight_steps_and_opens_todos(db_session, sample_tenant):
    answers = [
        ("linkedin", "https://www.linkedin.com/in/ada"),
        ("resume", "resume-id-1"),
        ("target_work", "data science, pytorch, spark pipelines"),
        ("priority_role", "role_ml_engineer"),
        ("management", "no"),
        ("location", "Bengaluru, remote is fine"),
        ("authorization", "Authorized to work in India. No sponsorship needed."),
        ("preferences", "I want more modeling work and want to avoid on-call rotations."),
    ]
    last = None
    for step, text in answers:
        last = await record_answer(db_session, sample_tenant.id, step, text, "text")
    assert last["done"] is True
    journey = await get_or_create_journey(db_session, sample_tenant.id)
    assert journey.stage == "todos"


@pytest.mark.asyncio
async def test_mic_answer_is_stored_as_text(db_session, sample_tenant):
    result = await record_answer(
        db_session, sample_tenant.id, "linkedin", "spoken profile text", "mic"
    )
    assert result["step"] == "resume"
```

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_counsel.py -q`
Expected: FAIL with import error for `record_answer`.

- [x] **Step 3: Implement counsel, the route, and the page**

`record_answer` rejects a step that is not the next unanswered step with `CounselOrderError`. It writes `ProfileSection` rows (`tenant_id`, `section`, `step`, `body` JSON, `input_mode`). For `target_work`, `body["suggestions"]` is the id list from `suggest_roles(text, mgmt_experience=False)`. For `priority_role`, the text must be one of those ids; then call `select_roles` with that single id as the priority and the suggestion ids as `role_ids`. For `management`, accept only `yes` or `no`, case insensitive. `yes` re-runs `suggest_roles` with `mgmt_experience=True` and `select_roles(..., mgmt_experience=True)`.

`frontend/lib/speech.ts`:

```ts
export function listenOnce(): Promise<string> {
  const Recognition = (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition;
  if (!Recognition) {
    return Promise.reject(new Error("This browser has no speech recognition. Type the answer instead."));
  }
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  return new Promise((resolve, reject) => {
    recognition.onresult = (event) => resolve(event.results[0][0].transcript);
    recognition.onerror = () => reject(new Error("The microphone did not capture speech."));
    recognition.start();
  });
}
```

`frontend/app/counsel/page.tsx` loads `GET /api/counsel`, shows `prompt`, a textarea with class `neo-inset`, a button "Speak" that fills the textarea from `listenOnce`, and a button "Save answer" that posts the answer. When `done` is true, `window.location.assign("/todos")`.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest app/tests/test_counsel.py app/tests/test_roles.py -q`
Expected: PASS. Then `cd frontend && npx tsc --noEmit`.

- [x] **Step 5: Commit**

```bash
git add app/domain/counsel.py app/domain/models.py app/api/routers/counsel.py app/api/main.py app/harness/roster.py alembic/versions/b7e1c2a9d4f0_candidate_journey.py frontend/lib/speech.ts frontend/app/counsel/page.tsx app/tests/test_counsel.py
git commit -m "feat: interview the candidate and save profile sections"
```

---

### Task 5: To-do list and the readiness lock

**Files:**
- Create: `frontend/app/todos/page.tsx`
- Modify: `app/domain/journey.py` with `refresh_stage_from_readiness`
- Test: `app/tests/test_journey.py` add one test

**Interfaces:**
- Consumes: `POST /api/gaps/compute`, `GET /api/todos`, `POST /api/todos/{id}` with `{ "action": "accept" | "edit" | "dismiss" }`, `readiness_gate.evaluate_readiness`.
- Produces: `async def refresh_stage_from_readiness(session, tenant_id) -> str`. When the current stage is `todos` and readiness `is_ready` is true, the stage becomes `mailbox`. Otherwise the stage is unchanged.

- [x] **Step 1: Write the failing test**

Append to `app/tests/test_journey.py`. Build a `ReadinessScore` with `overall_score=80` and no open critical `TodoItem`, set the journey to `todos`, call `refresh_stage_from_readiness`, and assert the stage is `mailbox`. A second case with an open critical todo stays on `todos`.

Use the real model constructors. `ReadinessScore` requires `tenant_id` and `overall_score`. `TodoItem` requires `category`, `severity`, `issue_text`, `why_it_matters`, and `fix_draft`.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py::test_ready_todos_advance_to_mailbox -q`
Expected: FAIL because `refresh_stage_from_readiness` does not exist.

- [x] **Step 3: Implement the transition and the page**

```python
async def refresh_stage_from_readiness(session: AsyncSession, tenant_id: str) -> str:
    journey = await get_or_create_journey(session, tenant_id)
    if journey.stage != "todos":
        return journey.stage
    status = await readiness_gate.evaluate_readiness(session, tenant_id)
    if status.is_ready:
        await set_stage(session, tenant_id, "mailbox")
    return (await get_or_create_journey(session, tenant_id)).stage
```

`frontend/app/todos/page.tsx` posts `/api/gaps/compute` on load, then lists `/api/todos`. Each open item is a `neo-raised` card with the issue, why it matters, and the fix draft. Buttons post `accept` or `dismiss`. After each action, call a new `POST /api/journey/refresh` that runs `refresh_stage_from_readiness`. If the response stage is `mailbox`, navigate to `/mailbox`.

Dismiss still uses the existing cap: dismissing a critical todo caps the score at 69. The page copy says that. Do not change `gap_engine`.

- [x] **Step 4: Run the tests and typecheck**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py app/tests/test_gap_engine.py -q`
Expected: PASS. Then `cd frontend && npx tsc --noEmit`.

- [x] **Step 5: Commit**

```bash
git add app/domain/journey.py app/api/routers/journey.py frontend/app/todos/page.tsx app/tests/test_journey.py
git commit -m "feat: show front-face todos and unlock the mailbox when they are clear"
```

---

### Task 6: Mailbox connect as agent tools

**Files:**
- Create: `app/mcp/__init__.py`
- Create: `app/mcp/tools.py`
- Create: `frontend/app/mailbox/page.tsx`
- Modify: `app/harness/registry.py` to register the three tools below if the names are absent
- Test: `app/tests/test_mail_tools.py`

**Interfaces:**
- Consumes: `email_service.connect_mailbox`, `grant_outreach_consent`, `send_outreach_email`.
- Produces these tool handlers, each taking `tenant_id` plus the fields below:

```python
async def connect_mailbox(tenant_id: str, session: AsyncSession, email_address: str, access_token: str, refresh_token: str, provider: str = "gmail") -> dict: ...
async def grant_send_consent(tenant_id: str, session: AsyncSession) -> dict: ...
async def queue_recruiter_email(tenant_id: str, session: AsyncSession, recipient: str, subject: str, body: str) -> dict: ...
```

`queue_recruiter_email` calls `send_outreach_email` only when the journey stage is `hunt` or `active`. Otherwise it raises `MailboxGateError` with the text `Connect the mailbox after the to-do list is clear.` On success of connect plus consent, `set_stage(..., "hunt")`.

Add `POST /api/journey/stage` with body `{ "stage": "mailbox" | "hunt" | "active" }`. It calls `set_stage` and returns `{ "stage": journey.stage }`. Regression returns HTTP 409 with the exception text.

The mailbox page collects email address, access token, and refresh token into `neo-inset` fields. Submit posts `/api/emails/connect`, then `/api/emails/consent`, then `/api/journey/stage` with `{ "stage": "hunt" }`. On 200, navigate to `/jobs`.

- [x] **Step 1: Write the failing test**

```python
import pytest

from app.domain.journey import set_stage
from app.mcp.tools import MailboxGateError, queue_recruiter_email


@pytest.mark.asyncio
async def test_recruiter_email_is_refused_before_the_mailbox_stage(db_session, sample_tenant):
    await set_stage(db_session, sample_tenant.id, "todos")
    with pytest.raises(MailboxGateError):
        await queue_recruiter_email(
            sample_tenant.id, db_session, "jobs@acme.com", "Application", "Hello"
        )
```

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_mail_tools.py -q`
Expected: FAIL with import error.

- [x] **Step 3: Implement the tools and the page**

Implement the three functions in `app/mcp/tools.py`. Register them on `registry` with `external=True` and `gate_required=True` for `queue_recruiter_email` only. `connect_mailbox` and `grant_send_consent` are `external=False`.

The page explains, in one sentence, that the agent sends from this mailbox only after the candidate approves a message. After consent, navigate to `/jobs`.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest app/tests/test_mail_tools.py app/tests/test_email_connect.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/mcp/__init__.py app/mcp/tools.py app/harness/registry.py frontend/app/mailbox/page.tsx app/api/routers/journey.py app/tests/test_mail_tools.py
git commit -m "feat: connect the mailbox before the agent can email a recruiter"
```

---

### Task 7: Job board fed by the scout

**Files:**
- Create: `frontend/app/jobs/page.tsx`
- Modify: `frontend/components/TodayView.tsx` only if it still calls `/api/scout/manual-scan`. Change that string to `/api/scout/scan-now`.
- Modify: `app/api/routers/jobs.py` `list_matched_jobs` so each item also includes `title` and `company` from the related `JobListing`.
- Test: `app/tests/test_scout.py` already covers the scheduler.

**Interfaces:**
- Consumes: `POST /api/scout/scan-now`. `GET /api/jobs` today returns `match_id`, `job_id`, `match_score`, `why_matched`, `status`.
- Produces: the same list plus `title: str` and `company: str`. The jobs page renders one `neo-raised` card per match using those fields. The scan button is disabled when `GET /api/journey` stage is `counsel`, `todos`, or `mailbox`. A 403 from scan-now is shown as `data.detail`. Two buttons are present and disabled in this task: "Use my resume" and "Refine for this job". Task 8 wires them.

- [x] **Step 1: Extend the jobs list and write the page**

In `list_matched_jobs`, load `JobListing` by `m.job_id` and add `"title": job.title` and `"company": job.company` to each dict. The page maps that array. Do not add a second list endpoint.

- [x] **Step 2: Fix the stale scout path**

In `frontend/components/TodayView.tsx`, replace `/api/scout/manual-scan` with `/api/scout/scan-now`.

- [x] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [x] **Step 4: Run the scout tests**

Run: `.venv/bin/python -m pytest app/tests/test_scout.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/app/jobs/page.tsx frontend/components/TodayView.tsx
git commit -m "feat: list scouted jobs on a light job board"
```

---

### Task 8: Apply with the original resume or a refined one

**Files:**
- Create: `app/domain/apply_choice.py`
- Modify: `app/api/routers/applications.py` with `POST /api/applications/choose`
- Modify: `frontend/app/jobs/page.tsx` to call that route
- Test: `app/tests/test_apply_choice.py`

**Interfaces:**
- Consumes: `get_master_version`, `draft_application_packet`, `review_tailored_honesty`.
- Produces:

```python
async def prepare_application(
    session: AsyncSession,
    tenant_id: str,
    job_id: str,
    mode: Literal["original", "refine"],
) -> dict:
    """Returns mode, resume_version_id, cover_letter body, honesty_review, draft_source."""
```

`original` uses the master resume content unchanged as the submitted resume. It still calls `generate_cover_letter` with that master content. `draft_source` is `original`. It does not call `draft_application_packet`.

`refine` calls `draft_application_packet`. `draft_source` is that packet's `draft_source`. The route saves both documents with `create_tailored_version` when `save` is true, matching the tailor endpoint.

The route body is `{ "job_id": str, "mode": "original" | "refine" }`. An unknown mode returns HTTP 400 with detail `mode must be original or refine`.

The jobs page enables the two buttons. "Refine for this job" posts `mode: "refine"` and shows the returned summary and cover letter in a `neo-inset` panel before a "Submit this packet" button. "Use my resume" posts `mode: "original"` and shows the same confirmation panel. Submit is Task 9's send plus the existing `POST /api/applications/submit`. This task ends when the packet is prepared and shown. The submit button can call the existing submit route with the returned version ids.

- [x] **Step 1: Write the failing test**

Construct a tenant, a master `DocumentVersion`, and a `JobListing` the same way `app/tests/test_execution_api.py` does. Call `prepare_application(..., mode="original")`. Assert the resume text still contains a bullet from the master and `draft_source == "original"`. Call `mode="refine"` with no OpenRouter key stored. Assert `draft_source == "deterministic"` and `honesty_review["is_honest"] is True`.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_apply_choice.py -q`
Expected: FAIL with import error.

- [x] **Step 3: Implement `prepare_application` and the route**

Keep the honesty gate on the refine path by using `draft_application_packet` unchanged. Do not add a second reviewer.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest app/tests/test_apply_choice.py app/tests/test_application_engine.py app/tests/test_execution_api.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/domain/apply_choice.py app/api/routers/applications.py frontend/app/jobs/page.tsx app/tests/test_apply_choice.py
git commit -m "feat: let the candidate apply with the original resume or a refined one"
```

---

### Task 9: Recruiter hunter from the posting only

**Files:**
- Create: `app/domain/recruiter_hunter.py`
- Modify: `app/api/routers/applications.py` so a successful submit calls `draft_recruiter_touch`
- Modify: `app/harness/roster.py` with agent `recruiter`
- Test: `app/tests/test_recruiter_hunter.py`

**Interfaces:**
- Consumes: `queue_recruiter_email` only after the draft is approved. This task creates the draft row. It does not send.
- Produces:

```python
def extract_public_email(text: str) -> str | None: ...

async def draft_recruiter_touch(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
    job_text: str,
    resume_excerpt: str,
    cover_letter: str,
) -> dict:
    """Returns {"status": "pending_approval", "recipient": email} or {"status": "no_public_email"}."""
```

`extract_public_email` returns the first address matched by `[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}`. It returns `None` for text that only contains a LinkedIn profile URL. It does not fetch any URL.

`draft_recruiter_touch` writes an `OutreachMessage` with `status="pending_approval"`, `recipient_role="Recruiter"`, subject `Application for {job title}`, and a body that includes the cover letter. `recipient_name` is `Recruiting team` when the posting has no name. When there is no email, it writes nothing and returns `no_public_email`.

Roster entry `recruiter`: provider `openrouter`, tier `cheap`, tools `("queue_recruiter_email",)` once that tool name is the registry name, `hands_off_to` `None`. Prompt: "Send only to an email that is already written on the job posting. Never look up a person."

- [x] **Step 1: Write the failing test**

```python
from app.domain.recruiter_hunter import extract_public_email


def test_extracts_a_posted_email_and_ignores_linkedin_urls():
    assert extract_public_email("Apply at jobs@acme.com or ignore us.") == "jobs@acme.com"
    assert extract_public_email("https://www.linkedin.com/in/someone") is None
```

Add an async test that a job description without an email returns `no_public_email` and leaves `OutreachMessage` count at 0.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_recruiter_hunter.py -q`
Expected: FAIL with import error.

- [x] **Step 3: Implement the extractor and the draft**

Wire `draft_recruiter_touch` at the end of the existing submit handler after the audit log is created. Pass `job.description` as `job_text`. Do not perform an HTTP request inside this function.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest app/tests/test_recruiter_hunter.py app/tests/test_execution_api.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/domain/recruiter_hunter.py app/api/routers/applications.py app/harness/roster.py app/tests/test_recruiter_hunter.py
git commit -m "feat: draft recruiter email only when the posting prints an address"
```

---

### Task 10: Application manager

**Files:**
- Create: `frontend/app/applications/page.tsx`
- Modify: `app/domain/journey.py` usage from the submit route: after the first successful submit, `set_stage(..., "active")`.
- Test: extend `app/tests/test_journey.py` with `test_submit_advances_hunt_to_active`. If the submit route is hard to call in a unit test, call `set_stage` from a small helper `async def note_application_submitted(session, tenant_id) -> str` that sets `active` only when the current stage is `hunt`.

**Interfaces:**
- Consumes: `GET /api/tracker/applications`.
- Produces: `note_application_submitted`. The page lists company, title, status, and the resume version id. Status values already used by `ApplicationTrack` stay: `applied`, `acknowledged`, `interview`, `assessment`, `offer`, `rejected`, `ghosted`, `withdrawn`.

- [x] **Step 1: Write the failing test**

A journey on `hunt` becomes `active` after `note_application_submitted`. A journey on `todos` raises `JourneyRegressionError` if the helper is asked to jump to `active` by calling `set_stage` directly. The helper itself moves `hunt` to `active` and leaves `todos` unchanged.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py::test_hunt_becomes_active_after_submit -q`
Expected: FAIL with missing helper.

- [x] **Step 3: Implement the helper and the page**

Call `note_application_submitted` from the submit endpoint after the audit log flush. The page is a stack of `neo-raised` cards. An empty list says "No applications yet."

- [x] **Step 4: Run the tests and typecheck**

Run: `.venv/bin/python -m pytest app/tests/test_journey.py app/tests/test_tracker.py -q`
Expected: PASS. Then `cd frontend && npx tsc --noEmit`.

- [x] **Step 5: Commit**

```bash
git add app/domain/journey.py app/api/routers/applications.py frontend/app/applications/page.tsx app/tests/test_journey.py
git commit -m "feat: keep submitted applications on a tracker page"
```

---

### Task 11: Recruiter conversation inbox

**Files:**
- Create: `app/domain/inbox.py`
- Create: `frontend/app/inbox/page.tsx`
- Modify: `app/api/routers/tracker.py` with `GET /api/tracker/inbox`
- Test: `app/tests/test_inbox.py`

**Interfaces:**
- Consumes: `OutreachMessage` and `InboundEmail` rows that share an `application_id`.
- Produces:

```python
async def thread_for_application(session: AsyncSession, tenant_id: str, application_id: str) -> list[dict]:
    """Each item is {"direction": "out"|"in", "subject": str, "body": str, "at": str}."""
```

Outbound items come from `OutreachMessage`. Inbound items come from `InboundEmail`. Sort by time ascending. Ignore rows for another tenant.

The page groups threads by application id. The list endpoint returns `{ "threads": [ { "application_id", "company_name", "messages": [...] } ] }`. Company name comes from `ApplicationTrack.company_name`.

- [x] **Step 1: Write the failing test**

Create one `ApplicationTrack`, one sent `OutreachMessage`, and one `InboundEmail` on that application. Assert `thread_for_application` returns the outbound message first when its timestamp is earlier, then the inbound message. A message for `second_tenant` is absent.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_inbox.py -q`
Expected: FAIL with import error.

- [x] **Step 3: Implement the query and the page**

Use the existing `POST /api/tracker/inbound-email` classifier. Do not add a new classifier. The inbox only reads rows that classifier already writes.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest app/tests/test_inbox.py app/tests/test_tracker_and_insights_api.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add app/domain/inbox.py app/api/routers/tracker.py frontend/app/inbox/page.tsx app/tests/test_inbox.py
git commit -m "feat: show recruiter email threads on the application"
```

---

### Task 12: Interview calendar and reminders

**Files:**
- Create: `app/domain/calendar.py`
- Modify: `app/domain/models.py` with `InterviewEvent`
- Create: `alembic/versions/c4a8e1b27d11_interview_events.py` with `down_revision = "b7e1c2a9d4f0"`
- Modify: `app/api/routers/tracker.py` so an inbound classification of `interview` calls `record_interview`
- Create: `frontend/app/calendar/page.tsx`
- Test: `app/tests/test_calendar.py`

**Interfaces:**
- Consumes: `InboundEmail.classification`, `ApplicationTrack`.
- Produces:

```python
async def record_interview(
    session: AsyncSession,
    tenant_id: str,
    application_id: str,
    starts_at: datetime,
    title: str,
) -> InterviewEvent: ...

def due_reminders(event: InterviewEvent, now: datetime) -> list[str]:
    """Returns a subset of ["24h", "1h"]. Empty when the flag for that window is already true."""
```

`InterviewEvent` columns: `id`, `tenant_id`, `application_id`, `title`, `starts_at`, `reminder_24h_sent`, `reminder_1h_sent`. Both reminder flags default false.

`due_reminders` returns `"24h"` when `now` is at or after `starts_at - 24 hours` and the 24h flag is false and `now` is still before `starts_at`. It returns `"1h"` on the same rule with one hour. It returns nothing after `starts_at`.

`POST /api/tracker/reminders/run` accepts `{ "now": isoformat }` in tests. For each due token it creates an `OutreachMessage` to the tenant user's email, subject `Interview reminder`, body containing the event title and start time, status `sent`, and sets the matching flag true. This test route does not open a network connection.

The calendar page lists events from `GET /api/tracker/interviews` as `neo-raised` rows: title, company, local datetime.

- [x] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

from app.domain.calendar import due_reminders


def test_reminder_windows():
    class Event:
        starts_at = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)
        reminder_24h_sent = False
        reminder_1h_sent = False

    early = Event.starts_at - timedelta(hours=30)
    day_before = Event.starts_at - timedelta(hours=20)
    hour_before = Event.starts_at - timedelta(minutes=30)
    assert due_reminders(Event(), early) == []
    assert due_reminders(Event(), day_before) == ["24h"]
    assert due_reminders(Event(), hour_before) == ["24h", "1h"]
    Event.reminder_24h_sent = True
    assert due_reminders(Event(), hour_before) == ["1h"]
```

Add an async test that `record_interview` persists a row and a second call with the same `application_id` and `starts_at` returns the same id.

- [x] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest app/tests/test_calendar.py -q`
Expected: FAIL with import error.

- [x] **Step 3: Implement the calendar**

Parse a datetime from the inbound email body only when the classifier already returned `interview` and the body contains an ISO-8601 timestamp. If there is no timestamp, do not create an event. Do not guess a time from phrases like "tomorrow".

- [x] **Step 4: Run the tests and typecheck**

Run: `.venv/bin/python -m pytest app/tests/test_calendar.py app/tests/test_tracker.py -q`
Expected: PASS. Then `cd frontend && npx tsc --noEmit`.

- [x] **Step 5: Commit**

```bash
git add app/domain/calendar.py app/domain/models.py alembic/versions/c4a8e1b27d11_interview_events.py app/api/routers/tracker.py frontend/app/calendar/page.tsx app/tests/test_calendar.py
git commit -m "feat: save interviews and emit 24-hour and 1-hour reminders"
```

---

## Spec coverage

| Request | Task |
|---|---|
| Light neumorphic theme | Task 1 |
| Login and registration first | Task 2 |
| Counsellor asks for LinkedIn, resume, and questions; text or mic; profile sections | Task 4 |
| Evaluate the profile and show a to-do list | Task 5 |
| Connect email so the agent can write recruiters, via tools | Task 6 |
| Scout jobs onto the dashboard | Task 7 |
| Apply with the uploaded resume or a resume refined to the job | Task 8 |
| Draft the cover letter and the refined resume, then apply | Task 8, using the existing submit route |
| Recruiter email with the resume and cover letter | Task 9 |
| Saved and managed applications | Task 10 |
| Saved and managed recruiter conversations | Task 11 |
| Interview calendar and reminders | Task 12 |

Agents, tool calls, and browser automation stay on the harness that is already in the repo. Task 4 adds the counsellor to `AGENT_ROSTER`. Task 6 adds the mailbox tools. Task 9 adds the recruiter agent. Scout and the Playwright apply ladder are unchanged on purpose.

## Execution order

Tasks 1 through 12 are ordered. Do not start a task until the previous task's tests pass. One agent may take one task. The next agent reads this file and the git log, then takes the next unchecked task.
