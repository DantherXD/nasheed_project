# The Nasheed Library

A sourced database and aggregation map of Islamic vocal music — **nasheed / anasheed (أناشيد)**, the **munshideen (منشدون)** who perform it, plus **nasyid**, **na'at**, **ilahi**, **inshād**, **qaṣīda**, **madīḥ** and **maddāḥī**.

Built to be the broadest single-file reference available, with the a cappella and percussion-only tradition foregrounded, but not exclusive of instrumented nasheed.

## What is in here

| File | What it is |
|---|---|
| `site/` | The website — a static wiki shell with sidebar navigation, search, filters and dense link lists. Published to GitHub Pages by `.github/workflows/pages.yml`. |
| `nasheed-library.html` | The original single-file app. Open it in any browser — search, filter, sort, export. Fully self-contained, works offline. |
| `nasheed-db.json` | The whole database: 301 artists, 61 labels/platforms, 20 aggregation sources, plus taxonomy. |
| `nasheed_artists.csv` | Flat artist table, Excel-ready (UTF-8 BOM). |
| `nasheed_labels_and_platforms.csv` | Labels, broadcasters, festivals, awards, distributors. |
| `nasheed_aggregation_sources.csv` | Each data source with access method, example query and licence limits. |

**Counts:** 294 artists and groups · 58 countries · 71 languages · 84 vocal-only or duff-only · 39 strictly a cappella · 61 labels and platforms · 20 aggregation sources.

By region: Arab World 120 · South Asia 42 · Southeast Asia 39 · Turkey & Iran 28 · Africa 24 · Europe 23 · North America 12 · Caucasus & Central Asia 3 · Latin America 2 · East Asia 1.

## The website

`site/` is a dependency-free static site: one HTML shell, one stylesheet, one script, and a `data.json` that is copied from `nasheed-db.json` on every deploy, so the two can never drift apart.

| Route | What it shows |
|---|---|
| `#/overview` | Counts, confidence legend, entry points |
| `#/artists` | The roster, grouped by region, with every filter |
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
  "u": "link", "cf": "high | med | low", "nt": "note"
}
```

Instrumentation codes: `acap` (a cappella), `duff` (voice + percussion only), `inst` (instrumental), `mixed`, `unk`.

Category codes: `nasheed`, `naat`, `nasyid`, `ilahi`, `inshad`, `qasida`, `madih`, `maddahi`, `children`, `adjacent`, `reciter`.

## Rebuilding

Source data lives in `data/` as three artist chunks plus organisations and sources. To regenerate everything:

```bash
python3 build.py
```

The build validates required fields, rejects duplicate names, checks every code against the taxonomy, and fails loudly rather than emitting a broken file.

## Method and confidence

Records were compiled from label and institutional pages, Wikipedia and Wikidata, MusicBrainz, Last.fm, Discogs, archive.org, Smithsonian Folkways, HMML, and regional Arabic, Malay, Turkish, Urdu and Bengali press.

Every record carries a confidence value:

- **high (127)** — artist and at least some works confirmed against a label, institutional or reliable reference.
- **medium (112)** — artist confirmed, discography or dates partial.
- **low (55)** — name attested but details unverified. Research leads, not facts.

No album title, date or label was invented to fill a cell. Where a field could not be verified it says so or is left blank. 17 records have no confirmed work titles and 7 have no link, deliberately.

## Rules this library follows

1. **Metadata and links only.** No audio is hosted. Spotify's terms forbid building a database from its content; YouTube forbids storing audiovisual data and caps metadata retention at 30 days; Deezer forbids audio storage. The compliant pattern is index → link out → embed with the platform's own player.
2. **A Creative Commons tag on a re-upload is not a licence.** It must come from the rights holder. Only CC0, CC BY and CC BY-SA are safe for broad reuse; NC blocks ad-supported use and ND blocks syncing to video.
3. **Extremist content is excluded.** A meaningful share of what is tagged "nasheed" on open archives is ISIS or Taliban propaganda. That needs a denylist and takedown process from day one.
4. **Genres are not merged.** Qawwali, Sufi art song, children's song and political chant are tagged `adjacent` rather than folded into "nasheed".

## Known gaps

Latin America and the Caribbean (Spanish-language nasheed exists but almost no named recording artists are catalogued); Central Asia (Uzbek, Kazakh, Kyrgyz, Tajik — lives on Telegram, not indexed catalogues); the Balkans (needs Bosnian, Albanian and Kosovar research); East Asia (Japan, Korea, Philippines, Thailand, Champa); Germany, Belgium, Spain, Italy beyond concert markets; Ireland; Brunei and Patani. These are documented absences in the field guide, not oversights.

## Extending it

The pipeline that produces the largest library, in order of yield:

1. **Seed** — Last.fm `tag.gettopartists` for `nasheed`, `anasheed`, `nasyid`, `ilahi`, `islamic`, then `artist.gettoptags` to reject false positives.
2. **Resolve** — MusicBrainz artist search to MBIDs, then browse releases and release groups.
3. **Enrich** — Discogs `database/search` and `releases/{id}` for label, catalogue number, country and year.
4. **Identity graph** — Wikidata `P136 = Q783874` plus Wikipedia category walks for Arabic, Malay, Turkish and Urdu aliases.
5. **Audio discovery** — YouTube channels via the uploads playlist (1 quota unit) rather than repeated searches; store IDs and a last-verified date.
6. **Openly licensed audio** — archive.org with a `licenseurl` filter and per-item metadata; accept only CC0, CC BY and CC BY-SA with attribution stored.
7. **QA** — dedupe on ISRC → MBID → normalised artist, title and duration; then apply this library's own taxonomy, because upstream vocabularies are inconsistent.
