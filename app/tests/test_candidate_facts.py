import pytest

from app.domain.candidate_facts import (
    FACT_QUESTIONS,
    completeness,
    get_facts,
    next_question,
    update_facts,
)


def test_questions_have_prompts_and_kinds():
    ids = [q["id"] for q in FACT_QUESTIONS]
    assert ids[:2] == ["years_experience", "seniority"]
    assert all(q["prompt"] and q["kind"] in {"choice", "multi", "text", "number", "list", "bool"} for q in FACT_QUESTIONS)


@pytest.mark.asyncio
async def test_facts_flow_one_question_at_a_time(db_session, sample_tenant):
    facts = await get_facts(db_session, sample_tenant.id)
    assert facts == {}
    assert next_question(facts)["id"] == "years_experience"

    facts = await update_facts(db_session, sample_tenant.id, {"years_experience": 6})
    assert next_question(facts)["id"] == "seniority"
    assert completeness(facts) == (1, len(FACT_QUESTIONS))

    facts = await update_facts(db_session, sample_tenant.id, {"deal_breakers": [" on-call ", "on-call", ""]})
    assert facts["deal_breakers"] == ["on-call"]
    assert (await get_facts(db_session, sample_tenant.id))["years_experience"] == 6


@pytest.mark.asyncio
async def test_facts_validation(db_session, sample_tenant):
    with pytest.raises(ValueError):
        await update_facts(db_session, sample_tenant.id, {"favourite_colour": "teal"})
    with pytest.raises(ValueError):
        await update_facts(db_session, sample_tenant.id, {"needs_sponsorship": "maybe"})
    with pytest.raises(ValueError):
        await update_facts(db_session, sample_tenant.id, {"work_mode": "moon"})
    with pytest.raises(ValueError):
        await update_facts(db_session, sample_tenant.id, {"years_experience": -2})


@pytest.mark.asyncio
async def test_skipped_questions_are_not_asked_again(db_session, sample_tenant):
    facts = await update_facts(db_session, sample_tenant.id, {"skipped": ["years_experience"]})
    assert next_question(facts)["id"] == "seniority"
