"""Tests for Resume Intake & Skill Extraction meeting AT-06 and ON-03 specifications."""

import pytest

from app.domain.resume_parser import resume_parser


@pytest.mark.asyncio
async def test_at06_parsed_skills_never_auto_marked_verified(db_session, sample_tenant):
    """AT-06: Parsed skills are NEVER auto-marked verified until user explicitly confirms."""
    resume_text = """
    Senior Software Engineer with 8 years of experience.
    Core competencies: Python, Docker, PostgreSQL, React, and Kubernetes.
    - Designed distributed API gateways handling 10M requests/day, reducing latency by 45%.
    - Led cloud migration to AWS saving $250k in annual infrastructure expenses.
    """

    # Parse resume
    parsed = await resume_parser.parse_resume_text(
        session=db_session,
        tenant_id=sample_tenant.id,
        filename="senior_engineer_resume.pdf",
        content=resume_text,
    )

    # 1. Verify skills were found
    assert len(parsed.extracted_skills) >= 4

    # 2. Strict AT-06 check: ALL extracted skills must be unverified initially
    assert all(skill["verified"] is False for skill in parsed.extracted_skills)

    # 3. User explicitly confirms Python
    updated = await resume_parser.confirm_skill(
        session=db_session,
        tenant_id=sample_tenant.id,
        parse_id=parsed.id,
        skill_name="Python",
    )

    # Only Python is verified; others remain unverified
    python_skill = next(s for s in updated.extracted_skills if s["name"] == "Python")
    docker_skill = next(s for s in updated.extracted_skills if s["name"] == "Docker")
    assert python_skill["verified"] is True
    assert docker_skill["verified"] is False


@pytest.mark.asyncio
async def test_on03_scanned_pdf_path_degrades_gracefully(db_session, sample_tenant):
    """ON-03: Scanned image PDF or low-character text degrades gracefully with confidence warning."""
    scanned_image_text = "Page 1. Scan image."  # <50 characters

    parsed = await resume_parser.parse_resume_text(
        session=db_session,
        tenant_id=sample_tenant.id,
        filename="scanned_resume.pdf",
        content=scanned_image_text,
    )

    # Confidence must drop below 0.8 for human-confirmation review
    assert parsed.confidence_score < 0.8
    assert parsed.confidence_score == 0.3
