"""Collect candidate items from pinned sources. Pure data: no model calls here.

Every item carries the URL the edition is allowed to link to. The lint step rejects
any link in the generated edition that is not in this set, so the model cannot invent URLs.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import feedparser
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "TodayInAI/1.0 (+https://sumiya.page/ainews.html)"}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _when(entry):
    for k in ("published_parsed", "updated_parsed"):
        if entry.get(k):
            return dt.datetime(*entry[k][:6], tzinfo=dt.timezone.utc)
    return None


def _text(html, n=1200):
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "html.parser").get_text(" ")).strip()[:n]


def fetch_rss(src, since):
    feed = feedparser.parse(get(src["url"]))
    out = []
    for e in feed.entries:
        when = _when(e)
        if when and when < since:
            continue
        out.append({
            "source": src["name"], "kind": "blog", "title": e.get("title", ""), "url": e.get("link"),
            "published": when.isoformat() if when else None,
            "summary": _text(e.get("summary") or (e.get("content") or [{}])[0].get("value", "")),
        })
    return out


def fetch_page(src, state):
    soup = BeautifulSoup(get(src["url"]), "html.parser")
    pat = re.compile(src["link_pattern"])
    seen_before = src["name"] in state["fetched_sources"]
    out, urls = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].split("?")[0]
        if not pat.match(href):
            continue
        url = urllib.parse.urljoin(src["url"], href)
        if url in urls:
            continue
        urls.add(url)
        title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if seen_before and url not in state["seen"]:
            out.append({"source": src["name"], "kind": "blog", "title": title, "url": url, "published": None,
                        "summary": _page_summary(url)})
    if not seen_before:  # first contact: seed the ledger so the back catalogue is not treated as news
        for u in urls:
            state["seen"].setdefault(u, dt.date.today().isoformat())
        state["fetched_sources"].append(src["name"])
    return out


def _page_summary(url):
    try:
        soup = BeautifulSoup(get(url), "html.parser")
    except Exception:
        return ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    body = " ".join(p.get_text(" ") for p in soup.select("article p, main p")[:12])
    return _text((meta["content"] if meta and meta.get("content") else "") + " " + body, 2000)


def fetch_youtube(src, since):
    if not src.get("channel_id"):
        return []
    feed = feedparser.parse(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={src['channel_id']}"))
    out = []
    for e in feed.entries:
        when = _when(e)
        if when and when < since:
            continue
        author = e.get("author", "")
        out.append({
            "source": author or src["name"],  # attribution comes from the video's own author field
            "kind": "video", "title": e.get("title", ""), "url": e.get("link"),
            "published": when.isoformat() if when else None,
            "summary": _text((e.get("media_description") or e.get("summary") or ""), 1500),
        })
    return out


def fetch_arxiv(cfg, since):
    cats = "+OR+".join(f"cat:{c}" for c in cfg["categories"])
    url = (f"http://export.arxiv.org/api/query?search_query={cats}&sortBy=submittedDate&sortOrder=descending"
           f"&max_results={cfg['max_results']}")
    feed = feedparser.parse(get(url, timeout=60))
    upvotes = {}
    if cfg.get("hf_daily_papers"):
        try:
            for p in json.loads(get("https://huggingface.co/api/daily_papers?limit=100")):
                pid = (p.get("paper") or {}).get("id")
                if pid:
                    upvotes[pid] = (p.get("paper") or {}).get("upvotes", 0)
        except Exception:
            pass
    out = []
    for e in feed.entries:
        when = _when(e)
        if when and when < since:
            continue
        aid = e.id.rsplit("/abs/", 1)[-1].split("v")[0]
        out.append({
            "source": "arXiv", "kind": "paper", "title": re.sub(r"\s+", " ", e.title), "url": f"https://arxiv.org/abs/{aid}",
            "published": when.isoformat() if when else None,
            "authors": [a.name for a in e.get("authors", [])][:8],
            "summary": _text(e.summary, 1200), "hf_upvotes": upvotes.get(aid),
        })
    # Papers people are actually upvoting first; the model still decides.
    out.sort(key=lambda x: -(x["hf_upvotes"] or 0))
    return out


def collect(state, now=None):
    cfg = yaml.safe_load((ROOT / "data" / "sources.yaml").read_text())
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(hours=cfg["window_hours"])
    items, gaps = [], []
    jobs = [(s, "blog") for s in cfg["blogs"]] + [(s, "youtube") for s in cfg["youtube"]]
    for src, kind in jobs:
        if kind == "blog" and not src.get("url"):
            continue
        try:
            if kind == "youtube":
                got = fetch_youtube(src, since)
            elif src["kind"] == "page":
                got = fetch_page(src, state)
            else:
                got = fetch_rss(src, since)
        except Exception as e:  # one source failing never stops the edition
            gaps.append(f"{src['name']}: {type(e).__name__}: {e}")
            continue
        items.extend(i for i in got if i["url"] and i["url"] not in state["seen"])
    try:
        items.extend(i for i in fetch_arxiv(cfg["arxiv"], since) if i["url"] not in state["seen"])
    except Exception as e:
        gaps.append(f"arXiv: {type(e).__name__}: {e}")
    return items, gaps
