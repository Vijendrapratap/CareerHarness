"""Answer engine: classify real ATS labels and answer only what the candidate's data supports."""

import pytest

from app.apply.answers import ApplyContext, Field, answer, classify, question_key

CTX = ApplyContext(
    profile={"full_name": "Ada Lovelace", "email": "ada@example.com", "phone": "+44 20 7946 0000",
             "location": "London, UK", "country": "United Kingdom", "current_company": "Babbage Labs",
             "linkedin": "https://linkedin.com/in/ada", "github": "", "website": "https://ada.dev"},
    facts={"needs_sponsorship": False},
    memory={question_key("Why do you want to work at Discord?*"): "I love building for communities."},
    resume_path="/tmp/resume.pdf",
)


@pytest.mark.parametrize("label,kind,expected", [
    ("First Name*", "text", "first_name"),
    ("Last Name*", "text", "last_name"),
    ("Full name ✱", "text", "full_name"),
    ("Legal Name", "text", "full_name"),
    ("Email*", "email", "email"),
    ("Phone ✱", "tel", "phone"),
    ("Location (City)*", "text", "location"),
    ("Current location ✱", "text", "location"),
    ("Country*", "combobox", "country"),
    ("Current company ✱", "text", "current_company"),
    ("LinkedIn Profile", "text", "linkedin"),
    ("GitHub URL", "text", "github"),
    ("Portfolio URL", "text", "website"),
    ("Resume/CV ✱ ATTACH RESUME/CV", "file", "resume"),
    ("Cover Letter", "file", "cover_letter"),
    ("How did you hear about this job?", "text", "how_heard"),
    ("Will you now or in the future require visa sponsorship?", "combobox", "sponsorship"),
    ("Veteran Status*", "combobox", "eeo"),
    ("Race and Ethnicity*", "combobox", "eeo"),
    ("Pronouns", "radio", "pronouns"),
    ("Social Security Number", "text", "forbidden"),
    ("Date of birth", "text", "forbidden"),
    ("Why do you want to work at Discord?*", "textarea", None),
    ("Are you legally authorized to work in the United States?", "combobox", None),
])
def test_classify_real_labels(label, kind, expected):
    assert classify(label, kind) == expected


def f(label, kind="text", required=True, options=None):
    return Field(key=label, label=label, kind=kind, required=required, options=options or [])


def test_profile_answers_split_name_and_attach_resume():
    assert answer(f("First Name*"), CTX).value == "Ada"
    assert answer(f("Last Name*"), CTX).value == "Lovelace"
    assert answer(f("Resume", "file"), CTX).value == "/tmp/resume.pdf"
    assert answer(f("Email*", "email"), CTX).source == "profile"


def test_missing_profile_value_is_not_invented():
    assert answer(f("GitHub URL"), CTX).value is None


def test_sponsorship_follows_facts_and_picks_the_option():
    a = answer(f("Do you require visa sponsorship?", "select", options=["Select...", "Yes", "No"]), CTX)
    assert a.value == "No" and a.source == "facts"
    unknown = ApplyContext(profile=CTX.profile, facts={}, memory={}, resume_path=None)
    assert answer(f("Do you require visa sponsorship?", "select", options=["Yes", "No"]), unknown).value is None


def test_eeo_always_declines():
    a = answer(f("Gender*", "combobox", options=["Male", "Female", "Decline To Self Identify"]), CTX)
    assert a.value == "Decline To Self Identify" and a.source == "decline"
    b = answer(f("Veteran", "radio", options=["I am a veteran", "I am not a veteran", "I don't wish to answer"]), CTX)
    assert b.value == "I don't wish to answer"
    no_decline = answer(f("Gender*", "combobox", options=["Male", "Female"]), CTX)
    assert no_decline.value is None  # required with no decline option -> the candidate must answer


def test_memory_answers_custom_questions_and_legal_ones_are_asked():
    assert answer(f("Why do you want to work at Discord? *", "textarea"), CTX).value == "I love building for communities."
    assert answer(f("Are you legally authorized to work in the United States?", "combobox",
                    options=["Yes", "No"]), CTX).value is None


def test_how_heard_and_country_options():
    assert answer(f("How did you hear about us?", "select", options=["LinkedIn", "Job board", "Referral"]), CTX).value == "Job board"
    assert answer(f("Country*", "combobox", options=["United States", "United Kingdom", "India"]), CTX).value == "United Kingdom"


def test_forbidden_field_is_flagged():
    assert answer(f("Social Security Number"), CTX).source == "forbidden"
