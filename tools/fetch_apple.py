#!/usr/bin/env python3
"""Find the Apple Music page for artists that don't have one yet.

    python3 tools/fetch_apple.py --out apple_links.json

Needs only Python 3 — no packages, no key. It reads nasheed-db.json, asks
Apple's public iTunes Search API, and writes the verified matches to JSON.
It is resumable: run it again and it skips whatever is already in the file.

    python3 tools/fetch_apple.py --limit 200 --sleep 3

Apple starts answering 403/429 after a few hundred lookups from one address.
When that happens the script backs off, saves, and stops — rerun later (or from
another network) and it carries on where it left off. Send back the JSON and
the matches can be merged into the database.
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_db, norm  # noqa: E402

API = "https://itunes.apple.com/search"
UA = "nasheed-db/1.0 (+https://github.com/DantherXD/nasheed_project)"


def query(term, country, timeout=15):
    qs = urllib.parse.urlencode(
        {"term": term, "entity": "musicArtist", "limit": 8, "country": country}
    )
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def match(name, arabic, results):
    """Strict: the returned artist name must normalise to ours."""
    wanted = {norm(name)}
    if arabic:
        wanted.add(norm(arabic))
    wanted = {w for w in wanted if w}
    for item in results:
        if norm(item.get("artistName")) in wanted and item.get("artistLinkUrl"):
            return item
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="apple_links.json", help="results file (resumable)")
    p.add_argument("--db", default="nasheed-db.json")
    p.add_argument("--country", default="US", help="storefront to search, e.g. US or SA")
    p.add_argument("--limit", type=int, default=0, help="stop after N lookups this run")
    p.add_argument("--sleep", type=float, default=2.0, help="seconds between lookups")
    p.add_argument("--max-misses", type=int, default=6,
                   help="stop after this many refusals in a row")
    args = p.parse_args()

    out_path = Path(args.out)
    found = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    found = {k: v for k, v in found.items() if not k.startswith("_")}

    db = json.loads(Path(args.db).read_text(encoding="utf-8"))
    todo = []
    for a in db["artists"]:
        if any(l["t"] == "apple" for l in a.get("links", [])):
            continue
        if a["n"] in found:
            continue
        todo.append(a)

    print(f"{len(todo)} artists still need an Apple Music page "
          f"({len(found)} already in {out_path})", flush=True)
    if not todo:
        return

    done = misses = 0
    for i, artist in enumerate(todo, 1):
        if args.limit and done >= args.limit:
            print(f"limit reached after {done} lookups", flush=True)
            break

        term = artist["n"]
        try:
            hit = match(term, artist.get("ar"), query(term, args.country).get("results", []))
            if not hit and artist.get("ar") and not hit:
                hit = match(term, artist.get("ar"), query(artist["ar"], args.country).get("results", []))
            misses = 0
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                misses += 1
                wait = min(60, args.sleep * (4 ** misses))
                print(f"  {e.code} — Apple is refusing, waiting {wait:.0f}s "
                      f"({misses}/{args.max_misses})", flush=True)
                if misses >= args.max_misses:
                    out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")
                    print(f"\nSTOPPED: still rate limited. {len(found)} matches saved to {out_path}.\n"
                          f"Rerun the same command later and it resumes from here.", flush=True)
                    return
                time.sleep(wait)
                continue
            print(f"  err {artist['n']}: {e}", flush=True)
            time.sleep(args.sleep)
            continue
        except Exception as e:  # noqa: BLE001 - network flakiness should not lose the run
            print(f"  err {artist['n']}: {e}", flush=True)
            time.sleep(args.sleep)
            continue

        done += 1
        if hit:
            found[artist["n"]] = {
                "url": hit["artistLinkUrl"],
                "id": hit.get("artistId"),
                "source": "itunes-search",
                "country": args.country,
            }
            print(f"[{i}/{len(todo)}] {artist['n']}  ->  {hit['artistLinkUrl']}", flush=True)
            out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
        else:
            print(f"[{i}/{len(todo)}] {artist['n']}  -- no match", flush=True)

        time.sleep(args.sleep * (1 + random.random() * 0.4))

    out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\ndone: {len(found)} matches in {out_path} "
          f"({len(todo) - done} not attempted)", flush=True)


if __name__ == "__main__":
    main()
