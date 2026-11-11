"""Security layer: input screening, output sanitising and number grounding.

Defences against prompt injection and made-up numbers:
1. User questions are length-capped and screened for injection phrases; flagged text is still answered,
   but wrapped and labelled as untrusted data, and the attempt is logged.
2. Every string a tool returns passes an allowlist (IDs, labels, dates), so text hidden in data fields
   can never reach a model as instructions.
3. Every number an agent writes must match a number its tools returned (grounding check).
"""
import re
from dataclasses import dataclass, field

from .settings import MAX_QUESTION_CHARS

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"disregard (the |your )?(system|previous|above)",
    r"(system|developer) prompt",
    r"you are now", r"act as", r"pretend (to be|you)", r"jailbreak", r"\bDAN\b",
    r"reveal (your|the) (instructions|prompt|key|secrets?)",
    r"api[_ -]?key", r"sk-[a-z0-9_-]{8,}",
    r"mark (all|every|everything).{0,30}(normal|safe)",
    r"<\s*/?\s*(system|assistant|tool)\s*>", r"```\s*system",
    r"(run|execute|eval)\s*\(", r"import os", r"rm -rf",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Strings allowed out of tools: IDs, names, dates, labels and short notes, from a limited character set.
_SAFE_TEXT_RE = re.compile(r"^[A-Za-z0-9 ._:;%/()+\-–≤≥<>=°×,'\"]{0,240}$")
_TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z]")


@dataclass
class ScreenResult:
    text: str
    flagged: bool
    reasons: list = field(default_factory=list)


def screen_user_text(text: str) -> ScreenResult:
    """Cap length, strip control characters and flag likely prompt-injection attempts."""
    reasons = []
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text or "").strip()
    if len(text) > MAX_QUESTION_CHARS:
        text = text[:MAX_QUESTION_CHARS]
        reasons.append(f"truncated to {MAX_QUESTION_CHARS} characters")
    hits = sorted({m.group(0).lower() for m in _INJECTION_RE.finditer(text)})
    if hits:
        reasons.append("possible prompt injection: " + ", ".join(hits[:3]))
    return ScreenResult(text, bool(hits), reasons)


def wrap_untrusted(text: str) -> str:
    """Put user text inside clear data markers the system prompt tells agents never to obey."""
    return f"<user_question>\n{text}\n</user_question>"


def sanitize(value):
    """Recursively clean tool output: unsafe strings are replaced, so data can't carry instructions."""
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        safe = _SAFE_TEXT_RE.match(value) and not _TAG_RE.search(value) and not _INJECTION_RE.search(value)
        return value if safe else "[removed: unsafe text]"
    return value


# --------------------------------------------------------------------------- grounding
_NUMBER_RE = re.compile(r"(?<![A-Za-z\-\d.])[-+]?\d+(?:\.\d+)?(?![A-Za-z\d])")
_ID_NUMBER_RE = re.compile(r"\b(?:B787|ENG|Tool|BR-V2|Station)-[\w-]+", re.IGNORECASE)


_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d{3}\b)")


def _numbers_in(obj, out: set):
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for n in _NUMBER_RE.findall(_THOUSANDS_RE.sub("", _ID_NUMBER_RE.sub(" ", obj))):
            out.add(float(n))


def ungrounded_numbers(text: str, tool_outputs: list) -> list:
    """Numbers in `text` that don't match any tool-output number (as-is, as a %, or rounded)."""
    known = set()
    for o in tool_outputs:
        _numbers_in(o, known)
    candidates = set(known)
    for k in known:
        candidates |= {k * 100, k / 100, abs(k), abs(k) * 100}
    cleaned = _THOUSANDS_RE.sub("", _ID_NUMBER_RE.sub(" ", text))
    bad = []
    for raw in _NUMBER_RE.findall(cleaned):
        n = abs(float(raw))
        if n <= 12 and float(n).is_integer():      # small counts, ranks, months: too noisy to police
            continue
        if 2020 <= n <= 2030:                      # years
            continue
        if not any(abs(n - c) <= max(0.051, 0.006 * abs(c)) or round(c) == n for c in candidates):
            bad.append(raw)
    return sorted(set(bad))
