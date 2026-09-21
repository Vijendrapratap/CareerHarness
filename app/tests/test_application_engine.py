"""Unit and contract tests for Application Engine Pipeline (F9).

Tests:
- AT-01: Tailored resume matches target job keywords strictly within factual constraints.
- AT-02: Reviewer sub-agent checks honesty: flags hallucinated metrics, dates, companies.
- AT-03: ATS checker simulates keyword scan and format check.
- AT-04: Screening questions answered strictly from verified profile facts; unverified triggers HITL.
- AT-05: 3-tier fallback ladder on bot block (Tier 1 -> Tier 2 -> Tier 3).
- AT-07: Application submit audit log created with immutable snapshot.
- VR-01: Every application attempt links to an immutable DocumentVersion ID.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.application_engine import (
    answer_screening_questions,
    check_ats_compatibility,
    execute_application_submission,
    review_tailored_honesty,
    tailor_resume,
)
from app.domain.models import JobListing, Tenant
from app.domain.vault import create_initial_master


@pytest.fixture
def sample_master_resume():
    return {
        "candidate_name": "Jane Doe",
        "contact_info": {"email": "jane@example.com", "phone": "555-0100"},
        "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Senior Engineer",
                "dates": "2021 - Present",
                "bullets": [
                    "Architected high-throughput API processing 50,000 requests per minute with 99.9% uptime",
                    "Reduced database query latency by 45% using PostgreSQL indexing and caching",
                ],
            },
            {
                "company": "Startup Labs",
                "role": "Software Developer",
                "dates": "2018 - 2021",
                "bullets": [
                    "Built microservices in Python and Docker containerized deployments",
                    "Scaled platform from 1,000 to 100,000 active users",
                ],
            },
        ],
        "education": [
            {"school": "State University", "degree": "BS in Computer Science", "year": "2018"}
        ],
    }


@pytest.fixture
def sample_job():
    return JobListing(
        id="job-target-001",
        title="Senior Backend Engineer",
        company="Fintech Giants",
        url="https://fintechgiants.com/jobs/001",
        description="We are seeking a Senior Backend Engineer proficient in Python, FastAPI, and PostgreSQL to scale financial APIs.",
    )


def test_at01_tailored_resume_matches_keywords_within_factual_constraints(
    sample_master_resume, sample_job
):
    """AT-01: Tailored resume matches target job keywords, strictly within factual constraints of master resume."""
    verified_skills = ["Python", "FastAPI", "Docker", "PostgreSQL"]

    tailored = tailor_resume(sample_master_resume, sample_job, verified_skills)

    # Keywords from job description that candidate possesses should be prioritized
    injected = tailored["tailored_keywords_injected"]
    assert "Python" in injected or "FastAPI" in injected or "PostgreSQL" in injected

    # Verify that company names and dates are preserved exactly
    tailored_companies = [e["company"] for e in tailored["experience"]]
    assert tailored_companies == ["Tech Corp", "Startup Labs"]

    # Verify that skills list does NOT contain any non-verified skills
    for s in tailored["skills"]:
        assert s in verified_skills


def test_at02_reviewer_subagent_flags_hallucinations(sample_master_resume):
    """AT-02: Reviewer sub-agent checks honesty: flags hallucinated metrics, dates, companies, and skills."""
    verified_skills = ["Python", "FastAPI", "Docker", "PostgreSQL"]

    # 1. Test clean honest draft -> passes review
    honest_draft = {
        "candidate_name": "Jane Doe",
        "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "experience": [
            {
                "company": "Tech Corp",
                "dates": "2021 - Present",
                "bullets": [
                    "Architected high-throughput API processing 50,000 requests per minute with 99.9% uptime"
                ],
            }
        ],
    }
    clean_review = review_tailored_honesty(sample_master_resume, honest_draft, verified_skills)
    assert clean_review["is_honest"] is True
    assert clean_review["violations_count"] == 0

    # 2. Test hallucinated company
    fake_company_draft = {
        "candidate_name": "Jane Doe",
        "skills": ["Python"],
        "experience": [
            {
                "company": "Google",  # Never worked here!
                "dates": "2021 - Present",
                "bullets": ["Wrote search algorithms"],
            }
        ],
    }
    review_fake_co = review_tailored_honesty(sample_master_resume, fake_company_draft, verified_skills)
    assert review_fake_co["is_honest"] is False
    assert any("Hallucinated company" in v for v in review_fake_co["violations"])

    # 3. Test hallucinated metric
    fake_metric_draft = {
        "candidate_name": "Jane Doe",
        "skills": ["Python"],
        "experience": [
            {
                "company": "Tech Corp",
                "dates": "2021 - Present",
                "bullets": [
                    "Architected high-throughput API processing 999,999 requests per minute"  # 999,999 never existed!
                ],
            }
        ],
    }
    review_fake_metric = review_tailored_honesty(sample_master_resume, fake_metric_draft, verified_skills)
    assert review_fake_metric["is_honest"] is False
    assert any("Hallucinated metric" in v for v in review_fake_metric["violations"])

    # 4. Test invented unverified skill
    fake_skill_draft = {
        "candidate_name": "Jane Doe",
        "skills": ["Python", "Solidity Blockchain"],  # Candidate has never verified Solidity
        "experience": sample_master_resume["experience"],
    }
    review_fake_skill = review_tailored_honesty(sample_master_resume, fake_skill_draft, verified_skills)
    assert review_fake_skill["is_honest"] is False
    assert any("Invented skill" in v for v in review_fake_skill["violations"])


def test_at03_ats_scanner_and_format_check(sample_master_resume, sample_job):
    """AT-03: ATS checker simulates keyword scan and format check."""
    # Complete resume with standard headings
    ats_result = check_ats_compatibility(sample_master_resume, sample_job)
    assert ats_result["passed"] is True
    assert ats_result["overall_ats_score"] >= 60
    assert ats_result["checks"]["standard_headings"] is True
    assert ats_result["checks"]["single_column_layout"] is True
    assert ats_result["checks"]["parseable_text"] is True

    # Missing critical heading ("education")
    broken_resume = dict(sample_master_resume)
    del broken_resume["education"]
    broken_result = check_ats_compatibility(broken_resume, sample_job)
    assert broken_result["passed"] is False
    assert "education" in broken_result["missing_headings"]


def test_at04_screening_questions_strictly_from_verified_facts():
    """AT-04: Screening questions answered strictly from verified facts; unverified facts trigger HITL."""
    verified_facts = {
        "work_authorization": "Yes, authorized to work in the US without sponsorship",
        "years_of_experience": "6+ years",
        "location_preference": "Remote (EST)",
        "verified_skills": ["Python", "FastAPI", "PostgreSQL"],
    }

    questions = [
        "Are you legally authorized to work in the United States?",
        "How many years of experience do you have?",
        "Do you have experience with Python and FastAPI?",
        "Do you have a valid Security Clearance Secret level?",  # Unknown/unverified fact!
    ]

    res = answer_screening_questions(questions, verified_facts)

    assert res["requires_hitl"] is True
    assert len(res["unanswered_questions"]) == 1
    assert "Security Clearance" in res["unanswered_questions"][0]

    # Verify that the known questions were answered faithfully
    answers = res["answers"]
    assert "authorized to work" in answers[questions[0]].lower()
    assert "6+" in answers[questions[1]]
    assert "Python" in answers[questions[2]]


@pytest.mark.asyncio
async def test_at05_and_at07_and_vr01_submission_ladder_and_audit_log(
    db_session: AsyncSession, sample_master_resume, sample_job
):
    """AT-05, AT-07, VR-01: Bot mitigation ladder, audit log, and DocumentVersion linking."""
    tenant = Tenant(name="Applicant User", plan="pro")
    db_session.add(tenant)
    db_session.add(sample_job)
    await db_session.flush()

    # Create immutable DocumentVersion in Vault
    master_version = await create_initial_master(
        session=db_session,
        tenant_id=tenant.id,
        title="Master Resume",
        content=sample_master_resume,
        raw_markdown="Master",
    )

    screening_answers = {"Authorized": "Yes", "Years": "6+"}

    # 1. Normal submission (Tier 1: Playwright automated ATS)
    audit_tier1 = await execute_application_submission(
        session=db_session,
        tenant_id=tenant.id,
        job=sample_job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=False,
    )

    assert audit_tier1.resume_version_id == master_version.id  # VR-01
    assert audit_tier1.bot_mitigation_tier == 1
    assert audit_tier1.channel == "ats_autofill"
    assert audit_tier1.status == "submitted"
    assert audit_tier1.confirmation_code.startswith("ATS-")
    assert audit_tier1.submission_payload_snapshot["job_id"] == sample_job.id  # AT-07

    # 2. Bot block detected with connected email (Tier 2: Email apply fallback)
    audit_tier2 = await execute_application_submission(
        session=db_session,
        tenant_id=tenant.id,
        job=sample_job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=True,
        has_connected_email=True,
        company_email="jobs@fintechgiants.com",
    )
    assert audit_tier2.bot_mitigation_tier == 2
    assert audit_tier2.channel == "email_apply"
    assert audit_tier2.status == "submitted"
    assert audit_tier2.fallback_reason is not None

    # 3. Bot block detected without email (Tier 3: 1-Click Candidate Handoff Bundle)
    audit_tier3 = await execute_application_submission(
        session=db_session,
        tenant_id=tenant.id,
        job=sample_job,
        resume_version=master_version,
        cover_letter_version=None,
        screening_answers=screening_answers,
        simulate_bot_block=True,
        has_connected_email=False,
        company_email=None,
    )
    assert audit_tier3.bot_mitigation_tier == 3
    assert audit_tier3.channel == "candidate_handoff"
    assert audit_tier3.status == "handoff_ready"
    assert audit_tier3.handoff_bundle_url is not None
    assert audit_tier3.confirmation_code.startswith("HANDOFF-")


def test_ats_compliant_pdf_generation_and_text_extraction(sample_master_resume):
    """Verifies that generated PDF has single-column ATS layout and is cleanly extractable by pypdf."""
    from app.domain.pdf_generator import pdf_generator
    from app.domain.resume_parser import resume_parser

    pdf_bytes = pdf_generator.generate_resume_pdf(sample_master_resume)
    assert len(pdf_bytes) > 500

    extracted_text = resume_parser.extract_text_from_pdf_bytes(pdf_bytes)
    assert "Jane Doe" in extracted_text
    assert "Tech Corp" in extracted_text
    assert "Python" in extracted_text
    assert "50,000" in extracted_text
