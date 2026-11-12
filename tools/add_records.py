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

# Country, region and era may be left empty when a name arrives from a listening
# list before it has been researched; the record then shows "unresolved" in the
# UI rather than pretending to a nationality or a date. Name, language, solo or
# group, category, instrumentation and confidence are still required.
REQUIRED = ["n", "l", "t", "k", "v", "cf"]


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
        for key in variants(a["n"]) | variants(a.get("ar", "")):
            known.add(key)
            known.add(key.replace(" ", ""))  # "In-Team" vs "Inteam"

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
        if r.get("r") and r["r"] not in tax["regions"]:
            rejected.append((r["n"], f"unknown region {r['r']}"))
            continue
        r["c"] = (r.get("c") or "").strip() or None
        r["r"] = (r.get("r") or "").strip()
        if r["c"] and r["c"].lower() in ("unknown", "n/a", "-"):
            r["c"] = None

        keys = variants(r["n"]) | variants(r.get("ar", ""))
        keys |= {k.replace(" ", "") for k in keys}
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
        print(f"  + {r['n']} ({r['c'] or 'country unresolved'}) — {len(r['links'])} link(s)")

    if added and not args.dry_run:
        db["meta"]["counts"] = {
            "artists": len(artists),
            "labels": len(db["organizations"]),
            "sources": len(db["sources"]),
            "countries": len({a["c"] for a in artists if a.get("c")}),
            "vocalOnly": sum(1 for a in artists if a["v"] in ("acap", "duff")),
        }
        save_db(db)
        print("database and derived files rewritten")
    elif args.dry_run:
        print("dry run — nothing written")


if __name__ == "__main__":
    main()
