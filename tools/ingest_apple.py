#!/usr/bin/env python3
"""Merge Apple Music pages found by fetch_apple.py into the database.

    python3 tools/ingest_apple.py apple_links.json --dry-run
    python3 tools/ingest_apple.py apple_links.json

Every URL is checked to be a music.apple.com artist page before it is written,
and artists that already have one are left alone.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import cap_links, is_latin, load_db, norm, save_db  # noqa: E402


def valid(url):
    return (url or "").startswith("https://music.apple.com/") and "/artist/" in url


def main():
    p = argparse.ArgumentParser()
    p.add_argument("results", help="JSON file written by fetch_apple.py")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    incoming = json.loads(Path(args.results).read_text(encoding="utf-8"))
    db = load_db()

    index = {}
    for a in db["artists"]:
        for key in (norm(a["n"]), norm(a.get("ar", ""))):
            if key:
                index.setdefault(key, a)

    added, already, unknown, bad, dropped = 0, 0, [], [], 0
    for name, info in incoming.items():
        if name.startswith("_"):
            continue
        url = info.get("url") if isinstance(info, dict) else info
        if not valid(url):
            bad.append(name)
            continue
        record = index.get(norm(name))
        if not record:
            unknown.append(name)
            continue
        if any(l["t"] == "apple" for l in record.get("links", [])):
            already += 1
            continue
        record.setdefault("links", []).append({"t": "apple", "u": url})
        dropped += len(cap_links(record))
        added += 1

    print(f"added {added} · already had one {already} · invalid url {len(bad)} · "
          f"not in db {len(unknown)}")
    if unknown:
        print("not in db:", ", ".join(unknown[:15]) + (" …" if len(unknown) > 15 else ""))
    if bad:
        print("rejected:", ", ".join(bad[:10]))
    if added and not args.dry_run:
        save_db(db)
        print("database and derived files rewritten")
    elif args.dry_run:
        print("dry run — nothing written")


if __name__ == "__main__":
    main()
