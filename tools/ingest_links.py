#!/usr/bin/env python3
"""Merge streaming pages found by fetch_links.py into the database.

    python3 tools/ingest_links.py data/link_candidates.json --dry-run
    python3 tools/ingest_links.py data/link_candidates.json

Each candidate URL is checked against its service's real host before it is
written, an artist that already has that service is left alone, and the
two-listening-link cap still applies.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import cap_links, link_type, load_db, save_db, variants  # noqa: E402

SERVICE_TO_TYPE = {"apple": "apple", "deezer": "deezer", "spotify": "spotify", "youtube": "youtube"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("candidates", help="JSON written by fetch_links.py")
    p.add_argument("--only", default="", help="comma-separated services to apply")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    incoming = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    only = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    db = load_db()

    index = {}
    for a in db["artists"]:
        for key in variants(a["n"]) | variants(a.get("ar", "")):
            index.setdefault(key, a)

    added, already, unknown, bad = [], [], [], []
    for name, entry in incoming.items():
        if name.startswith("_") or not isinstance(entry, dict):
            continue
        record = next((index[k] for k in variants(name) if k in index), None)
        if not record:
            unknown.append(name)
            continue
        for service, hit in entry.items():
            kind = SERVICE_TO_TYPE.get(service)
            url = hit.get("url") if isinstance(hit, dict) else hit
            if not (kind and url):
                continue
            if only and kind not in only:
                continue
            if link_type(url) != kind:
                bad.append((name, kind, url))
                continue
            if any(l["t"] == kind for l in record.get("links", [])):
                already.append(f"{name} ({kind})")
                continue
            record.setdefault("links", []).append({"t": kind, "u": url})
            added.append(f"{record['n']} ({kind})")

    for record in {id(r): r for r in index.values()}.values():
        cap_links(record)

    print(f"added {len(added)} · already had one {len(already)} · "
          f"not in db {len(unknown)} · rejected url {len(bad)}")
    for line in added[:20]:
        print("  +", line)
    if len(added) > 20:
        print(f"  … {len(added) - 20} more")
    if unknown:
        print("not in db:", ", ".join(unknown[:12]) + (" …" if len(unknown) > 12 else ""))
    for name, kind, url in bad[:8]:
        print(f"  rejected {name}: {kind} expected, got {url}")

    if added and not args.dry_run:
        save_db(db)
        print("database and derived files rewritten")
    elif args.dry_run:
        print("dry run — nothing written")


if __name__ == "__main__":
    main()
