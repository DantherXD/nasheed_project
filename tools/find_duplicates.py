#!/usr/bin/env python3
"""Report likely duplicate artist records.

    python3 tools/find_duplicates.py                # report
    python3 tools/find_duplicates.py --write        # also write data/duplicates.json

The database is now assembled from sources that overlap — streaming catalogues,
competition rosters, portal scrapes — so the same munshid can arrive twice with
a different transliteration, a different id, and half a discography on each
record. This does not merge anything: it ranks suspicious pairs so a human can
decide, because merging two people who merely share a name is worse than
carrying a duplicate.
"""
import argparse
import difflib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_db, norm, romanize, skeleton, variants  # noqa: E402

THRESHOLD = 0.86

# A shared given name proves nothing: half the Egyptian roster is a Mohammed.
# The surname (nisba, family name) is what identifies a person, so candidates
# must agree on it before the whole-name ratio is even considered.
GIVEN_NAME_NOISE = {"al", "el", "abdel", "abd", "bint", "bin", "ould", "sheikh", "shaykh",
                    "the", "hajj", "haji", "mohamed", "mohammed", "muhammad", "ahmed", "ahmad"}


def link_hosts(a):
    return {l["u"].split("/")[2] for l in a.get("links", []) if l.get("u", "").count("/") > 2}


def _skeleton_of(token):
    return "".join(c for c in romanize(token).lower() if c.isalnum() and c not in "aeiouy")


def name_tokens(a):
    return [t for t in norm(a["n"]).split() if t and t not in GIVEN_NAME_NOISE]


def surname_key(a):
    """Skeleton of the last meaningful token — the family name."""
    tokens = name_tokens(a)
    return _skeleton_of(tokens[-1]) if tokens else ""


def given_key(a):
    """Skeleton of the first meaningful token — the person's own name."""
    tokens = name_tokens(a)
    return _skeleton_of(tokens[0]) if tokens else ""


def whole_key(a):
    """Consonants of the whole name, spaces removed: 'In-Team' == 'Inteam'."""
    joined = "".join(norm(a["n"]).split())
    return _skeleton_of(joined)


def score(a, b):
    """Similarity of two records, or None when they cannot be the same person."""
    fa, fb = norm(a["n"]), norm(b["n"])
    if not fa or not fb:
        return None

    reasons = []
    if fa == fb:
        reasons.append("identical name")

    wa, wb = whole_key(a), whole_key(b)
    same_skeleton = bool(wa) and wa == wb and len(wa) >= 4

    sa, sb = surname_key(a), surname_key(b)
    surname_close = bool(sa and sb) and (
        sa == sb or sa in sb or sb in sa
        or difflib.SequenceMatcher(None, sa, sb).ratio() >= 0.8)
    # two brothers share a surname, so the given name has to agree as well
    ga, gb = given_key(a), given_key(b)
    given_close = bool(ga and gb) and (
        ga == gb or difflib.SequenceMatcher(None, ga, gb).ratio() >= 0.6)
    same_surname = surname_close and given_close

    if not (fa == fb or same_skeleton or same_surname):
        return None

    ratio = difflib.SequenceMatcher(None, fa, fb).ratio()
    same_country = bool(a.get("c")) and a.get("c") == b.get("c")

    if fa == fb:
        base = 1.0
    elif same_skeleton:
        base = 0.95 + min(ratio, 0.04)
        reasons.append("names reduce to the same consonants")
    else:
        required = 0.72 if same_country else 0.8
        if ratio < required:
            return None
        base = ratio
        reasons.append(f"same family name ({sa} ~ {sb}) and given name ({ga} ~ {gb})")

    value = base
    if same_country:
        value += 0.02
        reasons.append("same country")
    if a.get("v") == b.get("v") and a.get("k") == b.get("k"):
        value += 0.01
    if link_hosts(a) & link_hosts(b):
        value += 0.02
        reasons.append("overlapping link hosts")
    if set(variants(a["n"])) & set(variants(b["n"])):
        reasons.append("portal name variants coincide")
    return min(value, 1.0), reasons


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="write data/duplicates.json")
    p.add_argument("--threshold", type=float, default=THRESHOLD)
    p.add_argument("--limit", type=int, default=25)
    args = p.parse_args()

    artists = load_db()["artists"]
    pairs = []
    for i, a in enumerate(artists):
        for b in artists[i + 1:]:
            result = score(a, b)
            if not result:
                continue
            value, reasons = result
            if value >= args.threshold:
                pairs.append({
                    "score": round(value, 3),
                    "a": {"id": a["id"], "n": a["n"], "c": a.get("c"), "cf": a.get("cf"),
                          "links": len(a.get("links", []))},
                    "b": {"id": b["id"], "n": b["n"], "c": b.get("c"), "cf": b.get("cf"),
                          "links": len(b.get("links", []))},
                    "reasons": reasons,
                })
    pairs.sort(key=lambda x: -x["score"])

    print(f"{len(artists)} records · {len(pairs)} pair(s) at or above {args.threshold}")
    for p_ in pairs[:args.limit]:
        print(f'\n{p_["score"]:.3f}  {p_["a"]["n"]} ({p_["a"]["c"] or "?"}) '
              f'<-> {p_["b"]["n"]} ({p_["b"]["c"] or "?"})')
        print(f'       {p_["a"]["id"]} / {p_["b"]["id"]}')
        print(f'       {", ".join(p_["reasons"])}')

    if args.write:
        out = ROOT / "data" / "duplicates.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": len(artists),
            "threshold": args.threshold,
            "pairs": pairs,
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
