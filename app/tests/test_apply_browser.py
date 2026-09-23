"""Browser auto-fill against local fixture forms shaped like Greenhouse, Lever and Ashby (never live ATS)."""

from pathlib import Path

import pytest

from app.apply.answers import ApplyContext, question_key
from app.apply.browser import resolve_apply_url, run_fill

FORMS = Path(__file__).parent / "fixtures" / "forms"


@pytest.fixture
def ctx(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 fake")
    return ApplyContext(
        profile={"full_name": "Ada Lovelace", "email": "ada@example.com", "phone": "+44 20 7946 0000",
                 "location": "London, UK", "country": "United Kingdom", "current_company": "Babbage Labs",
                 "linkedin": "https://linkedin.com/in/ada"},
        facts={"needs_sponsorship": False},
        memory={},
        resume_path=str(resume),
    )


def by_label(result, text):
    return next(f for f in result.fields if text.lower() in f["label"].lower())


@pytest.mark.asyncio
async def test_greenhouse_like_fills_profile_declines_eeo_and_asks_the_rest(ctx, tmp_path):
    result = await run_fill((FORMS / "greenhouse_like.html").as_uri(), ctx, screenshot_path=str(tmp_path / "s.png"))
    assert by_label(result, "First Name")["value"] == "Ada"
    assert by_label(result, "Gender")["value"] == "Decline To Self Identify"
    assert by_label(result, "Attach")["value"] == "resume.pdf"      # labelled "Attach", id="resume"
    assert by_label(result, "Country")["value"] == "United Kingdom"  # options appear only after typing
    asked = {q["label"] for q in result.questions}
    assert asked == {"Why do you want to work at Acme?", "Are you legally authorized to work in the United States?",
                     "Preferred office"}
    assert next(q for q in result.questions if "authorized" in q["label"])["options"] == ["Yes", "No"]
    assert result.captcha is True and result.status == "needs_answers"
    assert (tmp_path / "s.png").stat().st_size > 1000


@pytest.mark.asyncio
async def test_answers_are_remembered_and_submit_reaches_confirmation(ctx, tmp_path):
    ctx.memory = {
        question_key("Why do you want to work at Acme?*"): "I want to build tools engineers love.",
        question_key("Are you legally authorized to work in the United States?*"): "Yes",
        question_key("Preferred office*"): "Paris",
    }
    result = await run_fill((FORMS / "greenhouse_like.html").as_uri(), ctx, submit=True,
                            screenshot_path=str(tmp_path / "s.png"))
    assert result.questions == []
    assert result.status == "submitted", result.message


@pytest.mark.asyncio
async def test_lever_like_groups_selects_and_readback(ctx, tmp_path):
    result = await run_fill((FORMS / "lever_like.html").as_uri(), ctx, screenshot_path=str(tmp_path / "s.png"))
    assert by_label(result, "Full name")["value"] == "Ada Lovelace"
    assert by_label(result, "Current company")["value"] == "Babbage Labs"
    assert by_label(result, "Gender")["value"] == "Prefer not to disclose"
    assert by_label(result, "How did you hear")["value"] == "Job board"
    [q] = result.questions
    assert q["label"] == "Which employment types are you open to?" and q["kind"] == "checkbox"
    assert q["options"] == ["Yes - Intern", "Yes - Full Time Employment"]


@pytest.mark.asyncio
async def test_forbidden_field_hands_off_without_filling(ctx, tmp_path):
    result = await run_fill((FORMS / "ashby_like.html").as_uri(), ctx, submit=True,
                            screenshot_path=str(tmp_path / "s.png"))
    assert result.status == "handoff" and "Social Security" in result.message


def test_resolve_apply_url_for_each_ats():
    assert resolve_apply_url("https://jobs.lever.co/spotify/827b") == ("lever", "https://jobs.lever.co/spotify/827b/apply")
    assert resolve_apply_url("https://jobs.ashbyhq.com/ramp/99/") == ("ashby", "https://jobs.ashbyhq.com/ramp/99/application")
    assert resolve_apply_url("https://job-boards.greenhouse.io/discord/jobs/8817776002") == (
        "greenhouse", "https://job-boards.greenhouse.io/embed/job_app?for=discord&token=8817776002")
    assert resolve_apply_url("https://databricks.com/careers/job?gh_jid=7882009002", greenhouse_org="databricks") == (
        "greenhouse", "https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=7882009002")
    assert resolve_apply_url("https://remoteok.com/remote-jobs/123") is None


@pytest.mark.asyncio
async def test_unmatched_dropdown_answer_is_asked_never_replaced_by_the_first_option(ctx, tmp_path):
    ctx.memory = {question_key("Preferred office*"): "Tokyo"}
    result = await run_fill((FORMS / "greenhouse_like.html").as_uri(), ctx, screenshot_path=str(tmp_path / "s.png"))
    assert "Preferred office" in {q["label"] for q in result.questions}
    assert all(f["label"] != "Preferred office" for f in result.fields)


@pytest.mark.asyncio
async def test_widget_showing_a_different_value_than_picked_is_asked(ctx, tmp_path):
    ctx.memory = {question_key("Dial code"): "United Kingdom +44"}
    result = await run_fill((FORMS / "greenhouse_like.html").as_uri(), ctx, screenshot_path=str(tmp_path / "s.png"))
    # The widget still shows "+1": never report that as the candidate's answer (required fields get asked).
    assert all(f["label"] != "Dial code" for f in result.fields)


@pytest.mark.asyncio
async def test_ashby_yes_no_buttons_are_scanned_and_never_submit_the_form(ctx, tmp_path):
    url = (FORMS / "ashby_yesno.html").as_uri()
    first = await run_fill(url, ctx, screenshot_path=str(tmp_path / "s.png"))
    [q] = first.questions  # required button question; the optional relocation one is left alone
    assert q["label"] == "Are you authorized to work in the U.S. without company sponsorship?"
    assert q["options"] == ["Yes", "No"] and q["kind"] == "buttons"

    ctx.memory = {question_key(q["label"]): "Yes"}
    second = await run_fill(url, ctx, screenshot_path=str(tmp_path / "s.png"))
    assert second.status == "ready"  # clicking the submit-type "Yes" must not have submitted anything
    assert by_label(second, "without company sponsorship")["value"] == "Yes"
