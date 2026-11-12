#!/usr/bin/env python3
"""Check a list of artist names against the database.

    python3 tools/match_names.py data/wanted_artists.txt

Prints what is already covered, what is new, and writes data/name_matches.json.
Matching is on normalised names, so honorifics ("المنشد", "Firqat"), bilingual
labels ("Mishari Al Baghli مشاري البغلي") and shortened forms ("مشاري العفاسي"
for "مشاري بن راشد العفاسي") all resolve to the same record.

Combined entries such as "Maher Zain & Harris J" are split and matched part by
part, so one known name inside a duet is not reported as missing.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_db, norm, variants  # noqa: E402

SPLIT_CREDIT = re.compile(r"\s*(?:&|,|;|\+|\band\b|\bft\.?\b|\bfeat\.?\b)\s*", re.I)
SKIP = {"playlists", "various artists", "unknown", "various"}


def fold(text):
    """Collapse transliteration noise: Mishari/Mishary, Al-Kandari/Alkandari,
    Abdulrahman/Abdurrahman, doubled letters, kh/dh/th/sh/q."""
    s = text.replace(" ", "")
    for a, b in (("dh", "d"), ("th", "t"), ("sh", "s"), ("kh", "k"), ("ph", "f"),
                 ("q", "k"), ("y", "i"), ("ou", "u"), ("oo", "u"), ("ee", "i"), ("aa", "a")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


def build_index(artists):
    index, folded = {}, {}
    for a in artists:
        for key in variants(a["n"]) | variants(a.get("ar", "")):
            index.setdefault(key, a["id"])
            index.setdefault(key.replace(" ", ""), a["id"])
            folded.setdefault(fold(key), a["id"])
    return index, folded


def match(name, index, folded):
    keys = variants(name)
    for key in keys:
        if key in index or key.replace(" ", "") in index:
            return index.get(key) or index[key.replace(" ", "")], "exact"
    for key in keys:
        if len(key) > 5 and fold(key) in folded:
            return folded[fold(key)], "exact"
    # token-subset: playlists drop the patronymic, so "مشاري العفاسي" is a
    # shortened "مشاري بن راشد العفاسي"
    tokens = [(set(k.split()), ident) for k, ident in index.items() if len(k.split()) > 1]
    for key in keys:
        probe = set(key.split())
        if len(probe) < 2:
            continue
        for tok, ident in tokens:
            if probe <= tok or (len(tok) >= 2 and tok <= probe):
                return ident, "partial"
    best, score = None, 0.0
    for key in keys:
        fk = fold(key)
        if len(fk) < 7:
            continue
        for folded_key, ident in folded.items():
            r = difflib.SequenceMatcher(None, fk, folded_key).ratio()
            if r > score:
                best, score = ident, r
    if score >= 0.88:
        return best, "close"
    return None, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("names", nargs="?", default="data/wanted_artists.txt")
    p.add_argument("--out", default="data/name_matches.json")
    args = p.parse_args()

    raw = Path(args.names).read_text(encoding="utf-8").splitlines()
    names = []
    for line in raw:
        line = line.strip().strip("\ufeff")
        if line and not line.startswith("#") and line.lower() not in SKIP:
            if line not in names:
                names.append(line)

    db = load_db()
    artists = db["artists"]
    index, folded = build_index(artists)

    found, partial, missing, close = [], [], [], []
    for name in names:
        parts = [x for x in SPLIT_CREDIT.split(name) if x.strip()]
        hits = []
        for part in parts or [name]:
            ident, how = match(part, index, folded)
            if ident:
                hits.append((ident, how, part))
        if any(h[1] == "close" for h in hits):
            close.append({"name": name, "ids": [h[0] for h in hits]})
        elif not hits:
            missing.append(name)
        elif all(h[1] == "exact" for h in hits) and len(hits) == len(parts):
            found.append({"name": name, "ids": [h[0] for h in hits]})
        else:
            partial.append({"name": name, "ids": [h[0] for h in hits],
                            "unmatched": [p_ for p_ in (parts or [name])
                                          if not any(h[2] == p_ for h in hits)]})

    print(f"{len(names)} names · {len(found)} already in the database · "
          f"{len(partial)} partial · {len(close)} close (check) · {len(missing)} new\n")
    if close:
        print("close matches, same person or a namesake — check before adding:")
        for item in close:
            print(f"  {item['name']}  ->  {', '.join(item['ids'])}")
        print()
    if partial:
        print("partial matches (one credited name unknown):")
        for item in partial:
            print(f"  {item['name']}  ->  {', '.join(item['ids'])}"
                  f"   [missing: {', '.join(item['unmatched'])}]")
        print()
    if missing:
        print("not in the database:")
        for name in missing:
            print(f"  {name}")
        print()

    Path(args.out).write_text(
        json.dumps({"found": found, "partial": partial, "close": close, "missing": missing},
                   ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"written {args.out}")


if __name__ == "__main__":
    main()
