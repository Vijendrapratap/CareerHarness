# Browser Auto-fill + Approve Implementation Plan (Plan 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For jobs at or above the apply line on Greenhouse, Lever or Ashby, a server-side browser fills the real application form from the candidate's profile, shows the candidate every answer plus a screenshot, asks only for what it can't know (remembered for next time), and submits only after the candidate approves. Anything it can't do safely becomes a clean hand-off with the answers ready to paste.

**Architecture:** Three layers.
1. `app/apply/answers.py` (pure): classify a form field from its label/type/options into a known key, and produce an answer from the candidate's apply profile, facts and remembered answers. EEO/demographic questions get "decline to self-identify". Unknown required fields become questions for the candidate.
2. `app/apply/browser.py` (Playwright): resolve the ATS apply URL, scan fields with one DOM script, fill each one by kind (text, file, native select, radio/checkbox group, searchable combobox), detect CAPTCHA and forbidden fields, screenshot, and on approval click submit and detect success.
3. `app/domain/apply_sessions.py` + `app/api/routers/apply.py`: an `ApplySession` row tracks each attempt (`filling → needs_answers | ready → submitting → submitted | handoff | failed`). Filling and submitting run in background tasks. Submit re-fills from scratch, so no browser is kept alive between requests.

**Tech Stack:** Playwright for Python 1.63 (Chromium 1243 already cached), FastAPI BackgroundTasks, reportlab for tailored resume PDFs.

**Spec:** User decision: "Browser auto-fill + approve". Live form reading on 2026-09-23 (Discord/Greenhouse, Spotify/Lever, Ramp/Ashby): all three have name, email, phone and resume. Greenhouse uses searchable dropdowns rendered as text inputs, and has reCAPTCHA. Lever uses native selects/radios/checkboxes and has hCaptcha. Ashby uses radios, checkbox groups and yes/no buttons, with no CAPTCHA. Custom questions ("Why do you want to work at X?", work authorization for a specific country) can't be inferred.

## Status (2026-09-23)

Implemented. 197 backend tests pass (7 real-browser tests against the fixture forms).
Checked on live forms without submitting:
- Ashby (Ramp): filled completely.
- Lever (Spotify): filled; asks one company-specific question.
- Greenhouse (Discord), full UI flow as a dry run: 21 fields filled, 0 questions left after the candidate
  answered; demographic questions declined; nothing sent.
Bugs found live and fixed:
- react-select values read back empty; they are now read from the displayed element.
- Greenhouse's resume input is labelled "Attach"; the element id is now used to classify it.
- Type-to-search dropdowns (country, city) are now filled by typing.
- Web fonts stalled the screenshot; a screenshot failure no longer aborts the fill.
- A dropdown used to fall back to the first option when nothing matched; it now asks the candidate.
- A widget showing a different value than the one clicked (phone country "+1") is now rejected.
- Deadlock: the Counsel finalize request held an uncommitted write while its background scan waited;
  it now commits first. Scans also take a per-candidate lock, and the SQLite busy timeout is 30s.
Known limits: Ashby yes/no *button* questions are not scanned yet (they fall to the candidate or the form
reports them); Greenhouse and Lever show CAPTCHAs, so live submits there may end in a hand-off.
Submitting stays off until `APPLY_SUBMIT_ENABLED=true`.

## Global Constraints

- **Never submit without the candidate's explicit approval of that specific application.** No auto-submit, even in trusted mode.
- **`APPLY_SUBMIT_ENABLED` (default False):** when off, Approve fills and validates but never clicks submit (result `dry_run`). Dev and tests never submit to real companies.
- Only jobs at or above the 4.0 apply line (`ensure_apply_line`). At most 10 submissions per candidate per day.
- Never guess eligibility or legal answers. Work authorization, visas, relocation and "why us" come from the candidate, and are remembered per question text.
- Demographic/EEO questions: always pick a decline option. If a required one has no decline option, ask the candidate.
- **Forbidden fields stop the fill and hand off:** SSN or national ID, passport, date of birth, bank, credit card, payment, driver's licence.
- A CAPTCHA, a login wall, an unsupported ATS or an expired posting means **hand-off**: open the application with prepared answers.
- Resume attached: the candidate's original uploaded PDF, or a PDF of the approved tailored version.
- Tests use local fixture forms only, never live ATS pages.

## Tasks

### Task 1: Answer engine (`app/apply/answers.py`, test `app/tests/test_apply_answers.py`)
- [ ] `classify(label, kind, options) -> str | None` for: first_name, last_name, full_name, email, phone, location, country, current_company, linkedin, github, website, resume, cover_letter, how_heard, sponsorship, eeo, pronouns, forbidden.
- [ ] `answer(key, field, ctx) -> Answer(value, source)`, with sources profile / facts / memory / default / decline. `question_key(label)` normalizes labels for memory.
- [ ] Tests: every classification; sponsorship follows facts; EEO picks a decline option; forbidden detected; unknown required gives no answer.

### Task 2: Storage (`app/domain/models.py`, migration)
- [ ] `ApplySession(id, tenant_id, job_id, mode, resume_version_id, status, apply_url, ats, fields JSON, questions JSON, result_code, message, screenshot_path, created_at, updated_at)`.
- [ ] `ResumeFile(id, tenant_id, filename, content bytes, created_at)`; the upload endpoint stores the original PDF.
- [ ] Facts internal dicts: `apply_profile` (name, email, phone, location, current_company, linkedin, github, website) and `apply_answers` (question key → answer).

### Task 3: Browser driver (`app/apply/browser.py`, test `app/tests/test_apply_browser.py` with fixture forms)
- [ ] `apply_url(job, org_lookup) -> (ats, url) | None` (Greenhouse embed form, Lever `/apply`, Ashby `/application`).
- [ ] `fill(page, plan)` handles every field kind; `scan(page)`; `detect_captcha(page)`; `submit(page, ats) -> result_code`.
- [ ] Fixture forms mimicking each ATS's structure (native fields, a searchable combobox, radios, checkbox groups, file input, EEO with a decline option, a custom required textarea).
- [ ] Tests: fill a fixture, then read the DOM values back; required unknown field reported; forbidden field stops the fill; submit on the fixture reaches its "Thank you" page.

### Task 4: Session service + API
- [ ] `POST /api/apply/sessions {job_id, mode}` (gate, cap, resolve URL, then a background fill) returns 202 with the session.
- [ ] `GET /api/apply/sessions/{id}`, `GET …/screenshot`, `POST …/answers {answers, profile}` (remember, then re-fill), `POST …/approve` (background submit).
- [ ] Tests with the driver stubbed: status transitions, answers are remembered for the next job, approve blocked while questions are open, dry-run when submit is disabled, daily cap.

### Task 5: UI
- [ ] Jobs card: "Auto-fill application" for supported ATSs; a review panel showing the screenshot, filled fields with their source, questions to answer, the apply profile, and Approve & submit. The result is shown clearly (submitted / dry-run / hand-off with an Open-application link and copyable answers).
