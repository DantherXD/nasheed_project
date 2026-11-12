"""Shared helpers for the nasheed tools.

The database is the source of truth; every generated file (CSV exports, the
single-file legacy app, site/data.json) is rebuilt from it by save_db() so the
copies can never drift.
"""
import csv
import io
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "nasheed-db.json"
CACHE = ROOT / "artifacts" / "src"

# Where you can hear an artist. Order is preference: when a record has more than
# MAX_LISTEN of these, the tail is dropped rather than kept as clutter.
LISTEN_ORDER = ["youtube", "apple", "spotify", "deezer", "amazon"]
MAX_LISTEN = 2

# Order links appear on an artist page; `u` is the first entry.
LINK_ORDER = ["linktree", "official"] + LISTEN_ORDER + ["catalogue"]
REF_ORDER = ["wiki", "archive", "press", "paper"]

LINK_DOMAINS = {
    "apple": ("music.apple.com",),
    "spotify": ("open.spotify.com",),
    "deezer": ("deezer.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "amazon": ("music.amazon.com", "amazon.com"),
    "linktree": ("linktr.ee", "linktree.com", "beacons.ai", "carrd.co"),
}


def load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _write_csv(path, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8-sig", newline="")


def related_map(artists, limit=6):
    """For each record, the records a reader should look at next.

    A shared country outweighs a shared category, which outweighs shared
    instrumentation; a shared region is only a tie-breaker. The point is a path
    from one artist to another, which is what a directory lacks. Computed here so
    the browser never has to: it ships inside site/data.json as `rel`.
    """
    by_country, by_cat, by_region = defaultdict(list), defaultdict(list), defaultdict(list)
    for a in artists:
        if a.get("c"):
            by_country[a["c"]].append(a)
        by_cat[a["k"]].append(a)
        if a.get("r"):
            by_region[a["r"]].append(a)

    names = {a["id"]: a["n"] for a in artists}
    out = {}
    for a in artists:
        score = {}

        def bump(other, weight):
            if other["id"] != a["id"]:
                score[other["id"]] = score.get(other["id"], 0) + weight

        for b in by_country.get(a.get("c"), ()) if a.get("c") else ():
            bump(b, 3)
            if b["k"] == a["k"]:
                bump(b, 2)
            if b["v"] == a["v"]:
                bump(b, 1)
        for b in by_cat[a["k"]]:
            bump(b, 1)
        for b in by_region.get(a.get("r"), ()) if a.get("r") else ():
            bump(b, 1)

        ranked = sorted(score.items(), key=lambda kv: (-kv[1], names.get(kv[0], "")))
        out[a["id"]] = [other_id for other_id, _ in ranked[:limit]]
    return out


# ---------------------------------------------------------------- search keys

_AR2LAT = {
    "ا": "a", "أ": "a", "إ": "a", "آ": "a", "ٱ": "a", "ب": "b", "ت": "t",
    "ث": "th", "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r",
    "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z",
    "ع": "a", "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ک": "k", "ل": "l",
    "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y", "ى": "a", "ی": "y",
    "ة": "a", "ء": "", "ؤ": "w", "ئ": "y", "پ": "p", "چ": "ch", "گ": "g",
    "ڤ": "v", "ژ": "zh",
}
_VOWEL = re.compile(r"[aeiouy]")


def romanize(text):
    """Arabic letters to Latin ones, so both scripts reach the same index."""
    return "".join(_AR2LAT.get(ch, ch) for ch in (text or ""))


def skeleton(text):
    """Consonant skeleton of a name.

    Transliteration varies wildly — "الدشناوي", "Al-Dishnawi" and "Dishnawi"
    are one person — but the consonants survive every spelling, so shrinking a
    name to them lets a Latin query reach an Arabic-only record.
    """
    spaced = re.sub(r"[^a-z0-9]+", " ", romanize(text).lower())
    keys = set()
    for token in spaced.split():
        bare = _VOWEL.sub("", token)
        if len(bare) >= 2:
            keys.add(bare)
        if token.startswith("al") and len(token) > 4:
            stripped = _VOWEL.sub("", token[2:])
            if len(stripped) >= 2:
                keys.add(stripped)
    whole = _VOWEL.sub("", spaced.replace(" ", ""))
    if len(whole) >= 3:
        keys.add(whole)
    return keys


def search_keys(artist, limit=16):
    """Every skeleton a record should answer to, from name, native name and id."""
    keys = set()
    for source in (artist.get("n", ""), artist.get("ar", ""), artist.get("id", "").replace("-", " ")):
        keys |= skeleton(source)
    return sorted(keys)[:limit]


def site_payload(db):
    """The database as the browser should receive it: `rel` and search keys added."""
    rel = related_map(db["artists"])
    out = dict(db)
    out["artists"] = [
        {**a, "rel": rel.get(a["id"], []), "s": search_keys(a)}
        for a in db["artists"]
    ]
    return out


def save_db(db):
    """Write the database and regenerate every derived file."""
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    artists = db["artists"]

    _write_csv(
        ROOT / "nasheed_artists.csv",
        ["name", "name_native_script", "country", "region", "language", "era",
         "solo_or_group", "category", "instrumentation", "key_works", "link",
         "confidence", "note", "links", "references"],
        [[a["n"], a.get("ar", ""), a["c"], a["r"], a["l"], a["e"], a["t"],
          a["catLabel"], a["vocalLabel"], a.get("w", ""), a.get("u", ""), a["cf"],
          a.get("nt", ""),
          "; ".join(f"{l['t']}={l['u']}" for l in a.get("links", [])),
          "; ".join(f"{r['t']}={r['u']}" for r in a.get("refs", []))]
         for a in artists],
    )

    # `rel` and `s` are derived, so they belong in the shipped payload, not the database file
    library = (ROOT / "nasheed-library.html").read_text(encoding="utf-8")
    payload = json.dumps(site_payload(db), ensure_ascii=False, separators=(",", ":"))
    library = re.sub(
        r'(<script type="application/json" id="db">)(.*?)(</script>)',
        lambda m: m.group(1) + payload + m.group(3),
        library, flags=re.S,
    )
    (ROOT / "nasheed-library.html").write_text(library, encoding="utf-8")

    (ROOT / "site" / "data.json").write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------- matching

_TRANSLIT = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "–": "-", "—": "-",
                          # Arabic letter folding: أ إ آ ٱ look like ا, ى like ي, ة like ه
                          "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه",
                          "ؤ": "و", "ئ": "ي"})
_DIACRITIC = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_NOISE = re.compile(
    r"\b(al[- ]?munshid|munshid|minshid|firqat|firqa|al[- ]?fannan|fannan|"
    r"the|artist|band|group|team|official|"
    r"المنشد|المنشدة|الفنان|الفنانة|فريق|فرقة|جوقة|الشيخ|الأستاذ|استاذ)\b",
    re.I,
)

# Portals label one artist twice: "مشاري العفاسي | Mishary Alafasy".
_SEPARATOR = re.compile(r"\s*(?:\||/|–|—|\s-\s)\s*")


def norm(text):
    """Normalise a name for comparison, Latin or Arabic.

    Folds case and accents, strips Arabic harakat, drops the honorifics the
    portals prepend ("المنشد", "الفنان", "Firqat"), so "المنشد عبدالله الجارالله"
    and "Abdullah Al-Jarallah" are comparable tokens.
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", str(text).translate(_TRANSLIT))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _DIACRITIC.sub("", s).lower()
    s = re.sub(r"[^\w\u0600-\u06ff]+", " ", s)
    s = re.sub(r"\s+", " ", _NOISE.sub(" ", s))
    return s.strip()


def variants(name):
    """Every comparable form of a name: the whole label, each side of a
    bilingual split, and each script run separately, so "Mishari Al Baghli
    مشاري البغلي" meets both "Mishari Al Baghli" and "مشاري البغلي"."""
    out = set()
    for part in [name or ""] + _SEPARATOR.split(name or ""):
        part = re.sub(r"\([^)]*\)", " ", part)
        pieces = [part] + re.findall(r"[\u0600-\u06ff\s]+|[A-Za-z\s'’\-.]+(?:\s*(?:&|and)\s*[A-Za-z\s'’\-.]*)?", part)
        for piece in pieces:
            key = norm(piece)
            if len(key) > 1:
                out.add(key)
    return out


def is_latin(text):
    return bool(re.search(r"[A-Za-z]", text or ""))


def slug(text):
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# ---------------------------------------------------------------- link rules

def _rank(link):
    order = LINK_ORDER + REF_ORDER
    return order.index(link["t"]) if link["t"] in order else len(order)


def cap_links(record):
    """Keep at most MAX_LISTEN listening links, best first; re-derive `u`."""
    links = [l for l in record.get("links", []) if l.get("t") and l.get("u")]
    listen, other = [], []
    for link in links:
        (listen if link["t"] in LISTEN_ORDER else other).append(link)

    seen, kept = set(), []
    for link in sorted(listen, key=lambda l: LISTEN_ORDER.index(l["t"])):
        if link["t"] not in seen:
            seen.add(link["t"])
            kept.append(link)
    dropped = kept[MAX_LISTEN:]
    kept = kept[:MAX_LISTEN]

    record["links"] = sorted(kept + other, key=_rank)
    record["u"] = record["links"][0]["u"] if record["links"] else ""
    return dropped


def link_type(url):
    """Classify a URL by host, or None when it is not a known service."""
    host = re.sub(r"^www\.", "", (url or "").split("//", 1)[-1].split("/")[0].lower())
    for kind, domains in LINK_DOMAINS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return kind
    return None
