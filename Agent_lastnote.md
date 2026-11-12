I'll research this properly — spawning several research agents in parallel to cover Arabic nasheed, South/Southeast Asian and Turkish/Persian scenes, Western and African scenes, groups and labels, and where catalogs can be aggregated from. Meanwhile I'll set up the workspace for the database.
Good — that first wave returned a lot. Several regions came back thin or truncated (Maghreb, Sudan, Iraq, Balkans, Central Asia, Latin America), so I'm sending a second wave to fill those gaps while I start building the library structure.
That fill-in returned the Maghreb, Sudan, Iraq, Mauritania and female munshidat. Now I'll write the database itself — starting with the Arab world, then Asia, then the West/Africa, then the labels and the aggregator app.


Arab world done. Now the Asian scenes — Pakistan/India/Bangladesh, Indonesia/Malaysia, Turkey, Iran and the Kurdish/Persian edges.


Now the organizations/labels layer and the aggregation-source layer — the part that makes this an aggregator rather than just a list.


Now the build script that validates everything and generates the database files plus the self-contained web app.




Built successfully — 301 artists, 61 labels, 20 sources. Now verifying the data integrity and the generated app.
Data and app both check out: 301 records, no duplicates, valid embedded JSON, JS syntax clean. Fixing one name typo, adding the README, and setting up a headless render test.


Done. I ran seven research agents across Arabic, South/Southeast Asian, Turkish/Persian, Western, African, Maghreb/Sudan/Iraq and organisational/data-source angles, then compiled everything into a single database and a working app.

**Your library:** [nasheed-library.html](files/nasheed-library.html) — one self-contained file, works offline, opens in any browser. Search in English or Arabic script, filter by region/category/instrumentation, and one click restricts to vocal-only.

What's in it:

| | |
|---|---|
| Artists & groups | **301** (munshideen, groups, ensembles, chanters) |
| Countries / languages | 59 / 71 |
| Vocal-only or duff-only | **91** — of which 44 strictly a cappella |
| Labels, broadcasters, festivals | 61 |
| Aggregation sources with live query strings | 20 |

Because you wanted non-music first, the default sort is vocal-first and the a cappella/percussion records are marked and filterable. Coverage: Arab world 124, South Asia 44, Southeast Asia 39, Turkey & Iran 28, Africa 24, Europe 23, North America 12 — spanning everyone from Sayed Al-Naqshabandi, Taha Al-Fashni and the Aleppo madīḥ families to Raihan, Snada, Hijjaz, Junaid Jamshed, Aayat Arif, the Malayalam Mappila industry, Bengali Kalarab, Ahmet Özhan, Iranian maddāḥī, Somali and Swahili qaswida, Zain Bhikha, Omar Esa, Ilyas Mao and the Chechen scene.

The other files: [nasheed-db.json](files/nasheed-db.json) (the whole database), [nasheed_artists.csv](files/nasheed_artists.csv), [nasheed_labels_and_platforms.csv](files/nasheed_labels_and_platforms.csv), [nasheed_aggregation_sources.csv](files/nasheed_aggregation_sources.csv), and [README.md](files/README.md).

Two things I was deliberately strict about. Every record carries a confidence dot — 131 high, 115 medium, 55 low — and I did not invent album titles to fill cells; 17 records openly say no work titles were verifiable. The app's Field guide also lists the real gaps (Latin America, Central Asia, the Balkans, East Asia, Germany/Belgium) rather than pretending the map is complete. And it flags four entities that keep circulating as "nasheed labels" but aren't: Wardah is cosmetics, Logiss is rock, Nagaswara is dance, Interpal is a charity.

Checks run: build validates every field, code and duplicate (301 records, zero duplicates); the embedded JSON parses; the JavaScript passes a syntax check; and a headless DOM test confirmed all 301 cards render, the vocal-only toggle returns exactly 91, English and Arabic search both work, and all four tabs switch with no runtime errors. I did not open it in a real browser, so the visual design is unseen — tell me if anything looks off.

The obvious next step is filling the thinnest regions, since those 55 low-confidence rows are mostly leads rather than facts.

---

**Status after the gap-filling pass (2026-11-12).** The "obvious next step" in the note above is done. Six research agents covered Latin America and the Caribbean, the Caucasus and Central Asia, the Balkans, East Asia, continental Europe, and the Southeast Asian and Pacific edges. Fifty-three verified records replaced four placeholder rows (Spanish-language nasheed, Caribbean scene, Tatar and Central Asian nasheed, Bosnian scene), so every region now carries data: 343 artists, 77 countries, 98 languages, 94 vocal-only, of which 47 strictly a cappella. Confidence is now 156 high / 134 medium / 53 low. Central Asia, East Asia and Latin America are no longer gaps; the remaining absences are narrower and are listed in the README's Known gaps section and in the site's field guide.
