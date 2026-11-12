#!/usr/bin/env python3
"""Build the published site from nasheed-db.json.

    python3 tools/build_site.py

Writes the payload the browser reads (with the derived `rel` and search keys),
one static page per artist so a record can be linked, cited and indexed, and a
sitemap. Run by .github/workflows/pages.yml before the artifact is uploaded, and
locally whenever the database changes.

The pages are deliberately plain: they carry the record's facts, its links and
its sources in ordinary HTML, so the page works for a crawler, a preview card or
a reader with JavaScript off. The interactive library stays where it is, and the
page links into it.
"""
import json
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_db, save_db  # noqa: E402

SITE = ROOT / "site"
ARTIST_DIR = SITE / "artist"
BASE = "https://dantherxd.github.io/nasheed_project"

LINK_LABEL = {
    "apple": "Apple Music", "spotify": "Spotify", "deezer": "Deezer",
    "youtube": "YouTube", "amazon": "Amazon Music", "catalogue": "Catalogue",
    "official": "Official site", "linktree": "All links", "wiki": "Wikipedia",
    "press": "Press", "paper": "Study", "archive": "Archive",
}
LISTEN = ("youtube", "apple", "spotify", "deezer", "amazon")

STYLE = """
:root{--bg:#08080c;--ink:#f4f2fb;--muted:#a9a4bd;--line:#26243a;--gold:#e2b866}
*{box-sizing:border-box}
body{margin:0;padding:48px 20px 80px;background:var(--bg);color:var(--ink);
  font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:72ch;margin:0 auto}
a{color:#8ec5ff}
.crumb{font-size:14px;color:var(--muted);text-decoration:none}
h1{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:18px 0 4px;letter-spacing:-.02em}
.native{font-size:20px;color:var(--muted);margin-bottom:18px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0}
.pill{border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:13px;color:var(--muted)}
h2{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  margin:30px 0 10px;border-bottom:1px solid var(--line);padding-bottom:8px}
.note{color:#d9d5ea}
.row{display:flex;flex-wrap:wrap;gap:8px}
.row a{border:1px solid var(--line);border-radius:9px;padding:7px 12px;text-decoration:none;font-size:14.5px}
.row a:hover{border-color:var(--gold)}
.dim{color:var(--muted);font-size:14px}
footer{margin-top:44px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:14px}
""".strip()


def listen_count(a):
    return sum(1 for l in a.get("links", []) if l.get("t") in LISTEN)


def describe(a):
    bits = []
    if a.get("c"):
        bits.append(a["c"])
    bits.append(a.get("catLabel") or a.get("k") or "nasheed")
    bits.append(a.get("vocalLabel") or "instrumentation unknown")
    if a.get("e"):
        bits.append(a["e"])
    head = f"{a['n']} — {' · '.join(bits)}."
    note = (a.get("nt") or "").strip()
    return (head + (" " + note if note else ""))[:300]


def chips(items):
    return "".join(
        f'<a href="{escape(x["u"], quote=True)}" rel="noopener">{escape(LINK_LABEL.get(x["t"], x["t"]))}</a>'
        for x in items if x.get("u")
    )


def page(a, names):
    listen = [l for l in a.get("links", []) if l.get("t") in LISTEN]
    other = [l for l in a.get("links", []) if l.get("t") not in LISTEN]
    refs = a.get("refs", [])
    rel = [names[i] for i in a.get("rel", []) if i in names]
    title = f"{a['n']} — The Nasheed Library"
    desc = describe(a)
    canonical = f"{BASE}/artist/{a['id']}.html"

    rel_html = ""
    if rel:
        rel_html = ('<h2>Look next</h2><div class="row">' + "".join(
            f'<a href="../artist/{escape(r["id"])}.html">{escape(r["n"])}</a>' for r in rel
        ) + "</div>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc, quote=True)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="profile">
<meta property="og:title" content="{escape(a['n'], quote=True)}">
<meta property="og:description" content="{escape(desc, quote=True)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<style>{STYLE}</style>
</head>
<body>
<main>
<a class="crumb" href="../index.html">← The Nasheed Library</a>
<h1>{escape(a['n'])}</h1>
{'<div class="native">' + escape(a['ar']) + '</div>' if a.get('ar') else ''}
<div class="tags">
{''.join(f'<span class="pill">{escape(str(v))}</span>' for v in [
    a.get('c') or 'country unresolved', a.get('catLabel'), a.get('vocalLabel'),
    a.get('t'), a.get('l'), a.get('e')] if v)}
</div>
{'<p class="note">' + escape(a.get('nt')) + '</p>' if a.get('nt') else ''}
{'<h2>Key works</h2><p>' + escape(a.get('w')) + '</p>' if a.get('w') and a.get('w') != '—' else ''}

<h2>Listen</h2>
<div class="row">{chips(listen) or '<span class="dim">No verified listening page yet.</span>'}</div>
<div class="row" style="margin-top:8px">
<a href="https://open.spotify.com/search/{escape(a['n'], quote=True)}" rel="noopener">Spotify search</a>
<a href="https://music.apple.com/search?term={escape(a['n'], quote=True)}" rel="noopener">Apple Music search</a>
<a href="https://www.youtube.com/results?search_query={escape(a['n'], quote=True)}" rel="noopener">YouTube search</a>
</div>

{'<h2>Label, catalogue &amp; official</h2><div class="row">' + chips(other) + '</div>' if other else ''}
{'<h2>References</h2><div class="row">' + chips(refs) + '</div>' if refs else ''}
{rel_html}

<h2>Open in the library</h2>
<div class="row"><a href="../index.html#/artist/{escape(a['id'])}">Full record, filters and related artists</a></div>

<footer>
<a class="crumb" href="../index.html">The Nasheed Library</a> · {len(names)} records ·
metadata and links only, no audio hosted · built {date.today().isoformat()}
</footer>
</main>
</body>
</html>
"""


def page_redirect(old_id, new_id, name):
    """A merged record's old address, pointing at the surviving one."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(name)} — The Nasheed Library</title>
<link rel="canonical" href="{BASE}/artist/{escape(new_id)}.html">
<meta http-equiv="refresh" content="0; url={escape(new_id)}.html">
<meta name="robots" content="noindex">
<style>{STYLE}</style>
</head>
<body><main>
<p class="dim">This record was merged into a single entry.</p>
<h1><a href="{escape(new_id)}.html">{escape(name)}</a></h1>
</main></body>
</html>
"""


def main():
    db = load_db()
    save_db(db)  # rewrites data.json with rel + search keys, and the CSVs
    payload = json.loads((SITE / "data.json").read_text(encoding="utf-8"))
    artists = payload["artists"]
    names = {a["id"]: {"n": a["n"], "id": a["id"]} for a in artists}
    aliases = payload.get("meta", {}).get("aliases", {})

    ARTIST_DIR.mkdir(parents=True, exist_ok=True)
    keep = set()
    for a in artists:
        path = ARTIST_DIR / f"{a['id']}.html"
        path.write_text(page(a, names), encoding="utf-8")
        keep.add(path.name)

    # a merged record keeps working for anyone holding the old address
    for old_id, new_id in aliases.items():
        if new_id not in names:
            continue
        target = page_redirect(old_id, new_id, names[new_id]["n"])
        (ARTIST_DIR / f"{old_id}.html").write_text(target, encoding="utf-8")
        keep.add(f"{old_id}.html")

    # drop pages for records that no longer exist
    removed = 0
    for stale in ARTIST_DIR.glob("*.html"):
        if stale.name not in keep:
            stale.unlink()
            removed += 1

    urls = [f"{BASE}/"] + [f"{BASE}/artist/{a['id']}.html" for a in artists]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f"<url><loc>{u}</loc></url>" for u in urls]
    sitemap.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")

    print(f"built {len(artists)} artist pages ({removed} stale removed), "
          f"sitemap with {len(urls)} urls")


if __name__ == "__main__":
    main()
