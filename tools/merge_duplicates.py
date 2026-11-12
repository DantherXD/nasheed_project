#!/usr/bin/env python3
"""Merge duplicate records, keeping both sets of links and sources.

    python3 tools/merge_duplicates.py merges.json --dry-run
    python3 tools/merge_duplicates.py merges.json

The file is a JSON list of {"keep": "<id>", "drop": "<id>", "why": "..."}.
The kept record absorbs everything the dropped one had: links of a type it lacks
are added, references are unioned, empty fields are filled. When both records
hold the same kind of link — two different Apple Music profiles for one name —
the extra is kept as an "alternate" note instead of being thrown away, because
which profile belongs to the real person is a research question, not a merge
detail.

The dropped id is remembered in meta.aliases, and tools/build_site.py turns it
into a redirect page so an existing link to the old record still lands.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import cap_links, load_db, save_db  # noqa: E402

CONF = {"low": 0, "med": 1, "high": 2}
FILL = ["c", "r", "e", "l", "w", "nt", "u"]


def merge(keep, drop, why=""):
    added_links, added_refs, filled, alternates = [], [], [], []

    have = {l["t"] for l in keep.get("links", [])}
    for link in drop.get("links", []):
        if link.get("t") in have:
            alternates.append(f'{link["t"]}: {link["u"]}')
        else:
            keep.setdefault("links", []).append(link)
            have.add(link["t"])
            added_links.append(link["t"])

    seen = {(r.get("t"), r.get("u")) for r in keep.get("refs", [])}
    for ref in drop.get("refs", []):
        if (ref.get("t"), ref.get("u")) not in seen:
            keep.setdefault("refs", []).append(ref)
            seen.add((ref.get("t"), ref.get("u")))
            added_refs.append(ref.get("t"))

    for field in FILL:
        if not keep.get(field) and drop.get(field):
            keep[field] = drop[field]
            filled.append(field)

    # the Arabic script usually arrives as the dropped record's *name*, not its
    # ar field, so take it from either — losing it would lose the only spelling
    # a reader can search for
    arabic = re.compile(r"[\u0600-\u06ff]")
    if not keep.get("ar") and drop.get("ar"):
        keep["ar"] = drop["ar"]
        filled.append("ar")
    elif not keep.get("ar") and arabic.search(drop.get("n", "")) and not arabic.search(keep.get("n", "")):
        keep["ar"] = drop["n"]
        filled.append("ar (native spelling taken from the merged name)")

    if CONF.get(drop.get("cf", "low"), 0) > CONF.get(keep.get("cf", "low"), 0):
        keep["cf"] = drop["cf"]

    note = f"Merged with the record \"{drop['n']}\" ({why})" if why else f"Merged with \"{drop['n']}\""
    if alternates:
        note += "; alternate profile kept here rather than resolved: " + ", ".join(alternates)
    keep["nt"] = (keep.get("nt", "").rstrip(".") + ". " + note + ".") if keep.get("nt") else note + "."

    cap_links(keep)
    return {"added_links": added_links, "added_refs": added_refs, "filled": filled,
            "alternates": alternates}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("merges", help="JSON list of {keep, drop} pairs")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    spec = json.loads(Path(args.merges).read_text(encoding="utf-8"))
    db = load_db()
    by_id = {a["id"]: a for a in db["artists"]}
    aliases = db.setdefault("meta", {}).setdefault("aliases", {})

    done, skipped = [], []
    for item in spec:
        keep_id, drop_id = item.get("keep"), item.get("drop")
        if keep_id not in by_id or drop_id not in by_id:
            skipped.append((keep_id, drop_id, "id not found"))
            continue
        if keep_id == drop_id:
            skipped.append((keep_id, drop_id, "same record"))
            continue
        keep, drop = by_id[keep_id], by_id[drop_id]
        result = merge(keep, drop, item.get("why", ""))
        aliases[drop_id] = keep_id
        db["artists"] = [a for a in db["artists"] if a["id"] != drop_id]
        by_id.pop(drop_id, None)
        done.append((keep_id, drop["n"], drop_id, result))

    print(f"merged {len(done)} · skipped {len(skipped)}")
    for keep_id, drop_name, drop_id, result in done:
        print(f"\n  {keep_id}  ←  {drop_id} ({drop_name})")
        print(f"    links added: {', '.join(result['added_links']) or 'none'} · "
              f"refs added: {', '.join(result['added_refs']) or 'none'} · "
              f"fields filled: {', '.join(result['filled']) or 'none'}")
        if result["alternates"]:
            print(f"    kept as alternates: {'; '.join(result['alternates'])}")
    for keep_id, drop_id, why in skipped:
        print(f"  skipped {keep_id} / {drop_id}: {why}")

    if done and not args.dry_run:
        db["meta"]["counts"] = {
            "artists": len(db["artists"]),
            "labels": len(db["organizations"]),
            "sources": len(db["sources"]),
            "countries": len({a["c"] for a in db["artists"] if a.get("c")}),
            "vocalOnly": sum(1 for a in db["artists"] if a["v"] in ("acap", "duff")),
        }
        save_db(db)
        print(f"\ndatabase now holds {len(db['artists'])} records · "
              f"{len(aliases)} alias(es) for redirects")
    elif args.dry_run:
        print("\ndry run — nothing written")


if __name__ == "__main__":
    main()
