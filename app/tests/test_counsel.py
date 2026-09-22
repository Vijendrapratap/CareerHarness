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


@pytest.mark.asyncio
async def test_priority_role_custom_role_does_not_exceed_cap(db_session, sample_tenant):
    await record_answer(db_session, sample_tenant.id, "linkedin", "https://linkedin.com/in/ada", "text")
    await record_answer(db_session, sample_tenant.id, "resume", "resume-1", "text")
    # target_work generates 3 suggestions
    res = await record_answer(db_session, sample_tenant.id, "target_work", "senior backend engineer with python and go", "text")
    assert res["step"] == "priority_role"
    # Select a custom role that is NOT in suggestions
    res_prio = await record_answer(db_session, sample_tenant.id, "priority_role", "custom_director_role", "text")
    assert res_prio["step"] == "management"
    assert "history" in res_prio
    assert len(res_prio["history"]) == 4
