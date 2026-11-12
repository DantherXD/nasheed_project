# The Nasheed Library

A sourced database and aggregation map of Islamic vocal music — **nasheed / anasheed (أناشيد)**, the **munshideen (منشدون)** who perform it, plus **nasyid**, **na'at**, **ilahi**, **inshād**, **qaṣīda**, **madīḥ** and **maddāḥī**.

Built to be the broadest single-file reference available, with the a cappella and percussion-only tradition foregrounded, but not exclusive of instrumented nasheed.

## What is in here

| File | What it is |
|---|---|
| `nasheed-library.html` | The app. Open it in any browser — search, filter, sort, export. Fully self-contained, works offline. |
| `nasheed-db.json` | The whole database: 301 artists, 61 labels/platforms, 20 aggregation sources, plus taxonomy. |
| `nasheed_artists.csv` | Flat artist table, Excel-ready (UTF-8 BOM). |
| `nasheed_labels_and_platforms.csv` | Labels, broadcasters, festivals, awards, distributors. |
| `nasheed_aggregation_sources.csv` | Each data source with access method, example query and licence limits. |

**Counts:** 301 artists and groups · 59 countries · 71 languages · 91 vocal-only or duff-only · 44 strictly a cappella · 61 labels and platforms · 20 aggregation sources.

By region: Arab World 124 · South Asia 44 · Southeast Asia 39 · Turkey & Iran 28 · Africa 24 · Europe 23 · North America 12 · Caucasus & Central Asia 3 · Latin America 2 · East Asia 1 · Asia-Pacific 1.

## How to use the app

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

Category codes: `nasheed`, `naat`, `nasyid`, `ilahi`, `inshad`, `qasida`, `madih`, `maddahi`, `latmiyya`, `children`, `adjacent`, `reciter`.

## Rebuilding

Source data lives in `data/` as three artist chunks plus organisations and sources. To regenerate everything:

```bash
python3 build.py
```

The build validates required fields, rejects duplicate names, checks every code against the taxonomy, and fails loudly rather than emitting a broken file.

## Method and confidence

Records were compiled from label and institutional pages, Wikipedia and Wikidata, MusicBrainz, Last.fm, Discogs, archive.org, Smithsonian Folkways, HMML, and regional Arabic, Malay, Turkish, Urdu and Bengali press.

Every record carries a confidence value:

- **high (131)** — artist and at least some works confirmed against a label, institutional or reliable reference.
- **medium (115)** — artist confirmed, discography or dates partial.
- **low (55)** — name attested but details unverified. Research leads, not facts.

No album title, date or label was invented to fill a cell. Where a field could not be verified it says so or is left blank. 17 records have no confirmed work titles and 7 have no link, deliberately.

## Rules this library follows

1. **Metadata and links only.** No audio is hosted. Spotify's terms forbid building a database from its content; YouTube forbids storing audiovisual data and caps metadata retention at 30 days; Deezer forbids audio storage. The compliant pattern is index → link out → embed with the platform's own player.
2. **A Creative Commons tag on a re-upload is not a licence.** It must come from the rights holder. Only CC0, CC BY and CC BY-SA are safe for broad reuse; NC blocks ad-supported use and ND blocks syncing to video.
3. **Extremist content is excluded.** A meaningful share of what is tagged "nasheed" on open archives is ISIS or Taliban propaganda. That needs a denylist and takedown process from day one.
4. **Genres are not merged.** Shia latmiyya, qawwali, Sufi art song and political chant are tagged `latmiyya` or `adjacent` rather than folded into "nasheed".

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
