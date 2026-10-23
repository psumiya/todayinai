"""Daily run: fetch -> model -> validate -> write data -> build.

Idempotent per date: if today's edition file exists, it exits without calling the model.
Usage:
  python -m newsletter.run                      # live (needs ANTHROPIC_API_KEY and internet)
  python -m newsletter.run --fixture tests/fixture --date 2026-10-22   # offline dry run
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import jsonschema

from newsletter import build
from newsletter.lint import lint_edition
from newsletter.schema import EDITION_SCHEMA

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
MODEL = os.environ.get("NEWSLETTER_MODEL", "claude-sonnet-5-5")
PALETTE = ["#d2563b", "#3a8fb7", "#8a6fd1", "#4fa36b", "#c98a1b", "#d14f8a", "#2f9e9e", "#7f8c3a"]
STALE_DAYS = 10
QUIET = re.compile(r"^\W*(quiet|nothing new)", re.I)

TOOL = {
    "name": "submit_edition",
    "description": "Submit today's finished edition and any thread changes.",
    "input_schema": {
        "type": "object",
        "required": ["edition", "new_threads", "retire_threads"],
        "properties": {
            "edition": EDITION_SCHEMA,
            "new_threads": {"type": "array", "items": {"type": "string"}},
            "retire_threads": {"type": "array", "items": {"type": "string"}},
        },
    },
}


def load_state():
    p = DATA / "state.json"
    s = json.loads(p.read_text()) if p.exists() else {"seen": {}, "fetched_sources": []}
    cutoff = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    s["seen"] = {u: d for u, d in s["seen"].items() if d >= cutoff}
    return s


def thread_context(threads, editions):
    """Active threads with their two most recent updates, newest first."""
    out = []
    for name, t in threads.items():
        if not t.get("active", True):
            continue
        recent = [(e["date"], u["update"]) for e in editions for u in e["threads"] if u["name"] == name][:2]
        out.append({"name": name, "started": t["started"], "recent_updates": recent})
    return out


UNENFORCED = {"minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum", "maximum", "uniqueItems"}


def api_schema(s):
    """Structured-output form of a schema: drop constraints the API can't enforce (jsonschema checks them after)."""
    if isinstance(s, list):
        return [api_schema(x) for x in s]
    if not isinstance(s, dict):
        return s
    out = {k: api_schema(v) for k, v in s.items() if k not in UNENFORCED}
    if isinstance(out.get("type"), list):
        rest = {k: v for k, v in out.items() if k != "type"}
        if "enum" in rest:
            rest["enum"] = [v for v in rest["enum"] if v is not None]
        return {"anyOf": [{"type": t, **(rest if t != "null" else {})} for t in out["type"]]}
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def ask_model(date, items, threads, editions, feedback=None):
    import anthropic

    system = (ROOT / "newsletter" / "prompt.md").read_text()
    payload = {
        "date": date,
        "threads": thread_context(threads, editions),
        "recent_top_stories": [{"date": e["date"], "titles": [s["title"] for s in e["top_stories"]]} for e in editions[:3]],
        "items": items,
    }
    messages = [{"role": "user", "content": "Today's input:\n" + json.dumps(payload, ensure_ascii=False)}]
    if feedback:
        messages[0]["content"] += "\n\nYour previous submission was rejected. Fix exactly these problems:\n- " + "\n- ".join(feedback)
    with anthropic.Anthropic().messages.stream(
        model=MODEL, max_tokens=64000, system=system, messages=messages,
        output_config={"format": {"type": "json_schema", "schema": api_schema(TOOL["input_schema"])}},
    ) as stream:
        resp = stream.get_final_message()
    if resp.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with {resp.stop_reason} (request {resp._request_id})")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def check(result, date, items, threads):
    ed = result["edition"]
    problems = []
    try:
        jsonschema.validate(ed, EDITION_SCHEMA)
    except jsonschema.ValidationError as e:
        problems.append(f"schema: {e.message} at {'/'.join(map(str, e.absolute_path))}")
        return problems
    if ed["date"] != date:
        problems.append(f"edition date must be {date}")
    known = set(threads) | set(result["new_threads"])
    for name in {t for s in ed["top_stories"] for t in s["threads"]} | {t["name"] for t in ed["threads"]}:
        if name not in known:
            problems.append(f"unknown thread {name!r}: use an existing name or list it in new_threads")
    problems += lint_edition(ed, allowed_urls={i["url"] for i in items})
    return problems


def apply_threads(threads, result, date, editions):
    for name in result["new_threads"]:
        if name not in threads:
            used = {t["color"] for t in threads.values()}
            color = next((c for c in PALETTE if c not in used), PALETTE[len(threads) % len(PALETTE)])
            threads[name] = {"started": date, "color": color, "active": True}
    for name in result["retire_threads"]:
        if name in threads:
            threads[name]["active"] = False
    # Mechanical decay: a thread with no substantive update in STALE_DAYS goes inactive.
    history = [result["edition"]] + editions
    for name, t in threads.items():
        last = next((e["date"] for e in history for u in e["threads"]
                     if u["name"] == name and not QUIET.match(u["update"])), t["started"])
        t["last_update"] = last
        if t.get("active", True) and (dt.date.fromisoformat(date) - dt.date.fromisoformat(last)).days > STALE_DAYS:
            t["active"] = False
    return threads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--fixture", help="dir with items.json and response.json; skips network and model")
    args = ap.parse_args()
    date = args.date or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    out = DATA / "editions" / f"{date}.json"
    if out.exists():
        print(f"{date} already exists; nothing to do")
        return
    threads = json.loads((DATA / "threads.json").read_text())
    editions = sorted((json.loads(f.read_text()) for f in (DATA / "editions").glob("*.json")),
                      key=lambda e: e["date"], reverse=True)
    state = load_state()
    log = {"date": date, "model": MODEL, "gaps": [], "attempts": []}

    if args.fixture:
        fx = Path(args.fixture)
        items = json.loads((fx / "items.json").read_text())
        responses = [json.loads((fx / "response.json").read_text())]
    else:
        from newsletter.fetch import collect

        items, log["gaps"] = collect(state)
        responses = None
    log["item_counts"] = {k: sum(i["kind"] == k for i in items) for k in ("blog", "video", "paper")}
    if sum(log["item_counts"].values()) < 3:
        log["outcome"] = "skipped: fewer than 3 new items"
        return finish(log, date)

    feedback, result = None, None
    for attempt in range(3):
        result = responses.pop(0) if responses else ask_model(date, items, threads, editions, feedback)
        feedback = check(result, date, items, threads)
        log["attempts"].append(feedback)
        if not feedback:
            break
        if args.fixture and not responses:
            break
    if feedback:
        log["outcome"] = "rejected"
        finish(log, date)
        sys.exit(1)

    threads = apply_threads(threads, result, date, editions)
    out.write_text(json.dumps(result["edition"], ensure_ascii=False, indent=2) + "\n")
    (DATA / "threads.json").write_text(json.dumps(threads, ensure_ascii=False, indent=2) + "\n")
    for i in items:
        state["seen"][i["url"]] = date
    (DATA / "state.json").write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    log["outcome"] = "published"
    finish(log, date)
    build.render(strict=True)


def finish(log, date):
    LOGS.mkdir(exist_ok=True)
    (LOGS / f"run-{date}.json").write_text(json.dumps(log, indent=2) + "\n")
    print(json.dumps({k: log[k] for k in ("date", "outcome") if k in log}))


if __name__ == "__main__":
    main()
