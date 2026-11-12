#!/usr/bin/env python3
"""Add fully-researched records to the database.

    python3 tools/add_records.py records.json --dry-run
    python3 tools/add_records.py records.json

The file is a JSON list. Nothing half-filled gets in: every required field is
checked, the category and instrumentation codes must exist in the taxonomy, the
region must be one of the eleven, and a country is mandatory — "unknown" is not
a country, it is a research task. Records the database already has are skipped,
matched on either name.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import cap_links, is_latin, load_db, save_db, slug, variants  # noqa: E402

REQUIRED = ["n", "c", "r", "l", "e", "t", "k", "v", "cf"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("records", help="JSON list of records")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    incoming = json.loads(Path(args.records).read_text(encoding="utf-8"))
    if isinstance(incoming, dict):
        incoming = incoming.get("records", [])

    db = load_db()
    tax = db["taxonomy"]
    artists = db["artists"]
    known, ids = set(), {a["id"] for a in artists}
    for a in artists:
        known |= variants(a["n"]) | variants(a.get("ar", ""))

    added, skipped, rejected = [], [], []
    for r in incoming:
        missing = [f for f in REQUIRED if not str(r.get(f, "")).strip()]
        if missing:
            rejected.append((r.get("n", "?"), f"missing {', '.join(missing)}"))
            continue
        if r["k"] not in tax["categories"]:
            rejected.append((r["n"], f"unknown category code {r['k']}"))
            continue
        if r["v"] not in tax["instrumentation"]:
            rejected.append((r["n"], f"unknown instrumentation code {r['v']}"))
            continue
        if r["r"] not in tax["regions"]:
            rejected.append((r["n"], f"unknown region {r['r']}"))
            continue
        if r["c"].strip().lower() in ("unknown", "n/a", "-"):
            rejected.append((r["n"], "country must be resolved, not 'unknown'"))
            continue

        keys = variants(r["n"]) | variants(r.get("ar", ""))
        if keys & known:
            skipped.append(r["n"])
            continue

        rid = r.get("id") or slug(r["n"])
        if not rid:
            if not r.get("id"):
                rejected.append((r["n"], "non-Latin name needs an explicit id"))
                continue
        base, n = rid, 2
        while rid in ids:
            rid = f"{base}-{n}"
            n += 1
        ids.add(rid)

        record = dict(r)
        record["id"] = rid
        record["catLabel"] = tax["categories"][r["k"]]
        record["vocalLabel"] = tax["instrumentation"][r["v"]]
        record.setdefault("links", [])
        record.setdefault("refs", [])
        cap_links(record)
        artists.append(record)
        known |= keys
        added.append(record)

    print(f"added {len(added)} · already present {len(skipped)} · rejected {len(rejected)}")
    for name, why in rejected:
        print(f"  rejected {name}: {why}")
    if skipped:
        print("  already present:", ", ".join(skipped[:12]) + (" …" if len(skipped) > 12 else ""))
    for r in added[:8]:
        print(f"  + {r['n']} ({r['c']}) — {len(r['links'])} link(s)")

    if added and not args.dry_run:
        db["meta"]["counts"] = {
            "artists": len(artists),
            "labels": len(db["organizations"]),
            "sources": len(db["sources"]),
            "countries": len({a["c"] for a in artists}),
            "vocalOnly": sum(1 for a in artists if a["v"] in ("acap", "duff")),
        }
        save_db(db)
        print("database and derived files rewritten")
    elif args.dry_run:
        print("dry run — nothing written")


if __name__ == "__main__":
    main()
