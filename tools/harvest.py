#!/usr/bin/env python3
"""Ask every aggregation source in the database about an artist — run this locally.

    python3 tools/harvest.py --check            # what is ready, what needs a key
    python3 tools/harvest.py --list             # every source and how it is handled
    python3 tools/harvest.py --artist "Maher Zain"
    python3 tools/harvest.py --limit 50 --sleep-scale 1.5
    python3 tools/harvest.py --source Deezer,MusicBrainz --refresh

Sources are matched by the names in nasheed-db.json, so nothing can quietly drop
out of the list: every source is either queried, or printed with the reason it
cannot be (a missing key, or a site with no API).

Responses are cached per artist and per source under data/harvest_cache/, so a
second run costs nothing. `--refresh` ignores the cache.

Credentials are read from the environment and never written anywhere:

    export DISCOGS_TOKEN=...        # discogs.com/settings/developers  (free)
    export LASTFM_API_KEY=...       # last.fm/api/account/create       (free)
    export SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=...   (free)
    export YOUTUBE_API_KEY=...      # console.cloud.google.com         (free)

Output: data/harvest.json, one entry per artist with whatever each source said.

Licence note, because this library's own rules apply to its tooling: Spotify's
Developer Terms forbid storing or aggregating its content, and YouTube forbids
keeping metadata past 30 days. harvest.json is therefore a local worksheet and
is git-ignored — read it, act on it, do not publish it or commit it.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_db, norm, slug  # noqa: E402

CACHE = ROOT / "data" / "harvest_cache"
UA = "nasheed-library-harvester/1.0 (+https://github.com/DantherXD/nasheed_project)"
TIMEOUT = 25


# ------------------------------------------------------------------ plumbing
class RateLimited(Exception):
    pass


_last_call = {}


def get(url, source, headers=None, accept_json=True):
    """One request, with the source's minimum interval and a patient retry.

    MusicBrainz answers 503 when it is merely busy, so a single refusal is not
    evidence that the source is unusable — back off, then give up loudly."""
    for attempt in range(4):
        wait = _last_call.get(source, 0) + RULES[source]["interval"] - time.time()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            _last_call[source] = time.time()
            if e.code in (429, 503):
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RateLimited(f"{e.code} from {source} after 4 attempts") from None
            raise
        finally:
            _last_call[source] = time.time()
    if not accept_json:
        return body.decode("utf-8", "replace")
    return json.loads(body.decode("utf-8", "replace"))


def cache_path(source, artist_id):
    return CACHE / slug(source) / f"{artist_id}.json"


def cached(source, artist_id, refresh=False):
    p = cache_path(source, artist_id)
    if p.exists() and not refresh:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return None


def store(source, artist_id, payload):
    p = cache_path(source, artist_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def q(name):
    return urllib.parse.quote(name)


# ------------------------------------------------------------------ adapters
# Each returns a small dict; the harvester stores whatever comes back.

def a_musicbrainz(name, artist):
    d = get(f"https://musicbrainz.org/ws/2/artist?query=artist:{q(name)}&fmt=json&limit=8",
            "MusicBrainz")
    out = []
    for a in d.get("artists", [])[:8]:
        out.append({
            "name": a.get("name"),
            "mbid": a.get("id"),
            "country": a.get("country"),
            "type": a.get("type"),
            "disambiguation": a.get("disambiguation"),
            "begin": a.get("life-span", {}).get("begin"),
            "tags": [t["name"] for t in (a.get("tags") or [])][:8],
            "url": f"https://musicbrainz.org/artist/{a.get('id')}",
        })
    return {"hits": out}


def a_deezer(name, artist):
    d = get("https://api.deezer.com/search/artist?" + urllib.parse.urlencode({"q": name, "limit": 8}),
            "Deezer")
    out = []
    for a in d.get("data", [])[:8]:
        out.append({"name": a.get("name"), "id": a.get("id"), "fans": a.get("nb_fan"),
                    "albums": a.get("nb_album"), "url": a.get("link")})
    return {"hits": out}


def a_archive(name, artist):
    params = [
        ("q", f'(title:("{name}") OR creator:("{name}")) AND mediatype:audio'),
        ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator"), ("fl[]", "licenseurl"),
        ("rows", "12"), ("page", "1"), ("output", "json"),
    ]
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    d = get(url, "Internet Archive")
    docs = d.get("response", {}).get("docs", [])
    return {"total": d.get("response", {}).get("numFound", 0),
            "hits": [{"identifier": x.get("identifier"), "title": x.get("title"),
                      "creator": x.get("creator"), "licence": x.get("licenseurl"),
                      "url": f"https://archive.org/details/{x.get('identifier')}"} for x in docs[:12]]}


def a_wikidata(name, artist):
    d = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
        "action": "wbsearchentities", "search": name, "language": "en",
        "uselang": "en", "limit": 8, "format": "json"}), "Wikidata")
    hits = [{"id": h.get("id"), "label": h.get("label"), "description": h.get("description"),
             "url": f"https://www.wikidata.org/wiki/{h.get('id')}"} for h in d.get("search", [])[:8]]
    # Arabic label for the same item, when the name came in Latin script
    return {"hits": hits}


def a_wikipedia(name, artist):
    out = {}
    for lang in ("en", "ar"):
        try:
            d = get(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": name, "srlimit": 5,
                "format": "json"}), "Wikipedia")
            out[lang] = [{"title": h["title"],
                          "url": f"https://{lang}.wikipedia.org/wiki/{q(h['title'].replace(' ', '_'))}"}
                         for h in d.get("query", {}).get("search", [])[:5]]
        except Exception as e:  # noqa: BLE001
            out[lang] = [{"error": str(e)}]
    return {"langs": out}


def a_wikipedia_categories(name, artist):
    cats = ["Category:Nasheed singers", "Category:Performers of Islamic music",
            "Category:Malaysian nasheed groups", "Category:Pakistani performers"]
    seen, found = set(), []
    for cat in cats:
        try:
            d = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "list": "categorymembers", "cmtitle": cat,
                "cmlimit": 500, "format": "json"}), "Wikipedia categories")
            for m in d.get("query", {}).get("categorymembers", []):
                seen.add(m["title"])
        except Exception:  # noqa: BLE001
            continue
    # the category listing is global; report whether this artist is inside it
    probe = norm(name)
    inside = sorted(t for t in seen if probe and probe in norm(t))
    return {"listed_in_categories": inside, "category_size": len(seen)}


def a_commons(name, artist):
    d = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": f"filetype:audio {name}",
        "srnamespace": 6, "srlimit": 5, "format": "json"}), "Wikimedia Commons")
    return {"hits": [{"title": h["title"],
                      "url": "https://commons.wikimedia.org/wiki/" + q(h["title"].replace(" ", "_"))}
                     for h in d.get("query", {}).get("search", [])[:5]]}


def a_huggingface(name, artist):
    d = get("https://huggingface.co/api/datasets?" + urllib.parse.urlencode({"search": "quran", "limit": 5}),
            "Hugging Face — Qur'an recitation datasets")
    return {"hits": [{"id": x.get("id"), "url": f"https://huggingface.co/datasets/{x.get('id')}"}
                     for x in (d if isinstance(d, list) else [])[:5]]}


def a_discogs(name, artist):
    token = os.environ.get("DISCOGS_TOKEN")
    d = get("https://api.discogs.com/database/search?" + urllib.parse.urlencode({
        "q": name, "type": "artist", "per_page": 8}),
        "Discogs", headers={"Authorization": f"Discogs token={token}"})
    return {"hits": [{"title": r.get("title"), "id": r.get("id"), "url": r.get("resource_url"),
                      "thumb": r.get("thumb")} for r in d.get("results", [])[:8]]}


def a_lastfm(name, artist):
    key = os.environ.get("LASTFM_API_KEY")
    d = get("https://ws.audioscrobbler.com/2.0/?" + urllib.parse.urlencode({
        "method": "artist.getinfo", "artist": name, "api_key": key,
        "format": "json", "autocorrect": 1}), "Last.fm")
    a = d.get("artist", {})
    tags = [t["name"] for t in (a.get("tags", {}) or {}).get("tag", [])]
    return {"name": a.get("name"), "listeners": a.get("stats", {}).get("listeners"),
            "playcount": a.get("stats", {}).get("playcount"), "tags": tags,
            "url": a.get("url")}


def a_spotify(name, artist):
    cid, secret = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
    import base64
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    # the token endpoint needs a POST, so it does not go through get()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=b"grant_type=client_credentials",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        access = json.loads(r.read().decode())["access_token"]
    d = get("https://api.spotify.com/v1/search?" + urllib.parse.urlencode({
        "q": name, "type": "artist", "limit": 5}),
        "Spotify", headers={"Authorization": f"Bearer {access}"})
    items = (d.get("artists", {}) or {}).get("items") or []
    return {"hits": [{"name": i["name"], "id": i["id"], "genres": i.get("genres", []),
                      "popularity": i.get("popularity"), "followers": i.get("followers", {}).get("total"),
                      "url": i["external_urls"]["spotify"]} for i in items]}


def a_youtube(name, artist):
    key = os.environ.get("YOUTUBE_API_KEY")
    d = get("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode({
        "part": "snippet", "type": "channel", "maxResults": 5, "q": name, "key": key}),
        "YouTube Data API")
    out = []
    for i in d.get("items", [])[:5]:
        cid = i.get("id", {}).get("channelId")
        out.append({"name": i.get("snippet", {}).get("channelTitle"), "id": cid,
                    "url": f"https://www.youtube.com/channel/{cid}"})
    return {"hits": out}


def a_genre_vocab(name, artist):
    """One request, not one per artist: the vocabulary is global."""
    body = get("https://musicbrainz.org/ws/2/genre/all?fmt=txt", "MusicBrainz genre vocabulary",
               accept_json=False)
    return {"genres": [g for g in body.splitlines() if g][:400]}


# name -> (function, interval seconds, credential env vars, note)
RULES = {
    "MusicBrainz": {"fn": a_musicbrainz, "interval": 1.1, "keys": [], "cf": "high"},
    "MusicBrainz genre vocabulary": {"fn": a_genre_vocab, "interval": 1.1, "keys": [], "cf": "high",
                                      "once": True},
    "Discogs": {"fn": a_discogs, "interval": 2.5, "keys": ["DISCOGS_TOKEN"], "cf": "high"},
    "Last.fm": {"fn": a_lastfm, "interval": 0.4, "keys": ["LASTFM_API_KEY"], "cf": "high"},
    "Deezer": {"fn": a_deezer, "interval": 0.3, "keys": [], "cf": "high"},
    "Spotify": {"fn": a_spotify, "interval": 0.4,
                "keys": ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"], "cf": "high"},
    "YouTube Data API": {"fn": a_youtube, "interval": 0.3, "keys": ["YOUTUBE_API_KEY"], "cf": "high"},
    "Internet Archive": {"fn": a_archive, "interval": 0.6, "keys": [], "cf": "high"},
    "Wikimedia Commons": {"fn": a_commons, "interval": 0.4, "keys": [], "cf": "med"},
    "Wikidata": {"fn": a_wikidata, "interval": 0.4, "keys": [], "cf": "high"},
    "Wikipedia categories": {"fn": a_wikipedia_categories, "interval": 0.4, "keys": [], "cf": "med"},
    "Hugging Face — Qur'an recitation datasets": {"fn": a_huggingface, "interval": 0.5, "keys": [], "cf": "med"},
}

# Sources with no machine interface. Kept here so --list can account for all of them.
MANUAL = {
    "Rate Your Music": "web only, scraping discouraged by the site",
    "NoCopyrightNasheeds": "paid subscription, no API",
    "Smithsonian Folkways": "catalogue pages only; audio is paid",
    "HMML — Music and Nasheeds from West Africa": "institutional web archive, no API",
    "GitHub nasheed collections": "a seed list of tracks, not an artist index",
    "HDtracks-free CC sources (Netlabels, FMA, Jamendo)": "per-site APIs and licences; netlabels first",
    "Islamic adhan and recitation APIs": "adhan and tilawa, not nasheed",
    "Assajda / Assabile": "no API — use tools/crawl_portals.py --source assajda",
    "Samaa Network (play.samaanetwork.net)": "no API — use tools/crawl_portals.py --source samaa",
}


def status(name):
    rule = RULES.get(name)
    if not rule:
        return "manual", MANUAL.get(name, "no adapter")
    missing = [k for k in rule["keys"] if not os.environ.get(k)]
    return ("ready", "") if not missing else ("key", ", ".join(missing))


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artist", help="one artist name to look up")
    p.add_argument("--limit", type=int, default=0, help="stop after N artists")
    p.add_argument("--source", default="", help="comma-separated source names")
    p.add_argument("--out", default="data/harvest.json",
                   help="where to write; keep it local, it is git-ignored on purpose")
    p.add_argument("--refresh", action="store_true", help="ignore the cache")
    p.add_argument("--check", action="store_true", help="test every ready source once")
    p.add_argument("--list", action="store_true", help="show every source and its status")
    p.add_argument("--sleep-scale", type=float, default=1.0, help="multiply all intervals")
    args = p.parse_args()

    db = load_db()
    names = [s["n"] for s in db["sources"]]

    if args.list or args.check:
        ready = keyed = manual = 0
        for n in names:
            st, why = status(n)
            marker = {"ready": "  query", "key": "  needs", "manual": "  skip "}[st]
            if st == "ready":
                ready += 1
            elif st == "key":
                keyed += 1
            else:
                manual += 1
            print(f"{marker}  {n:52} {why or RULES[n]['cf'] + ' confidence'}")
        print(f"\n{len(names)} sources · {ready} queryable now · {keyed} need a free key · {manual} web-only")
        if args.check:
            print("\nprobing the queryable ones against 'Maher Zain'…")
            for n in names:
                if status(n)[0] != "ready":
                    continue
                try:
                    r = RULES[n]["fn"]("Maher Zain", {"n": "x", "ar": ""})
                    got = len(r.get("hits", [])) if isinstance(r, dict) else "?"
                    print(f"  ok    {n}  ({got} hits)")
                except RateLimited as e:
                    print(f"  slow  {n}  {e}")
                except Exception as e:  # noqa: BLE001
                    print(f"  fail  {n}  {type(e).__name__}: {e}")
        return

    for n in names:
        if n in RULES:
            RULES[n]["interval"] *= max(0.2, args.sleep_scale)

    wanted = [n for n in names if n in RULES and status(n)[0] == "ready"]
    if args.source:
        pick = {s.strip().lower() for s in args.source.split(",") if s.strip()}
        wanted = [n for n in wanted if n.lower() in pick]
    once = [n for n in wanted if RULES[n].get("once")]
    wanted = [n for n in wanted if not RULES[n].get("once")]
    if not wanted:
        print("nothing to query — run --check to see which sources need keys")
        return

    artists = db["artists"]
    if args.artist:
        probe = norm(args.artist)
        artists = [a for a in artists if probe in norm(a["n"]) or probe in norm(a.get("ar", ""))]
        if not artists:
            print(f"no artist matching {args.artist!r} in the database")
            return
    if args.limit:
        artists = artists[:args.limit]

    out_path = Path(args.out)
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    print(f"{len(artists)} artists × {len(wanted)} sources\n  {', '.join(wanted)}\n")

    for source in once:  # global lookups, fetched once for the whole run
        try:
            results.setdefault("_meta", {})[source] = RULES[source]["fn"]("", {})
            print(f"fetched {source}")
        except Exception as e:  # noqa: BLE001
            print(f"  {source} failed: {e}")

    stats = {n: {"hits": 0, "empty": 0, "error": 0, "cached": 0, "why": ""} for n in wanted}
    rate_limited = set()
    for i, artist in enumerate(artists, 1):
        entry = results.setdefault(artist["id"], {"name": artist["n"], "ar": artist.get("ar", "")})
        for source in wanted:
            if source in rate_limited:
                entry[source] = {"error": "rate limited earlier in this run"}
                continue
            got = cached(source, artist["id"], args.refresh)
            if got is None:
                try:
                    got = RULES[source]["fn"](artist["n"], artist)
                except RateLimited as e:
                    print(f"  {source} is throttling ({e}) — skipping it for the rest of this run")
                    rate_limited.add(source)
                    got = {"error": "rate limited"}
                except Exception as e:  # noqa: BLE001
                    got = {"error": f"{type(e).__name__}: {e}"}
                store(source, artist["id"], got)
            else:
                stats[source]["cached"] += 1
            entry[source] = got
            st = stats[source]
            if got.get("error"):
                st["error"] += 1
                st["why"] = st["why"] or str(got["error"])[:90]
            elif got.get("hits") or len(got) > 1:
                st["hits"] += 1
            else:
                st["empty"] += 1
        print(f"[{i}/{len(artists)}] {artist['n']}")
        if i % 10 == 0:
            out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nwritten {out_path} — {len(artists)} artists")
    for s in wanted:
        st = stats[s]
        line = (f"  {s:52} hits {st['hits']:3}  empty {st['empty']:3}  "
                f"errors {st['error']:3}  from cache {st['cached']:3}")
        print(line + (f"   last error: {st['why']}" if st["why"] else ""))


if __name__ == "__main__":
    main()
