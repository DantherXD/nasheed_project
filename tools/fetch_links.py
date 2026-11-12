#!/usr/bin/env python3
"""Look up streaming pages for a list of artist names — run this locally.

    python3 tools/fetch_links.py --out data/link_candidates.json

Reads data/wanted_artists.txt (or --names FILE), asks Apple, Deezer, Spotify and
YouTube, and writes the matches to JSON. No crawling, no browser: one request
per service per name.

Apple and Deezer need nothing. Spotify and YouTube need credentials, and are
skipped when they are absent:

    export SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=...   # free at developer.spotify.com
    export YOUTUBE_API_KEY=...                              # free at console.cloud.google.com

It is resumable: interrupt it, get rate-limited, or stop at --limit, and the
same command carries on from where it stopped.

    python3 tools/fetch_links.py --limit 200 --sleep 1.5
    python3 tools/fetch_links.py --services apple,deezer        # keyless only
"""
import argparse
import base64
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import norm, variants  # noqa: E402

UA = "nasheed-db/1.0 (+https://github.com/DantherXD/nasheed_project)"


def get(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def close_enough(name, candidate):
    """Strict-ish: identical after normalising, or one name contains the other
    with at least two words in common. Rejects 'Maher Zain' vs 'Zain Maher'."""
    a, b = norm(name), norm(candidate)
    if not a or not b:
        return False
    if a == b or a.replace(" ", "") == b.replace(" ", ""):
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) >= 2 and (ta <= tb or tb <= ta)


def pick(name, items, name_key, url_key, extra=None):
    """items -> the best exact-ish candidate, or None."""
    for item in items:
        label = item.get(name_key) or ""
        if close_enough(name, label):
            url = item.get(url_key)
            if url:
                hit = {"name": label, "url": url}
                if extra:
                    hit.update({k: item[v] for k, v in extra.items() if v in item})
                return hit
    return None


# ---------------------------------------------------------------- services
def apple(name, country):
    qs = urllib.parse.urlencode({"term": name, "entity": "musicArtist", "limit": 8, "country": country})
    data = get(f"https://itunes.apple.com/search?{qs}")
    return pick(name, data.get("results", []), "artistName", "artistLinkUrl",
                {"id": "artistId"})


def deezer(name):
    data = get("https://api.deezer.com/search/artist?" + urllib.parse.urlencode({"q": name, "limit": 8}))
    return pick(name, data.get("data", []), "name", "link", {"id": "id"})


_spotify_token = {"value": None}


def spotify(name):
    cid, secret = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not (cid and secret):
        return None
    if not _spotify_token["value"]:
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        data = get("https://accounts.spotify.com/api/token",
                   headers={"Authorization": f"Basic {basic}",
                            "Content-Type": "application/x-www-form-urlencoded"},
                   data=b"grant_type=client_credentials")
        _spotify_token["value"] = data["access_token"]
    qs = urllib.parse.urlencode({"q": name, "type": "artist", "limit": 5})
    data = get("https://api.spotify.com/v1/search?" + qs,
               headers={"Authorization": f"Bearer {_spotify_token['value']}"})
    items = [{"name": i["name"], "url": i["external_urls"]["spotify"], "id": i["id"]}
             for i in (data.get("artists", {}).get("items") or [])]
    return pick(name, items, "name", "url", {"id": "id"})


def youtube(name):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return None
    qs = urllib.parse.urlencode({"part": "snippet", "type": "channel", "maxResults": 5,
                                 "q": name, "key": key})
    data = get("https://www.googleapis.com/youtube/v3/search?" + qs)
    items = []
    for item in data.get("items", []):
        cid = item.get("id", {}).get("channelId")
        title = item.get("snippet", {}).get("channelTitle", "")
        if cid:
            items.append({"name": title, "url": f"https://www.youtube.com/channel/{cid}", "id": cid})
    return pick(name, items, "name", "url", {"id": "id"})


SERVICES = {"apple": apple, "deezer": deezer, "spotify": spotify, "youtube": youtube}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--names", default="data/wanted_artists.txt")
    p.add_argument("--out", default="data/link_candidates.json")
    p.add_argument("--services", default="apple,deezer,spotify,youtube")
    p.add_argument("--country", default="US", help="Apple storefront, e.g. US, SA, GB")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--sleep", type=float, default=1.5)
    p.add_argument("--max-misses", type=int, default=6)
    args = p.parse_args()

    wanted = [l.strip() for l in Path(args.names).read_text(encoding="utf-8").splitlines()]
    wanted = [l for l in wanted if l and not l.startswith("#")]

    out_path = Path(args.out)
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    results = {k: v for k, v in results.items() if not k.startswith("_")}
    todo = [n for n in wanted if n not in results]

    chosen = []
    for svc in args.services.split(","):
        svc = svc.strip().lower()
        if svc == "spotify" and not (os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")):
            print("spotify skipped: set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
            continue
        if svc == "youtube" and not os.environ.get("YOUTUBE_API_KEY"):
            print("youtube skipped: set YOUTUBE_API_KEY")
            continue
        if svc in SERVICES:
            chosen.append(svc)

    print(f"{len(todo)} names to look up ({len(results)} already done) · services: {', '.join(chosen)}")
    done = misses = 0
    for i, name in enumerate(todo, 1):
        if args.limit and done >= args.limit:
            print(f"limit reached after {done} names")
            break
        entry = {}
        for svc in chosen:
            try:
                fn = SERVICES[svc]
                hit = fn(name, args.country) if svc == "apple" else fn(name)
                if hit:
                    entry[svc] = hit
                misses = 0
            except urllib.error.HTTPError as e:
                if e.code in (403, 429, 503):
                    misses += 1
                    wait = min(90, args.sleep * (3 ** misses))
                    print(f"  {svc} refused {e.code}, waiting {wait:.0f}s ({misses}/{args.max_misses})")
                    if misses >= args.max_misses:
                        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
                        print(f"\nSTOPPED: rate limited. {len(results)} names saved to {out_path}.\n"
                              f"Rerun the same command later; it resumes.", flush=True)
                        return
                    time.sleep(wait)
                else:
                    print(f"  {svc} error on {name}: {e}")
            except Exception as e:  # noqa: BLE001
                print(f"  {svc} error on {name}: {e}")
            time.sleep(args.sleep * (0.6 + random.random() * 0.8))

        results[name] = entry
        done += 1
        labels = ", ".join(f"{k}:{v['name']}" for k, v in entry.items())
        print(f"[{i}/{len(todo)}] {name}  ->  {labels or 'nothing found'}")
        if i % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    hits = sum(1 for v in results.values() if v)
    print(f"\ndone: {len(results)} names checked, {hits} with at least one match -> {out_path}")


if __name__ == "__main__":
    main()
