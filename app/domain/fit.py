"""Job fit engine: scores one job description against one candidate, deterministically.

Order of evaluation (after career-ops / AI-Job-Search):
1. Hard gates (blacklist, deal-breakers, sponsorship, onsite vs remote-only, big seniority gap)
   cap the score at 2.0 — a mismatch no resume edit can fix.
2. A requirement table is extracted from the JD *before* looking at the candidate:
   each skill gets an importance (critical / high / preferred) from where it appears.
3. Each requirement is matched: verified (candidate confirmed) / unconfirmed (only in the
   resume text) / gap. Unconfirmed counts half — confirming it is the candidate's fix.
4. Dimension scores (1-5) are combined with fixed weights in code, never by an LLM, so
   "what if I confirm Docker?" can be simulated instantly and shown as a gain.
"""

import html
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.domain.skills import find_skills

APPLY_LINE = 4.0
STRETCH_LINE = 3.5
GATED_CAP = 2.0
MAX_REQUIREMENTS = 12
FULL_EVIDENCE_WEIGHT = 6
WEIGHTS = {"skills": 0.45, "experience": 0.20, "role": 0.20, "logistics": 0.15}

_IMPORTANCE_WEIGHT = {"critical": 3, "high": 2, "preferred": 1}
_IMPORTANCE_RANK = {"critical": 0, "high": 1, "preferred": 2}
_MATCH_CREDIT = {"verified": 1.0, "unconfirmed": 0.5, "gap": 0.0}

_PREFERRED_WORDS = re.compile(r"nice to have|nice-to-have|preferred|bonus|\ba plus\b|\bplus\b|ideally|familiarity", re.I)
_REQUIRED_WORDS = re.compile(
    r"required|requirement|must|you have|you've|experience (?:with|in|building)|proficien|expertise|"
    r"strong|solid|qualifications|years of|deep knowledge|hands-on",
    re.I,
)
# "5+ years of experience", "2–12+ years of industry experience": lower bound, experience context only.
_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*)?years?\b[^.\n]{0,50}?experience", re.I
)
# Section headings decide what a line means. Company/benefits text never yields requirements.
_SECTION_PATTERNS = [
    ("preferred", re.compile(r"nice to have|nice-to-have|preferred|bonus|pluses|extra credit", re.I)),
    ("required", re.compile(r"requirement|qualification|who you are|what you (?:bring|have|need)|about you|"
                            r"you (?:have|bring)|must have|looking for|skills", re.I)),
    ("duties", re.compile(r"what you.?ll do|responsibilit|the role|in this role|you will|day[- ]to[- ]day|"
                          r"what you.?ll work on|your impact", re.I)),
    ("other", re.compile(r"about (?:us|the (?:company|team))|^about |who we are|benefit|perks|compensation|"
                         r"salary|equal opportunity|eeo|why (?:join|work)|life at|our (?:team|mission|values)|"
                         r"how we work|pay transparency|accommodation", re.I)),
]
_NO_SPONSORSHIP = re.compile(
    r"(?:unable|not able|cannot|can't|won't|will not|do not|don't)\s+(?:to\s+)?(?:provide\s+)?sponsor|"
    r"no (?:visa )?sponsorship|without (?:visa )?sponsorship|sponsorship is not available|"
    r"must be (?:legally )?authori[sz]ed|citizens? only|must be a (?:u\.?s\.? )?citizen|security clearance",
    re.I,
)
_REMOTE = re.compile(r"\bremote\b|work from home|distributed team|anywhere", re.I)
_ONSITE = re.compile(r"\bon-?site\b|in[- ]office|in the office|office-based|\bhybrid\b", re.I)
_SENIORITY = {"senior", "sr", "staff", "principal", "junior", "jr", "lead", "head", "i", "ii", "iii", "iv"}
_STOP = {"of", "and", "the", "a", "an", "for", "to", "in", "with", "&", "-"}


@dataclass
class CandidateSnapshot:
    role_titles: List[str]
    verified_skills: Set[str]
    resume_skills: Set[str]
    declined_skills: Set[str] = field(default_factory=set)
    facts: dict = field(default_factory=dict)


@dataclass
class Requirement:
    skill: str
    importance: str
    match: str


@dataclass
class FitReport:
    score: float
    verdict: str
    dimensions: Dict[str, float]
    requirements: List[Requirement]
    gates: List[str]
    strengths: List[str]
    gaps: List[str]
    fixes: List[dict]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "dimensions": self.dimensions,
            "requirements": [r.__dict__ for r in self.requirements],
            "gates": self.gates,
            "strengths": self.strengths,
            "gaps": self.gaps,
            "fixes": self.fixes,
        }


def clean_jd(text: str) -> str:
    """Plain text from escaped or raw HTML job descriptions (Greenhouse double-escapes)."""
    text = html.unescape(html.unescape(text or ""))
    text = re.sub(r"<\s*(?:br|/p|/li|/h\d|/div|li|p|h\d|div)[^>]*>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def required_years(jd: str) -> Optional[int]:
    years = [int(m.group(1)) for m in _YEARS.finditer(jd) if 0 < int(m.group(1)) <= 20]
    return max(years) if years else None


def _heading_section(line: str) -> Optional[str]:
    """Section a short heading line opens, or None when the line isn't a recognised heading."""
    if len(line.split()) > 6 or find_skills(line):
        return None
    return next((name for name, pattern in _SECTION_PATTERNS if pattern.search(line)), None)


def extract_requirements(title: str, jd: str) -> List[Tuple[str, str]]:
    """(skill, importance) pairs, most important first, from the JD text alone."""
    found: Dict[str, str] = {skill: "critical" for skill in find_skills(title)}
    section = None  # None until the first heading: many JDs have none
    for line in jd.splitlines():
        heading = _heading_section(line)
        if heading:
            section = heading
            continue
        if section == "other":
            continue
        if section == "preferred" or _PREFERRED_WORDS.search(line):
            importance = "preferred"
        elif section == "required" or _REQUIRED_WORDS.search(line):
            importance = "high"
        else:
            importance = "preferred"
        for skill in find_skills(line):
            if skill not in found or _IMPORTANCE_RANK[importance] < _IMPORTANCE_RANK[found[skill]]:
                found[skill] = importance
    ordered = sorted(found.items(), key=lambda kv: _IMPORTANCE_RANK[kv[1]])
    return ordered[:MAX_REQUIREMENTS]


def _title_words(title: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z0-9+#.]+", title.lower())} - _SENIORITY - _STOP


def _role_score(title: str, role_titles: List[str]) -> Tuple[float, str]:
    """Score for the closest target role (priority role wins ties), and that role's title."""
    job_words = _title_words(title)
    best, best_role = 0.0, ""
    for role in role_titles:
        words = _title_words(role)
        overlap = len(words & job_words) / len(words) if words else 0.0
        if overlap > best:
            best, best_role = overlap, role
    return (5.0 if best >= 1 else 4.0 if best >= 0.5 else 3.0 if best > 0 else 2.0), best_role


def _experience_score(needed: Optional[int], have: Optional[int]) -> float:
    if needed is None or have is None:
        return 3.5
    short = needed - have
    return 5.0 if short <= 0 else 4.0 if short == 1 else 3.0 if short == 2 else 2.0


def _is_remote(location: str, jd: str) -> bool:
    return bool(_REMOTE.search(location) or _REMOTE.search(jd))


def _is_onsite_only(location: str, jd: str) -> bool:
    return not _is_remote(location, jd) and bool(_ONSITE.search(jd) or location.strip())


def _logistics_score(location: str, jd: str, facts: dict) -> float:
    wanted = [loc.lower() for loc in facts.get("locations") or []]
    if _is_remote(location, jd) or facts.get("work_mode") == "any":
        return 5.0
    if wanted and any(w in location.lower() for w in wanted):
        return 5.0
    return 3.5 if not location.strip() else 2.5


def _gates(company: str, location: str, jd: str, facts: dict, needed_years: Optional[int]) -> List[str]:
    gates = []
    if company.lower() in {c.lower() for c in facts.get("blacklist_companies") or []}:
        gates.append(f"{company} is on your company blacklist")
    for phrase in facts.get("deal_breakers") or []:
        if phrase and phrase.lower() in jd.lower():
            gates.append(f"Deal-breaker in the description: {phrase}")
    if facts.get("needs_sponsorship") and _NO_SPONSORSHIP.search(jd):
        gates.append("You need visa sponsorship but this role won't sponsor")
    if facts.get("work_mode") == "remote_only" and _is_onsite_only(location, jd):
        gates.append("Onsite/hybrid role, but you want remote only")
    have = facts.get("years_experience")
    if needed_years is not None and have is not None and needed_years >= have + 4:
        gates.append(f"Requires {needed_years}+ years of experience; you have {have}")
    return gates


def _score(requirements: List[Requirement], other_dims: Dict[str, float], gated: bool) -> Tuple[float, Dict[str, float]]:
    skills = 3.0  # neutral when the JD names no skills
    if requirements:
        total = sum(_IMPORTANCE_WEIGHT[r.importance] for r in requirements)
        earned = sum(_IMPORTANCE_WEIGHT[r.importance] * _MATCH_CREDIT[r.match] for r in requirements)
        # Few requirements = thin evidence: lean toward neutral (full weight from ~3 high-importance skills).
        confidence = min(1.0, total / FULL_EVIDENCE_WEIGHT)
        skills = 3.0 + (1 + 4 * earned / total - 3.0) * confidence
    dims = {"skills": round(skills, 1), **other_dims}
    score = sum(WEIGHTS[k] * v for k, v in {"skills": skills, **other_dims}.items())
    if gated:
        score = min(score, GATED_CAP)
    return round(score, 1), dims


def _verdict(score: float) -> str:
    return "apply" if score >= APPLY_LINE else "stretch" if score >= STRETCH_LINE else "skip"


def evaluate(title: str, company: str, location: str, jd: str, cand: CandidateSnapshot) -> FitReport:
    text = clean_jd(jd)
    facts = cand.facts or {}
    needed = required_years(text)

    def match(skill: str) -> str:
        if skill in cand.verified_skills:
            return "verified"
        return "unconfirmed" if skill in cand.resume_skills else "gap"

    requirements = [Requirement(s, imp, match(s)) for s, imp in extract_requirements(title, text)]
    gates = _gates(company, location, text, facts, needed)
    role_score, matched_role = _role_score(title, cand.role_titles)
    other = {
        "experience": _experience_score(needed, facts.get("years_experience")),
        "role": role_score,
        "logistics": _logistics_score(location, text, facts),
    }
    score, dims = _score(requirements, other, bool(gates))

    fixes = []
    for req in requirements:
        if req.match == "verified" or req.skill in cand.declined_skills:
            continue
        simulated = [Requirement(r.skill, r.importance, "verified" if r is req else r.match) for r in requirements]
        gain = round(_score(simulated, other, bool(gates))[0] - score, 1)
        if gain > 0:
            fixes.append({"kind": "confirm_skill", "skill": req.skill, "importance": req.importance,
                          "in_resume": req.match == "unconfirmed", "gain": gain})
    fixes.sort(key=lambda f: -f["gain"])

    strong = [r.skill for r in requirements if r.match == "verified" and r.importance != "preferred"]
    strengths = []
    if strong:
        strengths.append("Verified: " + ", ".join(strong[:4]))
    if other["role"] >= 4:
        strengths.append(f"Title matches your target role: {matched_role}")
    if other["logistics"] >= 5:
        strengths.append("Remote or in one of your locations")
    unconfirmed = [r.skill for r in requirements if r.match == "unconfirmed" and r.importance != "preferred"]
    missing = [r.skill for r in requirements if r.match == "gap" and r.importance != "preferred"]
    gaps = []
    if unconfirmed:
        gaps.append("In your resume but not confirmed: " + ", ".join(unconfirmed[:4]))
    if missing:
        gaps.append("Missing: " + ", ".join(missing[:4]))
    if other["experience"] <= 3 and needed is not None:
        gaps.append(f"Asks for {needed}+ years of experience")

    return FitReport(
        score=score,
        verdict="skip" if gates else _verdict(score),
        dimensions=dims,
        requirements=requirements,
        gates=gates,
        strengths=strengths[:3],
        gaps=gaps[:3],
        fixes=fixes[:5],
    )
