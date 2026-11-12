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

    library = (ROOT / "nasheed-library.html").read_text(encoding="utf-8")
    payload = json.dumps(db, ensure_ascii=False, separators=(",", ":"))
    library = re.sub(
        r'(<script type="application/json" id="db">)(.*?)(</script>)',
        lambda m: m.group(1) + payload + m.group(3),
        library, flags=re.S,
    )
    (ROOT / "nasheed-library.html").write_text(library, encoding="utf-8")

    (ROOT / "site" / "data.json").write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------- matching

_TRANSLIT = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "–": "-", "—": "-"})
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
    """Every comparable form of a name: whole label plus each side of a
    bilingual split, so Arabic-only and Latin-only records still meet."""
    out = set()
    for part in [name or ""] + _SEPARATOR.split(name or ""):
        part = re.sub(r"\([^)]*\)", " ", part)
        key = norm(part)
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
