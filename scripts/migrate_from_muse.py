"""One-time migration: split the exported Muse archive HTML into structured edition JSON.

Usage: python scripts/migrate_from_muse.py path/to/ainews.html

Writes data/editions/YYYY-MM-DD.json, data/threads.json, and prints a report of
reader-facing source-gap notes that were dropped (they violate the newsletter rules).
"""
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
GAP = re.compile(
    r"\b(were quiet|was quiet|channels were quiet|blogs were quiet|no new uploads|"
    r"surfaced no|quiet in the window|quiet in-window|newest is still|newest upload)\b",
    re.I,
)
LEAD_DASH = re.compile(r"^\s*[—–-]\s*")


def inner(tag):
    return "".join(str(c) for c in tag.contents).strip()


def pop_links(tag):
    links = []
    for a in tag.select("a.source-link"):
        links.append({"label": a.get_text(strip=True), "url": a["href"]})
        a.decompose()
    return links


def clean_html(html):
    html = re.sub(r"\s+", " ", html).strip()
    html = re.sub(r"(\s*·\s*)+$", "", html).strip()
    return LEAD_DASH.sub("", html)


def parse_story(li):
    threads = [b["data-thread"] for b in li.select(".story-ribbon[data-thread]")]
    chip = li.select_one(".layer-chip")
    layer = chip["data-layer"] if chip else None
    bq = li.select_one("blockquote")
    links = pop_links(bq) if bq else []
    if bq:
        lab = bq.select_one("span")
        if lab:
            lab.decompose()
    return {
        "lead": "lead" in li.get("class", []),
        "threads": threads,
        "layer": layer,
        "title": li.select_one("h3").get_text(strip=True),
        "summary": clean_html(inner(li.select_one(".story-copy"))),
        "why": clean_html(inner(bq)) if bq else "",
        "links": links,
    }


def parse_edition(p, dropped):
    date = p["data-edition"]
    ed = {
        "date": date,
        "dek": p.select_one(".dek").get_text(strip=True),
        "brief": [clean_html(inner(x)) for x in p.select(".day-brief p")],
        "top_stories": [parse_story(li) for li in p.select('[data-section="top-stories"] li.story')],
        "blogs": [],
        "videos": [],
        "papers": [],
        "threads": [],
    }
    for li in p.select('[data-section="blogs"] li'):
        if GAP.search(li.get_text()) and not li.select("a.source-link"):
            dropped.append((date, "blogs", li.get_text(" ", strip=True)[:90]))
            continue
        links = pop_links(li)
        ed["blogs"].append({"body": clean_html(inner(li)), "links": links})
    vsec = p.select_one('[data-section="videos"]')
    if vsec:
        for li in vsec.select(".content-list li"):
            dropped.append((date, "videos", li.get_text(" ", strip=True)[:90]))
        for li in vsec.select("li.video-card"):
            watch = li.select_one("a.video-watch")
            copy = li.select_one(".video-copy")
            links = pop_links(copy)
            strong = copy.select_one("strong")
            heading = strong.get_text(" ", strip=True)
            strong.decompose()
            q = r"[“\"*]*"
            m = re.match(rf"^(.+?)\s+[—–]\s+{q}(.+?){q}\s*$", heading)
            if m:
                channel, title = m.group(1).strip("*"), m.group(2)
            elif re.match(rf"^[“\"]", heading):
                channel, title = "", heading.strip("“”\"")
            else:
                channel, title = heading.strip("*"), ""
            body = clean_html(inner(copy))
            note = ""
            nm = re.match(r"^\(([^)]*)\)\s*[—–-]?\s*", body)
            if nm:
                note, body = nm.group(1), body[nm.end():]
            if not title:
                em = re.match(r"^<em>[“\"]?(.+?)[”\"]?</em>\s*[—–-]?\s*", body)
                if em:
                    title, body = em.group(1).strip("“”\""), body[em.end():]
            ed["videos"].append({
                "channel": channel,
                "title": title,
                "when": note,
                "url": watch["href"] if watch else None,
                "summary": LEAD_DASH.sub("", body),
                "links": links,
            })
    for li in p.select('[data-section="papers"] li'):
        d = li.select_one("details.paper")
        title = d.select_one("summary > span").get_text(strip=True)
        chip = d.select_one(".layer-chip")
        body = d.select_one("summary ~ div")
        links = pop_links(body)
        ed["papers"].append({
            "title": title,
            "layer": chip["data-layer"] if chip else None,
            "body": clean_html(inner(body)),
            "links": links,
        })
    for li in p.select('[data-section="threads"] li.thread-card'):
        started = re.search(r"\d{4}-\d{2}-\d{2}", li.select_one(".thread-start").get_text())
        color = re.search(r"--thread:\s*(#[0-9a-fA-F]{6})", li.get("style", ""))
        ed["threads"].append({
            "name": li["data-thread-name"],
            "update": clean_html(inner(li.select_one("p"))).replace("NEW. ", "", 1),
            "_started": started.group(0) if started else date,
            "_color": color.group(1) if color else None,
        })
    return ed


def main(src):
    soup = BeautifulSoup(Path(src).read_text(), "html.parser")
    out = ROOT / "data" / "editions"
    out.mkdir(parents=True, exist_ok=True)
    dropped, registry = [], {}
    eds = [parse_edition(p, dropped) for p in soup.select("main.edition-panel")]
    for ed in sorted(eds, key=lambda e: e["date"]):
        for t in ed["threads"]:
            r = registry.setdefault(t["name"], {"started": ed["date"], "color": t["_color"]})
            r["last_update"] = ed["date"]
            t.pop("_started"); t.pop("_color")
        (out / f"{ed['date']}.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2) + "\n")
    # ribbon colors for threads that only ever appear as ribbons
    for b in soup.select(".storyline-pick[data-thread]"):
        c = re.search(r"#[0-9a-fA-F]{6}", b.get("style", ""))
        registry.setdefault(b["data-thread"], {"started": None, "color": None})
        registry[b["data-thread"]]["color"] = registry[b["data-thread"]]["color"] or (c and c.group(0))
    order = [b["data-thread"] for b in soup.select(".storyline-pick[data-thread]")]
    registry = {k: registry[k] for k in order + [k for k in registry if k not in order]}
    (ROOT / "data" / "threads.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    # Seed the seen-URL ledger so the first live run does not re-cover archived items.
    seen = {}
    for ed in eds:
        for u in re.findall(r'https?://[^"\s<>]+', json.dumps(ed, ensure_ascii=False)):
            seen.setdefault(u, ed["date"])
    (ROOT / "data" / "state.json").write_text(json.dumps({"seen": seen, "fetched_sources": []}, indent=1, sort_keys=True) + "\n")
    print(f"editions: {len(eds)}  threads: {len(registry)}  dropped gap notes: {len(dropped)}")
    for d in dropped:
        print("  dropped", *d)


if __name__ == "__main__":
    main(sys.argv[1])
