"""Reader-facing content checks.

The structural guarantee is the schema: the model only fills content fields, so pipeline
status has nowhere to go. These checks are a backstop for the two failure modes that shipped
before (source-gap narration, production chatter) plus link provenance for new editions.
"""
import re

from bs4 import BeautifulSoup

# Phrases that describe how the newsletter was produced or which sources had nothing.
# Narrow on purpose: "quietly shipped" and "a quiet launch" are legitimate copy.
LEAK_PATTERNS = [
    r"\b(blogs?|channels?|feeds?|sources?) (were|was) quiet\b",
    r"\bquiet in[- ](the )?window\b",
    r"\bno new uploads?\b",
    r"\bsurfaced no\b",
    r"\bnewest (post|upload|issue|edition) is (still )?(from )?",
    r"\bfetch(ing)? (failed|failure|error)\b",
    r"\b(newsletter|edition|our) pipeline\b",
    r"\bscheduled run\b",
    r"\b(published|added) to the archive\b",
    r"\bthe public link (is|was|still)\b",
    r"\bthis (newsletter|edition) (was|has been) (built|compiled|generated|published)\b",
    r"\bcompiled (at|on)\b",
]
LEAK = re.compile("|".join(LEAK_PATTERNS), re.I)
NUMBERED = re.compile(r"(^|\s)(0\d|Story \d+|#\d+\s*[:.])\b")


def _text(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ")


def _fields(ed):
    yield "dek", ed["dek"]
    for i, p in enumerate(ed["brief"]):
        yield f"brief[{i}]", p
    for i, s in enumerate(ed["top_stories"]):
        for k in ("title", "summary", "why"):
            yield f"top_stories[{i}].{k}", s[k]
    for sec, keys in (("blogs", ("body",)), ("videos", ("title", "summary")), ("papers", ("title", "body")), ("threads", ("update",))):
        for i, item in enumerate(ed[sec]):
            for k in keys:
                yield f"{sec}[{i}].{k}", item[k]


def _urls(ed):
    for s in ed["top_stories"]:
        yield from (l["url"] for l in s["links"])
    for sec in ("blogs", "videos", "papers"):
        for item in ed[sec]:
            yield from (l["url"] for l in item["links"])
            if sec == "videos" and item.get("url"):
                yield item["url"]
    for _, value in _fields(ed):
        for a in BeautifulSoup(value or "", "html.parser").find_all("a", href=True):
            yield a["href"]


def lint_edition(ed, allowed_urls=None):
    """Return a list of problems. allowed_urls: set of URLs fetched this run (provenance check)."""
    problems = []
    for where, value in _fields(ed):
        text = _text(value)
        m = LEAK.search(text)
        if m:
            problems.append(f"{ed['date']} {where}: production/source-gap phrase {m.group(0)!r}")
        if NUMBERED.search(text) and where.endswith(("title", "dek")):
            problems.append(f"{ed['date']} {where}: numbered label")
    if sum(s["lead"] for s in ed["top_stories"]) != 1:
        problems.append(f"{ed['date']}: exactly one top story must be lead")
    if allowed_urls is not None:
        norm = {u.rstrip("/") for u in allowed_urls}
        for u in set(_urls(ed)):
            if u.rstrip("/") not in norm:
                problems.append(f"{ed['date']}: link not in today's fetched sources: {u}")
    return problems
