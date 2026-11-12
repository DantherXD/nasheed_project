#!/usr/bin/env python3
"""Repeatable crawl of the two portal indexes this database was seeded from.

    python3 tools/crawl_portals.py --source all            # crawl + report
    python3 tools/crawl_portals.py --source samaa --refresh
    python3 tools/crawl_portals.py --report-only

Samaa is crawled through its music-free archive, /genre/acapella-version/
("بدون موسيقى"), because a cappella is the only thing this database accepts as
inshad — an artist whose portal page is instrumental pop never shows up here.
Arabic-only names are fine; a Latin name is not required.

Output: data/portal_candidates.json — every artist found, their tracks, and a
note on whether the database already has them. Re-running reuses the cached
pages unless you pass --refresh, so a fresh look at the portals costs nothing.
"""
import argparse
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, ROOT, load_db, variants  # noqa: E402

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
OUT = ROOT / "data" / "portal_candidates.json"
SAMA_BASE = "https://play.samaanetwork.net/genre/acapella-version/"
ASSAJDA_INDEX = "https://www.assajda.com/en/anasheed"


def fetch(url, cache_file, refresh=False, delay=1.2):
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    if cache_file.exists() and not refresh and cache_file.stat().st_size > 5000:
        return cache_file.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read().decode("utf-8", errors="replace")
    cache_file.write_text(body, encoding="utf-8")
    time.sleep(delay)
    return body


def text(fragment):
    return htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


# ------------------------------------------------------------------ samaa
ARTICLE = re.compile(r'<article[^>]*class="item post-(\d+)[^"]*"[^>]*>(.*?)</article>', re.S)
ARTIST = re.compile(r'<a[^>]*href="https://play\.samaanetwork\.net/(\d+)/"[^>]*>(.*?)</a>', re.S)
ANCHOR = re.compile(r"<a([^>]*)>(.*?)</a>", re.S)
SLUG_HREF = re.compile(r'href="(?:https://play\.samaanetwork\.net/)?(music/[^"]+?)/"')


def track_title(block):
    """The card's own title anchor; the other /music/ links on a card are
    \"music version / rythm version\" alternates, which are not tracks."""
    for attrs, inner in ANCHOR.findall(block):
        if "text-ellipsis" not in attrs:
            continue
        m = SLUG_HREF.search(attrs)
        title = text(inner)
        if m and title:
            return title
    return None


def crawl_samaa(max_pages, refresh):
    artists, pages, tracks = {}, 0, 0
    for page in range(1, max_pages + 1):
        url = SAMA_BASE if page == 1 else f"{SAMA_BASE}page/{page}/"
        cache = CACHE / "crawl_samaa" / f"acapella_p{page}.html"
        try:
            body = fetch(url, cache, refresh)
        except Exception as e:  # noqa: BLE001
            print(f"  samaa page {page}: {e}", file=sys.stderr)
            break
        found = 0
        for post_id, block in ARTICLE.findall(body):
            m_art = ARTIST.search(block)
            if not m_art:
                continue
            artist_id, name = m_art.group(1), text(m_art.group(2))
            if not name:
                continue
            title = track_title(block)
            entry = artists.setdefault(artist_id, {
                "portal": "samaa",
                "portal_id": artist_id,
                "url": f"https://play.samaanetwork.net/{artist_id}/",
                "names": {},
                "tracks": [],
                "genres": ["acapella-version"],
            })
            entry["names"][name] = entry["names"].get(name, 0) + 1
            if title and title not in entry["tracks"]:
                entry["tracks"].append(title)
            found += 1
            tracks += 1
        pages += 1
        print(f"  samaa page {page}: {found} music-free tracks")
        if not found:
            break

    for entry in artists.values():
        entry["name"] = max(entry["names"], key=entry["names"].get)
        del entry["names"]
        entry["count"] = len(entry["tracks"])
    return {"samaa": artists, "pages": pages, "tracks": tracks}


# ---------------------------------------------------------------- assajda
CARD = re.compile(
    r'<a[^>]+href="(?:https://www\.assajda\.com)?/en/([a-z0-9\-]+?)-(\d+)\.html"[^>]*>(.*?)</a>',
    re.S,
)
META = re.compile(r"([A-Z][A-Za-z .'\-]+?)\s*·\s*(\d+)\s*nasheed")


def crawl_assajda(refresh):
    body = fetch(ASSAJDA_INDEX, CACHE / "crawl_assajda" / "index.html", refresh)
    artists = {}
    for slug, num, inner in CARD.findall(body):
        chunk = text(inner)
        m = META.search(chunk)
        if not m:
            continue
        name_part = chunk[: m.start()].strip()
        latin = re.search(r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)", name_part)
        arabic = re.search(r"([\u0600-\u06ff][\u0600-\u06ff\s]{2,})", name_part)
        artists[f"{slug}-{num}"] = {
            "portal": "assajda",
            "portal_id": f"{slug}-{num}",
            "url": f"https://www.assajda.com/en/{slug}-{num}.html",
            "name": latin.group(1).strip() if latin else (arabic.group(1).strip() if arabic else chunk[:60]),
            "ar": arabic.group(1).strip() if arabic else "",
            "country": m.group(1).strip(),
            "count": int(m.group(2)),
        }
    return {"assajda": artists}


# ----------------------------------------------------------------- report
def report(candidates, min_tracks):
    db = load_db()
    known = {}
    for a in db["artists"]:
        for key in variants(a["n"]) | variants(a.get("ar", "")):
            known.setdefault(key, a["id"])

    by_tokens = [(set(k.split()), i) for k, i in known.items()]

    def fuzzy(keys):
        """Portals shorten names (\"مشاري العفاسي\" for \"مشاري بن راشد العفاسي\"),
        so accept a key whose tokens are a subset of a stored one."""
        best, best_len = None, 0
        for key in keys:
            tokens = set(key.split())
            if len(tokens) < 2:
                continue
            for tokens2, ident in by_tokens:
                if tokens <= tokens2 and len(tokens) > best_len:
                    best, best_len = ident, len(tokens)
        return best

    seen, fresh = [], []
    for portal in ("samaa", "assajda"):
        for entry in candidates.get(portal, {}).values():
            keys = variants(entry["name"]) | variants(entry.get("ar", ""))
            hit = next((known[k] for k in keys if k in known), None) or fuzzy(keys)
            entry["in_db"] = hit
            (seen if hit else fresh).append(entry)

    fresh.sort(key=lambda e: -e["count"])
    strong = [e for e in fresh if e["count"] >= min_tracks]
    print(f"\n{len(seen)} already in the database, {len(fresh)} new "
          f"({len(strong)} with {min_tracks}+ tracks)")
    for e in strong[:25]:
        where = f" · {e['country']}" if e.get("country") else ""
        print(f"  {e['name'][:34]:36} {e['count']:>3} tracks{where}  {e['url']}")
    if len(strong) > 25:
        print(f"  … {len(strong) - 25} more in {OUT.relative_to(ROOT)}")
    return fresh


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["samaa", "assajda", "all"], default="all")
    p.add_argument("--max-pages", type=int, default=25)
    p.add_argument("--refresh", action="store_true", help="ignore cached pages")
    p.add_argument("--report-only", action="store_true", help="use the last crawl")
    p.add_argument("--min-tracks", type=int, default=2)
    args = p.parse_args()

    if args.report_only:
        candidates = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        candidates = {}
        if args.source in ("samaa", "all"):
            print("crawling Samaa music-free archive …")
            candidates.update(crawl_samaa(args.max_pages, args.refresh))
        if args.source in ("assajda", "all"):
            print("crawling Assajda index …")
            candidates.update(crawl_assajda(args.refresh))

    report(candidates, args.min_tracks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(candidates, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nwritten {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
