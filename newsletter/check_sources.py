"""Probe every source in data/sources.yaml and resolve missing YouTube channel ids.

Prints one line per source. Fix or pin anything marked FAIL before trusting a run.
Usage: python -m newsletter.check_sources
"""
import re

import feedparser
import yaml

from newsletter.fetch import ROOT, get


def main():
    cfg = yaml.safe_load((ROOT / "data" / "sources.yaml").read_text())
    for s in cfg["blogs"]:
        if not s.get("url"):
            print(f"SKIP {s['name']}: no url pinned")
            continue
        try:
            body = get(s["url"])
            if s["kind"] == "rss":
                n = len(feedparser.parse(body).entries)
                print(f"{'OK  ' if n else 'FAIL'} {s['name']}: {n} feed entries")
            else:
                n = len(set(re.findall(s["link_pattern"].strip("^$").replace("/?", ""), body.decode("utf-8", "ignore"))))
                print(f"{'OK  ' if n else 'FAIL'} {s['name']}: {n} matching article links")
        except Exception as e:
            print(f"FAIL {s['name']}: {e}")
    for s in cfg["youtube"]:
        cid = s.get("channel_id")
        if not cid and s.get("handle"):
            try:
                html = get(f"https://www.youtube.com/{s['handle']}").decode("utf-8", "ignore")
                m = re.search(r'"channelId":"(UC[\w-]{22})"', html) or re.search(r'channel/(UC[\w-]{22})', html)
                cid = m.group(1) if m else None
                print(f"     {s['name']}: resolved {s['handle']} -> {cid}  (pin this in sources.yaml)")
            except Exception as e:
                print(f"FAIL {s['name']}: handle lookup {e}")
                continue
        if not cid:
            print(f"FAIL {s['name']}: no channel_id")
            continue
        feed = feedparser.parse(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"))
        author = feed.feed.get("title", "?")
        ok = feed.entries and s["name"].lower().split()[0] in author.lower()
        print(f"{'OK  ' if ok else 'FAIL'} {s['name']}: feed title {author!r}, {len(feed.entries)} videos")


if __name__ == "__main__":
    main()
