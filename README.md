# The Nasheed Library

A sourced database and aggregation map of Islamic vocal music — **nasheed / anasheed (أناشيد)**, the **munshideen (منشدون)** who perform it, plus **nasyid**, **na'at**, **ilahi**, **inshād**, **qaṣīda**, **madīḥ** and **maddāḥī**.

Built to be the broadest single-file reference available, with the a cappella and percussion-only tradition foregrounded, but not exclusive of instrumented nasheed.

## What is in here

| File | What it is |
|---|---|
| `site/` | The website — a static wiki shell with sidebar navigation, search, filters and dense link lists. Published to GitHub Pages by `.github/workflows/pages.yml`. |
| `nasheed-library.html` | The original single-file app. Open it in any browser — search, filter, sort, export. Fully self-contained, works offline. |
| `nasheed-db.json` | The whole database: 370 artists, 61 labels/platforms, 21 aggregation sources, plus taxonomy. |
| `nasheed_artists.csv` | Flat artist table, Excel-ready (UTF-8 BOM). |
| `nasheed_labels_and_platforms.csv` | Labels, broadcasters, festivals, awards, distributors. |
| `nasheed_aggregation_sources.csv` | Each data source with access method, example query and licence limits. |

**Counts:** 433 artists and groups · 78 countries · 71 languages · 98 vocal-only or duff-only · 51 strictly a cappella · 61 labels and platforms · 21 aggregation sources. A further 63 records carry a name and listening links but no country yet — they are marked unresolved rather than guessed.

By region: Arab World 144 · Southeast Asia 47 · Europe 44 · South Asia 42 · Turkey & Iran 28 · Africa 24 · Caucasus & Central Asia 13 · North America 12 · East Asia 7 · Latin America 7 · Asia-Pacific 2.

## The website

`site/` is a dependency-free static site: one HTML shell, one stylesheet, one script, and a `data.json` that is copied from `nasheed-db.json` on every deploy, so the two can never drift apart.

| Route | What it shows |
|---|---|
| `#/overview` | Counts, confidence legend, entry points |
| `#/artists` | The roster, grouped by region, with every filter |
| `#/artist/<id>` | One record: listen links, catalogue, and the references behind it |
| `#/references` | The research trail — papers, press and encyclopaedia entries, separate from listening |
| `#/labels` | Labels, distributors, broadcasters, festivals, awards |
| `#/sources` | Aggregation sources with copy-ready queries |
| `#/guide` | The field guide, with an on-this-page sidebar |

Filters live in the URL hash (`#/artists?region=Egypt&vocalOnly=1`), so any view can be linked or bookmarked. `/` focuses search, `Esc` clears it, and the theme toggle persists.

**Preview locally**

```bash
python3 -m http.server 3000 --directory site
```

**Publish** — push to `main`. The workflow in `.github/workflows/pages.yml` assembles the site, enables Pages on first run and deploys. Live at <https://dantherxd.github.io/nasheed_project/>.

## How to use the standalone app

Open `nasheed-library.html`. Four tabs:

- **Artists & groups** — search by name, Arabic script, country or work title. Filter by region, category, instrumentation, solo/group and confidence. "Vocal-only first" restricts to a cappella and duff-only records. Export CSV from the top bar.
- **Labels & platforms** — who releases and monetises nasheed, including four entities explicitly flagged as *not* nasheed bodies so they stop circulating in lists.
- **Aggregation sources** — exact API endpoints and query strings for MusicBrainz, Discogs, Last.fm, Deezer, Spotify, YouTube, archive.org, Wikidata and others, with the licence constraint that governs each.
- **Field guide** — terminology, the four fiqh positions on instruments, regional traditions, five historical waves, how confidence works, and the known gaps.

## Schema

Artist record:

```json
{
  "n": "name", "ar": "native script", "c": "country", "r": "region",
  "l": "language", "e": "era or active years", "t": "Solo | Group",
  "k": "category code", "v": "instrumentation code", "w": "key works",
  "u": "primary usable link", "cf": "high | med | low", "nt": "note",
  "links": [{"t": "deezer", "u": "https://www.deezer.com/artist/711"}],
  "refs":  [{"t": "paper",  "u": "https://escholarship.org/..."}]
}
```

Links are typed, so the database never confuses "where to hear this artist" with "where this artist was documented". `links` holds `apple`, `spotify`, `deezer`, `youtube`, `catalogue`, `official` and `linktree` entries, and `u` mirrors the best one. `refs` holds `wiki`, `press`, `paper` and `archive` entries — the evidence trail. Every artist also gets a page at `#/artist/<id>` that lists all of it in one place, which is the link to share.

Instrumentation codes: `acap` (a cappella), `duff` (voice + percussion only), `inst` (instrumental), `mixed`, `unk`.

Category codes: `nasheed`, `naat`, `nasyid`, `ilahi`, `inshad`, `qasida`, `madih`, `maddahi`, `children`, `adjacent`, `reciter`.

## Tools

`nasheed-db.json` is the source of truth. Everything else — the CSV exports, the single-file app, `site/data.json` — is regenerated from it by `tools/common.py`, so the copies cannot drift.

| Command | What it does |
|---|---|
| `python3 tools/crawl_portals.py --source all` | Re-crawls the Assajda index and Samaa's music-free archive, writes `data/portal_candidates.json`, and reports which portal artists the database has not got. Pages are cached, so a re-run is nearly free; `--refresh` fetches again, `--report-only` just re-reports the last crawl. |
| `python3 tools/add_records.py data/new_records_samaa.json` | Adds fully-researched records. Checks every field against the taxonomy, rejects duplicates on either name, and accepts a record without a country when the name came from a listening list (it is marked unresolved). |
| `python3 tools/fetch_apple.py --out apple_links.json` | Finds Apple Music artist pages for records that lack one via Apple's public search API. Resumable — interrupt it or get rate-limited and the same command carries on later. |
| `python3 tools/ingest_apple.py apple_links.json` | Merges those results, verifying each URL really is a `music.apple.com` artist page first. `--dry-run` reports without writing. |
| `python3 tools/match_names.py data/wanted_artists.txt` | Checks a list of names against the database — already here, partial, close, or new — and writes `data/name_matches.json`. |
| `python3 tools/fetch_links.py --out data/link_candidates.json` | Looks up artist pages for those names on Apple, Deezer, Spotify and YouTube, one request per service per name. Apple and Deezer need no key; Spotify and YouTube are used when `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` or `YOUTUBE_API_KEY` are set. Resumable. |
| `python3 tools/ingest_links.py data/link_candidates.json` | Merges those results, checking each URL's host and keeping the two-listening-link cap. `--dry-run` reports without writing. |

The Samaa crawl reads `/genre/acapella-version/` — "بدون موسيقى" — not the whole artist list, because a cappella is what this library accepts as inshad. An act whose portal page is instrumental pop never reaches the candidate file. Arabic-only names are kept as they are; a Latin name is a bonus, not a requirement.

Listening links are capped at two per artist by `tools/common.py`, chosen YouTube → Apple Music → Spotify → Deezer → Amazon Music. Two is enough to hear someone; a fifth is clutter.

## Method and confidence

Records were compiled from label and institutional pages, Wikipedia and Wikidata, MusicBrainz, Last.fm, Discogs, archive.org, Smithsonian Folkways, HMML, and regional Arabic, Malay, Turkish, Urdu and Bengali press.

Every record carries a confidence value:

- **high (169)** — artist and at least some works confirmed against a label, institutional or reliable reference.
- **medium (147)** — artist confirmed, discography or dates partial.
- **low (117)** — name attested but details unverified. Research leads, not facts.

No album title, date or label was invented to fill a cell. Where a field could not be verified it says so or is left blank. 21 records have no confirmed work titles and 6 have no link, deliberately.

## Rules this library follows

1. **Metadata and links only.** No audio is hosted. Spotify's terms forbid building a database from its content; YouTube forbids storing audiovisual data and caps metadata retention at 30 days; Deezer forbids audio storage. The compliant pattern is index → link out → embed with the platform's own player.
2. **A Creative Commons tag on a re-upload is not a licence.** It must come from the rights holder. Only CC0, CC BY and CC BY-SA are safe for broad reuse; NC blocks ad-supported use and ND blocks syncing to video.
3. **Extremist content is excluded.** A meaningful share of what is tagged "nasheed" on open archives is ISIS or Taliban propaganda. That needs a denylist and takedown process from day one.
4. **Genres are not merged.** Qawwali, Sufi art song, children's song and political chant are tagged `adjacent` rather than folded into "nasheed".
5. **Inshad only.** Portal crawls accept music-free material — the a cappella archive, not a whole catalogue — so an instrumented pop singer who happens to have recorded one nasheed does not get in.
6. **Two listening links, not six.** Cover the artist on the services people actually use and stop; `links` also carries catalogue and official pages, which are not listening links.

## Known gaps

The first pass flagged Latin America, Central Asia, the Balkans, East Asia and continental Europe as gaps. A second research wave has filled them and all eleven regions now carry records, so what remains is narrower: Spanish- and Portuguese-language nasheed in Mexico, Brazil, Chile and the Andes (mosques and daʿwa are documented, named recording artists are not); Turkmenistan, Georgia and Armenia; Albania itself, plus Bulgaria's Pomak and Turkish scenes; Belgium, Sweden, Norway, Ireland and Austria, which return touring acts and anonymous streaming profiles with no stated country; and Brunei, Fiji and Papua New Guinea, where nasyid is described but never credited. These are documented absences in the field guide, not oversights.

## Extending it

The pipeline that produces the largest library, in order of yield:

1. **Seed** — Last.fm `tag.gettopartists` for `nasheed`, `anasheed`, `nasyid`, `ilahi`, `islamic`, then `artist.gettoptags` to reject false positives.
2. **Resolve** — MusicBrainz artist search to MBIDs, then browse releases and release groups.
3. **Enrich** — Discogs `database/search` and `releases/{id}` for label, catalogue number, country and year.
4. **Identity graph** — Wikidata `P136 = Q783874` plus Wikipedia category walks for Arabic, Malay, Turkish and Urdu aliases.
5. **Audio discovery** — YouTube channels via the uploads playlist (1 quota unit) rather than repeated searches; store IDs and a last-verified date.
6. **Openly licensed audio** — archive.org with a `licenseurl` filter and per-item metadata; accept only CC0, CC BY and CC BY-SA with attribution stored.
Two portal indexes are worth seeding from before any API call: **Assajda** (36 munshids, country-tagged, one page each) and **Samaa Network** (500+ munshid pages carrying bilingual Arabic and Latin names). Neither exposes a usable API — Samaa's `download_artist` route is not published and its artist sitemap points at 404s, so crawl the paginated listing — and both are distribution platforms rather than rights holders. Index the metadata, link out, never mirror tracks. Between them they confirmed 28 existing records and surfaced five Moroccan, Egyptian and Algerian munshids this library had missed.

7. **QA** — dedupe on ISRC → MBID → normalised artist, title and duration; then apply this library's own taxonomy, because upstream vocabularies are inconsistent.
