"""Decide what goes into each application-form field — and what must be asked instead.

Pure functions, no browser. The rule is honesty: answer only from the candidate's own profile,
facts, or answers they gave before; decline demographic questions; never guess eligibility.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

Value = Union[str, List[str], None]


@dataclass
class Field:
    key: str            # stable locator from the page scan
    label: str
    kind: str           # text | email | tel | textarea | file | select | radio | checkbox | combobox | buttons
    required: bool
    options: List[str] = field(default_factory=list)
    hint: str = ""      # element id/name, e.g. Greenhouse's resume input is labelled just "Attach"


@dataclass
class ApplyContext:
    profile: Dict[str, str]   # full_name, email, phone, location, country, current_company, linkedin, github, website
    facts: Dict[str, Any]
    memory: Dict[str, Value]  # question_key(label) -> the candidate's earlier answer
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None


@dataclass
class Answer:
    value: Value
    source: str  # profile | facts | memory | file | default | decline | forbidden | none


# Order matters: first match wins.
_RULES = [
    ("forbidden", r"social security|\bssn\b|national (?:id|insurance)|passport|date of birth|\bdob\b|"
                  r"bank|credit card|card number|\biban\b|routing number|driver'?s licen[cs]e"),
    ("cover_letter", r"cover letter"),
    ("resume", r"\bresume\b|\bcv\b|curriculum vitae"),
    ("eeo", r"gender|race|ethnicity|hispanic|latino|veteran|disability|disabled|lgbt|sexual orientation|transgender"),
    ("pronouns", r"pronoun"),
    ("sponsorship", r"sponsor"),
    ("how_heard", r"how did you (?:hear|find)|where did you (?:hear|find)|referral source"),
    ("linkedin", r"linkedin"),
    ("github", r"github"),
    ("website", r"website|portfolio|personal site|\bblog\b"),
    ("email", r"e-?mail"),
    ("phone", r"phone|mobile"),
    ("first_name", r"first name|given name|preferred name"),
    ("last_name", r"last name|family name|surname"),
    ("full_name", r"full name|legal name|^name$|your name"),
    ("current_company", r"current (?:company|employer)|most recent (?:company|employer)"),
    ("country", r"^country"),
    ("location", r"location|\bcity\b|where are you (?:based|located)"),
]
# "Are you authorized/eligible to work ... without sponsorship?" is the OPPOSITE polarity of
# "Do you require sponsorship?", and is country-specific: never auto-answer it.
_ELIGIBILITY = re.compile(r"authori[sz]ed|eligib|without (?:\w+ )?sponsorship|right to work", re.I)
_DECLINE = re.compile(r"decline|prefer not|don.?t wish|do not wish|not to (?:answer|disclose|say|self)|"
                      r"choose not|rather not|i don.?t want", re.I)


def _clean(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*✱]", " ", label or "")).strip()


def question_key(label: str) -> str:
    """Normalized question text used to remember the candidate's answers across applications."""
    return " ".join(re.findall(r"[a-z0-9]+", _clean(label).lower()))


def classify(label: str, kind: str = "text", options: Optional[List[str]] = None, hint: str = "") -> Optional[str]:
    if _ELIGIBILITY.search(_clean(label)):
        return None
    for text in (_clean(label).lower(), re.sub(r"[_\-]+", " ", hint or "").lower()):
        for key, pattern in _RULES:
            if text and re.search(pattern, text):
                if key in ("resume", "cover_letter") and kind not in ("file", "textarea"):
                    continue  # e.g. "Tell us about your resume" as a yes/no question
                return key
    return None


def pick(options: List[str], wanted: str) -> Optional[str]:
    """The option matching `wanted`: exact, then prefix, then substring (case-insensitive)."""
    real = [o for o in options if o and not o.lower().startswith("select")]
    low = wanted.lower()
    for test in (lambda o: o.lower() == low, lambda o: o.lower().startswith(low), lambda o: low in o.lower()):
        hit = next((o for o in real if test(o)), None)
        if hit:
            return hit
    return None


def _from_profile(key: str, profile: Dict[str, str]) -> Optional[str]:
    full = (profile.get("full_name") or "").strip()
    if key == "first_name":
        return full.split()[0] if full else None
    if key == "last_name":
        return full.split()[-1] if len(full.split()) > 1 else None
    return (profile.get(key) or "").strip() or None


def answer(f: Field, ctx: ApplyContext) -> Answer:
    remembered = ctx.memory.get(question_key(f.label))
    if remembered not in (None, "", []):
        return Answer(remembered, "memory")

    key = classify(f.label, f.kind, f.options, f.hint)
    if key == "forbidden":
        return Answer(None, "forbidden")
    if key == "resume":
        return Answer(ctx.resume_path, "file") if ctx.resume_path else Answer(None, "none")
    if key == "cover_letter":
        path = ctx.cover_letter_path if f.kind == "file" else None
        return Answer(path, "file") if path else Answer(None, "none")
    if key in ("eeo", "pronouns"):
        decline = next((o for o in f.options if _DECLINE.search(o)), None)
        return Answer(decline, "decline") if decline else Answer(None, "none")
    if key == "sponsorship":
        needs = ctx.facts.get("needs_sponsorship")
        if needs is None:
            return Answer(None, "none")
        wanted = "Yes" if needs else "No"
        return Answer(pick(f.options, wanted) if f.options else wanted, "facts")
    if key == "how_heard":
        if f.options:
            for wanted in ("job board", "online", "website", "internet", "other"):
                hit = pick(f.options, wanted)
                if hit:
                    return Answer(hit, "default")
            return Answer(None, "none")
        return Answer("Job board", "default")
    if key in ("country", "location") and f.options:
        for wanted in (ctx.profile.get("country") or "", ctx.profile.get("location") or ""):
            hit = pick(f.options, wanted) if wanted else None
            if hit:
                return Answer(hit, "profile")
        return Answer(None, "none")
    if key:
        value = _from_profile(key, ctx.profile)
        return Answer(value, "profile") if value else Answer(None, "none")
    return Answer(None, "none")
