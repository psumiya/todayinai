"""Render data/editions/*.json + data/threads.json into dist/ainews.html.

Deterministic: same data in, same bytes out. The model never touches this file's output directly.
Usage: python -m newsletter.build
"""
import calendar
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import jsonschema
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from newsletter.lint import lint_edition
from newsletter.schema import ARCHIVE_SCHEMA, LAYERS

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
SITE = {
    "title": "Today in AI",
    "description": "A daily AI newsletter tracking the storylines that persist across days.",
    "colophon": "Edited daily from the primary-source record",
}
ALLOWED = {"a", "em", "strong", "sup", "sub", "code", "i", "b"}


def inline(value):
    """Sanitize inline text: keep a small tag allowlist, force safe link attributes."""
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED:
            tag.unwrap()
            continue
        if tag.name == "a":
            href = tag.get("href", "")
            if not re.match(r"^https?://", href):
                tag.unwrap()
                continue
            classes = [c for c in tag.get("class", []) if c == "source-link"]
            tag.attrs = {"href": href, "target": "_blank", "rel": "noopener"}
            if classes:
                tag["class"] = classes
        else:
            tag.attrs = {}
    return Markup(str(soup))


def load():
    threads = json.loads((DATA / "threads.json").read_text())
    editions = []
    for f in sorted((DATA / "editions").glob("*.json")):
        ed = json.loads(f.read_text())
        try:
            jsonschema.validate(ed, ARCHIVE_SCHEMA)
        except jsonschema.ValidationError as e:
            raise SystemExit(f"{f.name}: {e.message} at {'/'.join(map(str, e.absolute_path))}")
        if f.stem != ed["date"]:
            raise ValueError(f"{f.name}: date field is {ed['date']}")
        for name in {t for s in ed["top_stories"] for t in s["threads"]} | {t["name"] for t in ed["threads"]}:
            if name not in threads:
                raise ValueError(f"{f.name}: unknown thread {name!r}; add it to data/threads.json")
        editions.append(ed)
    editions.sort(key=lambda e: e["date"], reverse=True)
    return threads, editions


def decorate(editions):
    for i, ed in enumerate(editions):
        d = dt.date.fromisoformat(ed["date"])
        ed.update(
            latest=i == 0,
            newer=editions[i - 1]["date"] if i > 0 else None,
            older=editions[i + 1]["date"] if i + 1 < len(editions) else None,
            weekday=calendar.day_name[d.weekday()],
            month=f"{calendar.month_name[d.month]} {d.year}",
            month_day=f"{calendar.month_name[d.month]} {d.day}",
            short_date=f"{calendar.month_abbr[d.month]} {d.day}, {d.year}",
            long_date=f"{calendar.day_name[d.weekday()]}, {calendar.month_name[d.month]} {d.day}, {d.year}",
            day=str(d.day),
            year=d.year,
        )
    months = []
    for ed in editions:
        if not months or months[-1][0] != ed["month"]:
            months.append((ed["month"], []))
        months[-1][1].append(ed)
    return months


def render(strict=False):
    threads, editions = load()
    problems = [p for ed in editions for p in lint_edition(ed)]
    if problems:
        for p in problems:
            print("lint:", p, file=sys.stderr)
        if strict:
            raise SystemExit(1)
    months = decorate(editions)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["j2"]))
    env.filters["inline"] = inline
    registry = {k: {"started": v["started"], "color": v["color"]} for k, v in threads.items()}
    out = env.get_template("page.html.j2").render(
        site=SITE,
        editions=editions,
        months=months,
        threads=threads,
        layers=LAYERS,
        css=Markup((ROOT / "templates" / "styles.css").read_text()),
        js=Markup((ROOT / "templates" / "app.js").read_text()),
        registry_json=Markup(json.dumps(registry, ensure_ascii=False).replace("</", "<\\/")),
    )
    DIST.mkdir(exist_ok=True)
    (DIST / "ainews.html").write_text(out)
    print(f"built dist/ainews.html: {len(editions)} editions, {len(out) // 1024} KB")


if __name__ == "__main__":
    render(strict="--strict" in sys.argv)
