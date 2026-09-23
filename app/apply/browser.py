"""Fill a real application form in a headless browser, and submit it only when told to.

One DOM scan tags every visible field (radio/checkbox groups become one question), the answer
engine decides each value, and a filler per field kind types, selects, checks or uploads it.
Values are read back from the page so the candidate reviews what was actually entered.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.apply.answers import ApplyContext, Field, answer, classify

SUCCESS = re.compile(r"thank you for (?:applying|your application)|application (?:has been |was )?(?:submitted|received)|"
                     r"we(?:'ve| have) received your application", re.I)
NAV_TIMEOUT_MS = 45_000
ACTION_TIMEOUT_MS = 8_000
SUBMIT_WAIT_MS = 15_000


@dataclass
class FillResult:
    status: str                      # needs_answers | ready | submitted | dry_run | handoff | failed
    fields: List[Dict[str, Any]] = field(default_factory=list)
    questions: List[Dict[str, Any]] = field(default_factory=list)
    captcha: bool = False
    message: str = ""


def resolve_apply_url(url: str, greenhouse_org: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """(ats, application-form URL) for Greenhouse/Lever/Ashby postings; None for anything else."""
    url = (url or "").strip()
    m = re.match(r"https?://jobs\.lever\.co/([^/?#]+)/([^/?#]+)", url)
    if m:
        return "lever", f"https://jobs.lever.co/{m.group(1)}/{m.group(2)}/apply"
    m = re.match(r"https?://jobs\.ashbyhq\.com/([^/?#]+)/([^/?#]+)", url)
    if m:
        return "ashby", f"https://jobs.ashbyhq.com/{m.group(1)}/{m.group(2)}/application"
    m = re.search(r"(?:job-)?boards\.greenhouse\.io/([^/?#]+)/jobs/(\d+)", url)
    org, job_id = (m.group(1), m.group(2)) if m else (greenhouse_org, None)
    if not job_id:
        jid = re.search(r"gh_jid=(\d+)", url)
        job_id = jid.group(1) if jid else None
    if org and job_id:
        return "greenhouse", f"https://job-boards.greenhouse.io/embed/job_app?for={org}&token={job_id}"
    return None


# Tags each visible field with data-ch-key and describes it; groups radios/checkboxes by name.
_SCAN_JS = r"""() => {
  const clean = (t) => (t || "").replace(/[*✱]/g, " ").replace(/\s+/g, " ").trim();
  // Rendered text (skips hidden helpers like "Couldn't auto-read resume"), minus nested controls' own text.
  const textOf = (node) => {
    let t = node.innerText || "";
    node.querySelectorAll("select,ul[role=listbox],button").forEach((n) => {
      const own = n.innerText || "";
      if (own.trim()) t = t.replace(own, "");
    });
    return t;
  };
  // Labels often carry helper/error text on later lines ("No location found..."): keep the first line.
  const firstLine = (t) => (t || "").split("\n").map((l) => l.trim()).find((l) => l) || "";
  const labelOf = (el) => {
    const by = el.getAttribute("aria-labelledby");
    if (by) { const n = document.getElementById(by.split(" ")[0]); if (n) return textOf(n); }
    if (el.labels && el.labels.length) return textOf(el.labels[0]);
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    const wrap = el.closest("label"); if (wrap) return textOf(wrap);
    return el.placeholder || "";
  };
  const optionLabel = (el) => clean((el.labels && el.labels.length) ? textOf(el.labels[0]) : (el.closest("label") ? textOf(el.closest("label")) : el.value));
  const groupLabel = (inputs) => {
    const opts = new Set(inputs.map(optionLabel));
    let node = inputs[0].parentElement;
    while (node && node !== document.body) {
      if (inputs.every((i) => node.contains(i))) {
        const line = (node.innerText || "").split("\n").map(clean).find((l) => l && !opts.has(l));
        if (line) return line;
      }
      node = node.parentElement;
    }
    return inputs[0].name || "";
  };
  const visible = (el) => el.type === "file" || !!(el.offsetParent || el.getClientRects().length);
  const required = (el, label) => el.required || el.getAttribute("aria-required") === "true" || /[*✱]/.test(label);
  const out = [], groups = {};
  let n = 0;
  for (const el of document.querySelectorAll("input, textarea, select")) {
    const type = (el.type || "").toLowerCase();
    if (type === "hidden" || type === "submit" || type === "button" || el.name === "g-recaptcha-response") continue;
    if (!visible(el)) continue;
    if (type === "radio" || type === "checkbox") {
      const name = el.name || ("__" + n);
      (groups[name] = groups[name] || []).push(el);
      continue;
    }
    const raw = firstLine(labelOf(el));
    if (!clean(raw)) continue;  // unlabeled helpers (e.g. react-select validators)
    const key = String(n++);
    el.setAttribute("data-ch-key", key);
    const isCombo = el.getAttribute("role") === "combobox" || el.hasAttribute("aria-autocomplete");
    const kind = el.tagName === "SELECT" ? "select" : el.tagName === "TEXTAREA" ? "textarea"
      : isCombo ? "combobox" : (["file", "email", "tel"].includes(type) ? type : "text");
    const options = el.tagName === "SELECT" ? [...el.options].map((o) => clean(o.text)).filter(Boolean) : [];
    out.push({ key, label: clean(raw), kind, required: required(el, raw), options, hint: el.id || el.name || "" });
  }
  for (const [name, inputs] of Object.entries(groups)) {
    const key = String(n++);
    inputs.forEach((i) => i.setAttribute("data-ch-key", key));
    const label = groupLabel(inputs);
    out.push({ key, label: clean(label), kind: inputs[0].type, options: inputs.map(optionLabel),
               required: inputs.some((i) => i.required) || /[*✱]/.test(label), hint: name });
  }
  return out;
}"""

_OPTION_LABEL_JS = r"""(el) => ((el.labels && el.labels[0] ? el.labels[0].innerText : (el.closest('label') || {}).innerText) || el.value || '')
  .replace(/[*✱]/g, ' ').replace(/\s+/g, ' ').trim()"""

_CAPTCHA_SELECTOR = ("iframe[src*='recaptcha'], iframe[title*='reCAPTCHA'], iframe[src*='hcaptcha'], "
                     ".g-recaptcha, .h-captcha, [data-sitekey]")


async def _combobox_options(page, key: str) -> List[str]:
    box = page.locator(f'[data-ch-key="{key}"]')
    try:
        await box.click()
        options: List[str] = []
        for wait_ms in (400, 1200):  # menus often render their options a beat after opening
            await page.wait_for_timeout(wait_ms)
            options = [t.strip() for t in await page.locator("[role=option]:visible").all_inner_texts() if t.strip()]
            if options:
                break
        await box.press("Escape")
        return options
    except Exception:
        return []


async def _fill(page, f: Field, value: Any) -> Optional[str]:
    """Fills one field; for dropdowns returns the option text actually clicked."""
    loc = page.locator(f'[data-ch-key="{f.key}"]')
    if f.kind in ("text", "email", "tel", "textarea"):
        await loc.first.fill(str(value))
    elif f.kind == "file":
        await loc.first.set_input_files(str(value))
    elif f.kind == "select":
        await loc.first.select_option(label=str(value))
    elif f.kind == "combobox":
        return await _fill_combobox(page, loc.first, str(value))
    elif f.kind in ("radio", "checkbox"):
        wanted = set(value if isinstance(value, list) else [value])
        for i in range(await loc.count()):
            member = loc.nth(i)
            if await member.evaluate(_OPTION_LABEL_JS) in wanted:
                await member.check(force=True)
    return None


async def _read_back(page, f: Field) -> Any:
    loc = page.locator(f'[data-ch-key="{f.key}"]')
    if f.kind == "select":
        return await loc.first.evaluate("(el) => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text.trim() : ''")
    if f.kind in ("radio", "checkbox"):
        picked = [await loc.nth(i).evaluate(_OPTION_LABEL_JS) for i in range(await loc.count()) if await loc.nth(i).is_checked()]
        return picked if f.kind == "checkbox" else (picked[0] if picked else "")
    if f.kind == "file":
        return await loc.first.evaluate("(el) => el.files && el.files[0] ? el.files[0].name : ''")
    if f.kind == "combobox":
        return await loc.first.evaluate(_COMBOBOX_VALUE_JS)
    return await loc.first.input_value()


# React-select style widgets clear the input and show the choice in a sibling "single-value" element.
_COMBOBOX_VALUE_JS = r"""(el) => {
  if (el.value) return el.value.trim();
  let node = el.parentElement;
  for (let i = 0; node && i < 4; i++, node = node.parentElement) {
    const shown = node.querySelector('[class*="single-value"], [class*="singleValue"]');
    if (shown && shown.innerText.trim()) return shown.innerText.trim();
  }
  return "";
}"""


async def _fill_combobox(page, box, value: str) -> str:
    """Pick `value` in a searchable dropdown: click it, else type to search and take the best option."""
    await box.click()
    await page.wait_for_timeout(250)
    exact = page.get_by_role("option", name=value, exact=True)
    if await exact.count():
        await exact.first.click()
        return value
    await box.fill("")
    await box.type(value.split(",")[0].strip(), delay=20)  # "London, UK" -> search "London"
    await page.wait_for_timeout(900)
    options = page.locator("[role=option]:visible")
    texts = [t.strip() for t in await options.all_inner_texts()]
    lowered = value.lower()
    token = lowered.split(",")[0].strip()
    best = next((i for i, t in enumerate(texts) if t.lower() == lowered), None)
    if best is None:
        best = next((i for i, t in enumerate(texts) if t.lower().startswith(token)), None)
    if best is None:
        best = next((i for i, t in enumerate(texts) if token in t.lower()), None)
    if best is None:  # never fall back to an arbitrary option: the candidate is asked instead
        raise LookupError(f"No option for {value!r}")
    await options.nth(best).click()
    return texts[best]


async def _screenshot(page, path: str) -> None:
    """Best effort: a slow web font must never fail the fill."""
    if not path:
        return
    try:
        await page.screenshot(path=path, full_page=True, timeout=30_000, animations="disabled")
    except Exception:
        pass


async def _submit(page, captcha: bool) -> Tuple[str, str]:
    button = page.locator("button[type=submit], input[type=submit]")
    if not await button.count():
        button = page.get_by_role("button", name=re.compile(r"submit|apply", re.I))
    await button.first.click()
    waited = 0
    while waited < SUBMIT_WAIT_MS:
        await page.wait_for_timeout(500)
        waited += 500
        if SUCCESS.search(await page.inner_text("body")):
            return "submitted", "Application submitted."
    if captcha:
        return "handoff", "The site asked for a CAPTCHA check. Open the application to finish — your answers are ready to paste."
    return "failed", "The site did not confirm the submission. Open the application to check it."


async def run_fill(url: str, ctx: ApplyContext, submit: bool = False, screenshot_path: str = "") -> FillResult:
    """Fill the form at `url`; with submit=True and nothing left to ask, click submit and confirm."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(ACTION_TIMEOUT_MS)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if response is not None and response.status >= 400:
                return FillResult("handoff", message=f"The posting is no longer available ({response.status}).")
            await page.wait_for_timeout(1500)  # client-rendered forms (Ashby, Greenhouse embeds)
            if await page.locator("input[type=password]:visible").count():
                return FillResult("handoff", message="This site needs you to sign in before applying.")

            fields = [Field(**raw) for raw in await page.evaluate(_SCAN_JS)]
            for f in fields:
                if f.kind == "combobox":
                    f.options = await _combobox_options(page, f.key)
            captcha = await page.locator(_CAPTCHA_SELECTOR).count() > 0

            forbidden = [f.label for f in fields if f.required and classify(f.label, f.kind, hint=f.hint) == "forbidden"]
            if forbidden:
                return FillResult("handoff", captcha=captcha, message=(
                    f"The form asks for {forbidden[0]}. We never enter that for you — please apply directly."))

            filled, questions = [], []
            for f in fields:
                a = answer(f, ctx)
                if a.value in (None, "", []) or a.source == "forbidden":
                    if f.required:
                        questions.append({"key": f.key, "label": f.label, "kind": f.kind,
                                          "options": f.options, "required": True})
                    continue
                try:
                    picked = await _fill(page, f, a.value)
                    shown = await _read_back(page, f)
                    if shown in ("", [], None):
                        raise ValueError("value did not stick")  # never report a blank as filled
                    if picked and shown not in picked and picked not in shown:
                        # e.g. a phone-country widget still showing "+1" after "United Kingdom +44" was clicked
                        raise ValueError(f"widget shows {shown!r}, not the chosen {picked!r}")
                    filled.append({"label": f.label, "kind": f.kind, "source": a.source, "required": f.required,
                                   "value": shown})
                except Exception:
                    if f.required:
                        questions.append({"key": f.key, "label": f.label, "kind": f.kind,
                                          "options": f.options, "required": True})

            await _screenshot(page, screenshot_path)
            if questions:
                return FillResult("needs_answers", filled, questions, captcha,
                                  f"{len(questions)} question(s) need your answer.")
            if not submit:
                return FillResult("ready", filled, [], captcha, "Everything is filled in. Review and approve to submit.")
            status, message = await _submit(page, captcha)
            await _screenshot(page, screenshot_path)
            return FillResult(status, filled, [], captcha, message)
        finally:
            await browser.close()
