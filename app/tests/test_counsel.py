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
