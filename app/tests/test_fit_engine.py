"""Pure fit-engine tests: skill vocabulary, requirement extraction, gates, scoring, fixes."""

from app.domain.skills import find_skills


def test_find_skills_resolves_aliases():
    found = find_skills("5+ yrs Postgres, k8s and Node, plus C++ and Go (golang)")
    for skill in ("PostgreSQL", "Kubernetes", "Node.js", "C++", "Go"):
        assert skill in found


def test_find_skills_respects_word_boundaries_and_ambiguous_words():
    assert "React" not in find_skills("a reactive java service")
    assert "Java" in find_skills("a reactive java service")
    assert "JavaScript" not in find_skills("a reactive java service")
    assert "R" not in find_skills("our R&D team")
    assert "Go" not in find_skills("Go-to-market lead; go to the office")
    assert "C" not in find_skills("C++ only")


# --- Fit engine -----------------------------------------------------------------

from app.domain.fit import (  # noqa: E402
    APPLY_LINE,
    CandidateSnapshot,
    clean_jd,
    evaluate,
    extract_requirements,
    required_years,
)

JD = """
<h2>About the role</h2><p>We are hiring a Senior Backend Engineer to build our payments platform.</p>
<h3>What you have</h3>
<ul>
<li>5+ years of experience building backend services in Python</li>
<li>Strong experience with PostgreSQL and Docker</li>
<li>You have shipped REST APIs at scale</li>
</ul>
<h3>Nice to have</h3>
<ul><li>Kubernetes and Terraform are a plus</li></ul>
<p>Remote (US).</p>
"""


def cand(**kw):
    base = dict(
        role_titles=["Backend Engineer"],
        verified_skills={"Python", "PostgreSQL", "Docker", "REST APIs"},
        resume_skills=set(),
        declined_skills=set(),
        facts={"years_experience": 6, "work_mode": "remote_only"},
    )
    base.update(kw)
    return CandidateSnapshot(**base)


def test_clean_jd_strips_html_and_unescapes():
    assert clean_jd("&lt;p&gt;Hello&amp;nbsp;<b>world</b>&lt;/p&gt;") == "Hello world"


def test_requirements_get_importance_from_context():
    reqs = dict(extract_requirements("Senior Python Engineer", clean_jd(JD)))
    assert reqs["Python"] == "critical"          # in the title
    assert reqs["PostgreSQL"] == "high"          # "experience with"
    assert reqs["Kubernetes"] == "preferred"     # "nice to have / a plus"
    assert required_years(clean_jd(JD)) == 5


def test_strong_candidate_clears_the_apply_line():
    r = evaluate("Senior Backend Engineer", "Acme", "Remote (US)", JD, cand())
    assert r.score >= APPLY_LINE and r.verdict == "apply"
    assert not r.gates
    assert r.strengths


def test_unconfirmed_skills_score_lower_than_verified_and_gaps_lowest():
    verified = evaluate("Backend Engineer", "Acme", "Remote", JD, cand())
    unconfirmed = evaluate("Backend Engineer", "Acme", "Remote", JD, cand(
        verified_skills={"Python"}, resume_skills={"PostgreSQL", "Docker", "REST APIs"}))
    missing = evaluate("Backend Engineer", "Acme", "Remote", JD, cand(verified_skills={"Python"}))
    assert verified.score > unconfirmed.score > missing.score
    assert {r.skill: r.match for r in unconfirmed.requirements}["Docker"] == "unconfirmed"


def test_fix_gain_is_real():
    c = cand(verified_skills={"Python"}, resume_skills={"PostgreSQL", "Docker", "REST APIs"})
    r = evaluate("Backend Engineer", "Acme", "Remote", JD, c)
    top = r.fixes[0]
    assert top["kind"] == "confirm_skill" and top["gain"] > 0
    c.verified_skills.add(top["skill"])
    assert evaluate("Backend Engineer", "Acme", "Remote", JD, c).score == round(r.score + top["gain"], 1)


def test_declined_skills_are_not_offered_as_fixes():
    r = evaluate("Backend Engineer", "Acme", "Remote", JD, cand(verified_skills={"Python"}, declined_skills={"Docker"}))
    assert "Docker" not in [f["skill"] for f in r.fixes]


def _gated(**facts_and_kw):
    jd = facts_and_kw.pop("jd", JD)
    company = facts_and_kw.pop("company", "Acme")
    location = facts_and_kw.pop("location", "Remote")
    r = evaluate("Backend Engineer", company, location, jd, cand(facts={"years_experience": 6, **facts_and_kw}))
    assert r.score <= 2.0 and r.verdict == "skip"
    return r.gates


def test_hard_gates_cap_score():
    assert "blacklist" in _gated(blacklist_companies=["acme"])[0].lower()
    assert "on-call" in _gated(deal_breakers=["on-call"], jd=JD + "<p>Weekly on-call rotation.</p>")[0].lower()
    assert "sponsor" in _gated(needs_sponsorship=True, jd=JD + "<p>We are unable to sponsor visas.</p>")[0].lower()
    assert "onsite" in _gated(work_mode="remote_only", location="New York, NY", jd=JD.replace("Remote (US).", "This role is onsite in NYC."))[0].lower()
    assert "years" in _gated(years_experience=1)[0].lower()


def test_experience_and_role_dimensions():
    junior = evaluate("Backend Engineer", "Acme", "Remote", JD, cand(facts={"years_experience": 3}))
    assert junior.dimensions["experience"] < evaluate("Backend Engineer", "Acme", "Remote", JD, cand()).dimensions["experience"]
    off_role = evaluate("Account Executive", "Acme", "Remote", JD, cand())
    assert off_role.dimensions["role"] < 3


REAL_SHAPED_JD = """Who we are
About Acme
Acme is hiring! Our team loves high performance and our stakeholders use AWS and Kafka.
What you'll do
Build services in Go on Kubernetes.
Mentor engineers to help them grow
Who you are
Minimum requirements
2–12+ years of industry software engineering experience
Experience with PostgreSQL
Preferred qualifications
Terraform
Benefits
Free lunch and a Docker-themed hoodie."""


def test_sections_drive_importance_and_company_text_is_ignored():
    reqs = dict(extract_requirements("Backend Engineer", REAL_SHAPED_JD))
    assert reqs["PostgreSQL"] == "high"
    assert reqs["Terraform"] == "preferred"
    assert reqs["Kubernetes"] == "preferred"      # responsibilities without requirement wording
    for noise in ("AWS", "Kafka", "Hiring", "Performance", "Stakeholder Management", "Docker"):
        assert noise not in reqs, noise


def test_years_uses_lower_bound_and_needs_experience_context():
    assert required_years(REAL_SHAPED_JD) == 2
    assert required_years("Founded 12 years ago. 3+ years of Python experience.") == 3
    assert required_years("5-8 years experience building APIs") == 5


def test_thin_evidence_does_not_swing_the_skill_score():
    thin = "Requirements\nExperience with Database Design"
    r = evaluate("Full Stack Engineer", "Acme", "Remote", thin, cand(role_titles=["Full Stack Engineer"], verified_skills=set()))
    assert 2.0 < r.dimensions["skills"] < 3.0  # one missing skill is a signal, not a verdict
