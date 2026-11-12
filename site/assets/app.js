/* ============================================================
   The Nasheed Library — client
   Loads data.json (a copy of nasheed-db.json), renders the wiki
   shell, and keeps filters shareable through the URL hash.
   ============================================================ */
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

/* fold Arabic diacritics, hamza forms and apostrophe variants so Latin
   and Arabic-script queries both hit the same records */
const norm = v => String(v == null ? '' : v)
  .toLowerCase()
  .replace(/[\u064B-\u0652\u0670\u0640]/g, '')
  .replace(/[إأآ]/g, 'ا')
  .replace(/[ىی]/g, 'ي')
  .replace(/ة/g, 'ه')
  .replace(/[ʾʿ'’‘`]/g, '');

const ROUTES = ['overview', 'artists', 'labels', 'sources', 'references', 'guide', 'artist'];
const VOCAL_ORDER = { acap: 0, duff: 1, mixed: 2, inst: 3, unk: 4 };
const CONF_ORDER = { high: 0, med: 1, low: 2 };

const state = {
  route: 'overview',
  q: '', region: '', cat: '', vocal: '', type: '', conf: '',
  sort: 'vocal', vocalOnly: false, artistId: '', check: '', need: ''
};

let DATA = null;
let A = [], O = [], S = [];

/* ---------------------------------------------------------- theme */
(function theme() {
  const saved = localStorage.getItem('nl-theme');
  document.documentElement.dataset.theme = saved === 'light' ? 'light' : 'dark';
  $('#themeBtn').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('nl-theme', next);
  });
})();

/* ---------------------------------------------------------- reviewed
   A review state that lives only in this browser: no server, no cookies,
   nothing sent anywhere. Shape: {v:1, ids:{artistId: ISO timestamp}}.
   Timestamps are not shown yet, but they make "recently reviewed" possible
   later and cost nothing now. */
const CHECK_KEY = 'nl-checked';
let CHECKED = new Map();

function loadChecked() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHECK_KEY) || '{}');
    const ids = parsed && parsed.ids && typeof parsed.ids === 'object' ? parsed.ids : {};
    CHECKED = new Map(Object.entries(ids).filter(([, at]) => typeof at === 'string'));
  } catch (err) {
    CHECKED = new Map();          // corrupt or hand-edited: start clean, never throw
  }
}

function saveChecked() {
  try {
    localStorage.setItem(CHECK_KEY, JSON.stringify({ v: 1, ids: Object.fromEntries(CHECKED) }));
  } catch (err) {
    /* private mode or a full quota — the tick still works for this page view */
  }
}

const isChecked = a => CHECKED.has(a.id);
const checkedCount = () => A.filter(isChecked).length;

function setChecked(id, on) {
  if (!id) return;
  on ? CHECKED.set(id, new Date().toISOString()) : CHECKED.delete(id);
  saveChecked();
  render();
}

/* records get renamed or dropped between data updates; forget ids that are gone */
function pruneChecked() {
  const known = new Set(A.map(a => a.id));
  let changed = false;
  for (const id of [...CHECKED.keys()]) if (!known.has(id)) { CHECKED.delete(id); changed = true; }
  if (changed) saveChecked();
}

/* ---------------------------------------------------------- routing */
function readHash() {
  const raw = (location.hash || '').replace(/^#\/?/, '');
  const [rawPath, qs] = raw.split('?');
  const p = new URLSearchParams(qs || '');
  let path = rawPath;
  state.artistId = '';
  if (rawPath.startsWith('artist/')) {
    path = 'artist';
    state.artistId = decodeURIComponent(rawPath.slice(7));
  }
  state.route = ROUTES.includes(path) ? path : 'overview';
  state.q = p.get('q') || '';
  state.region = p.get('region') || '';
  state.cat = p.get('cat') || '';
  state.vocal = p.get('vocal') || '';
  state.type = p.get('type') || '';
  state.conf = p.get('conf') || '';
  state.sort = p.get('sort') || 'vocal';
  state.vocalOnly = p.get('vocalOnly') === '1';
  state.check = ['todo', 'done'].includes(p.get('check')) ? p.get('check') : '';
  state.need = ['link', 'country', 'inst'].includes(p.get('need')) ? p.get('need') : '';
}

function writeHash() {
  const p = new URLSearchParams();
  if (state.q) p.set('q', state.q);
  if (state.region) p.set('region', state.region);
  if (state.cat) p.set('cat', state.cat);
  if (state.vocal) p.set('vocal', state.vocal);
  if (state.type) p.set('type', state.type);
  if (state.conf) p.set('conf', state.conf);
  if (state.sort && state.sort !== 'vocal') p.set('sort', state.sort);
  if (state.vocalOnly) p.set('vocalOnly', '1');
  if (state.check) p.set('check', state.check);
  if (state.need) p.set('need', state.need);
  const qs = p.toString();
  const next = '#/' + state.route + (qs ? '?' + qs : '');
  if (location.hash !== next) history.replaceState(null, '', next);
}

function syncControls() {
  $('#q').value = state.q;
  $('#vocalToggle').setAttribute('aria-pressed', String(state.vocalOnly));
  $('#fRegion').value = state.region;
  $('#fCat').value = state.cat;
  $('#fVocal').value = state.vocal;
  $('#fType').value = state.type;
  $('#fConf').value = state.conf;
  $('#sort').value = state.sort;
  $$('[data-checkview]').forEach(b =>
    b.setAttribute('aria-pressed', String((b.dataset.checkview || '') === state.check)));
}

function showPage() {
  $$('.page').forEach(s => s.classList.toggle('active', s.id === 'page-' + state.route));
  $$('.nav a[data-nav]').forEach(a => {
    const on = a.dataset.nav === state.route;
    on ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
  });
  $$('.nav-sub a').forEach(a => a.removeAttribute('aria-current'));
  if (state.route !== 'artist') {
    const h1 = $('#page-' + state.route + ' h1');
    document.title = state.route === 'overview'
      ? 'The Nasheed Library'
      : (h1 ? h1.textContent.trim() : 'The Nasheed Library') + ' — The Nasheed Library';
  }
}

function render() {
  if (state.route === 'artists') renderArtists();
  if (state.route === 'labels') renderOrgs();
  if (state.route === 'sources') renderSources();
  if (state.route === 'references') renderReferences();
  if (state.route === 'artist') renderArtistPage();
  showPage();
  syncControls();
}

function go(route) {
  state.route = route;
  writeHash();
  render();
  window.scrollTo({ top: 0, behavior: 'instant' in document.documentElement.style ? 'instant' : 'auto' });
  $('#sidebar').classList.remove('open');
  $('#menuBtn').setAttribute('aria-expanded', 'false');
}

/* ---------------------------------------------------------- facets */
function buildFacets() {
  const regions = [...new Set(A.map(a => a.r))]
    .sort((x, y) => DATA.taxonomy.regions.indexOf(x) - DATA.taxonomy.regions.indexOf(y));
  const cats = [...new Set(A.map(a => a.k))]
    .sort((x, y) => (DATA.taxonomy.categories[x] || x).localeCompare(DATA.taxonomy.categories[y] || y));

  const fill = (sel, label, items) => {
    const el = $(sel);
    el.innerHTML = `<option value="">${label}</option>` +
      items.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
  };

  fill('#fRegion', 'All regions', regions.map(r => [r, `${r} (${A.filter(a => a.r === r).length})`]));
  fill('#fCat', 'All categories', cats.map(c => [c, `${DATA.taxonomy.categories[c] || c} (${A.filter(a => a.k === c).length})`]));
  fill('#fVocal', 'Any instrumentation', [
    ['acap', `A cappella (${A.filter(a => a.v === 'acap').length})`],
    ['duff', `Voice + percussion only (${A.filter(a => a.v === 'duff').length})`],
    ['inst', `Instrumental (${A.filter(a => a.v === 'inst').length})`],
    ['mixed', `Mixed / varies (${A.filter(a => a.v === 'mixed').length})`],
    ['unk', `Unknown (${A.filter(a => a.v === 'unk').length})`]
  ]);
  fill('#fType', 'Solo & group', [['Solo', 'Solo'], ['Group', 'Group'], ['Various', 'Various'], ['Festival', 'Festival'], ['Label', 'Label']]);
  fill('#fConf', 'Any confidence', [['high', 'High only'], ['med', 'Medium'], ['low', 'Low (leads)']]);
  $('#sort').innerHTML = [
    ['vocal', 'Sort: vocal-first'],
    ['name', 'Sort: name A–Z'],
    ['country', 'Sort: country A–Z'],
    ['listen', 'Sort: listening links'],
    ['conf', 'Sort: confidence']
  ].map(([v, t]) => `<option value="${v}">${t}</option>`).join('');

  const counts = Object.fromEntries(regions.map(r => [r, A.filter(a => a.r === r).length]));
  $('#regionNav').innerHTML = regions
    .map(r => `<a href="#/artists?region=${encodeURIComponent(r)}">${esc(r)}<span class="n" style="margin-left:auto">${counts[r]}</span></a>`)
    .join('');
}

/* ---------------------------------------------------------- stats */
function renderStats() {
  const c = DATA.meta.counts;
  const playable = A.filter(listenCount).length;
  const need = {
    link: A.length - playable,
    country: A.filter(a => !a.c).length,
    inst: A.filter(a => a.v === 'unk').length
  };

  $('#stats').innerHTML = [
    [c.artists, 'artists & groups'],
    [c.vocalOnly, 'vocal-only or duff-only'],
    [A.filter(a => a.v === 'acap').length, 'strictly a cappella'],
    [c.countries, 'countries & scenes'],
    [playable, 'with a playable link'],
    [need.link, 'awaiting a link'],
    [c.labels, 'labels & platforms'],
    [c.sources, 'aggregation sources']
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');

  $$('[data-count]').forEach(el => { el.textContent = c[el.dataset.count]; });
  $$('[data-need]').forEach(el => { el.textContent = need[el.dataset.need]; });
  $('#refCount').textContent = A.filter(a => (a.refs || []).length).length;
  $('#hubArtists').textContent = `${c.artists} records · ${c.countries} countries →`;

  /* the copy has to keep up with the data it describes */
  const badge = $('#heroBadge');
  if (badge) badge.textContent = 'updated ' + DATA.meta.built;
  const sub = $('#heroSub');
  if (sub) sub.textContent = `${A.length} records, ${playable} with a playable link and ` +
    `${need.link} still awaiting one — sourced, not scraped.`;
  const md = document.querySelector('meta[name="description"]');
  if (md) md.content = `An open, sourced database of Islamic vocal music: ${A.length} artists and ` +
    `groups across ${c.countries} countries, ${playable} with a playable link, and a citation trail for every record.`;
  $('#footStats').textContent =
    `${c.artists} artists · ${c.labels} labels · ${c.sources} sources · built ${DATA.meta.built}`;
}

/* ---------------------------------------------------------- artists */
function filteredArtists() {
  const q = norm(state.q);
  return A.filter(a => {
    if (state.region && a.r !== state.region) return false;
    if (state.cat && a.k !== state.cat) return false;
    if (state.vocal && a.v !== state.vocal) return false;
    if (state.type && a.t !== state.type) return false;
    if (state.conf && a.cf !== state.conf) return false;
    if (state.vocalOnly && a.v !== 'acap' && a.v !== 'duff') return false;
    if (state.check === 'todo' && isChecked(a)) return false;
    if (state.check === 'done' && !isChecked(a)) return false;
    if (state.need === 'link' && listenCount(a)) return false;
    if (state.need === 'country' && a.c) return false;
    if (state.need === 'inst' && a.v !== 'unk') return false;
    if (q && !norm([a.n, a.ar, a.c, a.r, a.l, a.e, a.w, a.nt, a.catLabel, a.vocalLabel].join(' ')).includes(q)) return false;
    return true;
  });
}

const RTL_SCRIPT = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F]/;
const native = s => `<span class="e-native"${RTL_SCRIPT.test(s) ? ' lang="ar" dir="rtl"' : ''}>${esc(s)}</span>`;

function artistEntry(a) {
  const name = `<a class="e-name" href="#/artist/${encodeURIComponent(a.id)}">${esc(a.n)}</a>`;
  const desc = (a.w && a.w !== '—')
    ? `<p class="e-desc"><b>${esc(a.w)}</b>${a.nt ? ' — ' + esc(a.nt) : ''}</p>`
    : (a.nt ? `<p class="e-desc">${esc(a.nt)}</p>` : '');
  const vocalPill = `<span class="pill ${esc(a.v === 'acap' ? 'acap' : a.v === 'duff' ? 'duff' : a.v === 'inst' ? 'inst' : '')}">${esc(a.vocalLabel)}</span>`;
  const catPill = `<span class="pill ${a.k === 'reciter' ? 'reciter' : ''}">${esc(a.catLabel)}</span>`;
  const bits = [a.l, a.e, a.t].filter(Boolean).join(' · ');
  const on = isChecked(a);
  const tick = `<button class="tick${on ? ' on' : ''}" type="button" data-check="${esc(a.id)}" aria-pressed="${on}" aria-label="${on ? 'Unmark' : 'Mark'} ${esc(a.n)} as reviewed" title="${on ? 'Reviewed — click to unmark' : 'Mark as reviewed'}">✓</button>`;
  return `<li class="entry v-${esc(a.v)}${on ? ' checked' : ''}">
  <div class="e-head">
    ${tick}
    ${name}
    ${a.ar ? native(a.ar) : ''}
    <span class="conf ${esc(a.cf)}" title="Confidence: ${esc(a.cf)}"></span>
  </div>
  ${desc}
  <div class="e-meta">
    ${a.c ? `<span class="pill">${esc(a.c)}</span>` : ''}
    ${vocalPill}
    ${catPill}
    <span class="e-dim">${esc(bits)}</span>
    <span class="e-links">${listenChips(a)}</span>
    <a class="e-src" href="#/artist/${encodeURIComponent(a.id)}">all links →</a>
  </div>
</li>`;
}

const listenCount = a => (a.links || []).filter(l => LISTEN_TYPES.includes(l.t)).length;

function sortArtists(rows) {
  const cmp = {
    vocal: (x, y) => (VOCAL_ORDER[x.v] - VOCAL_ORDER[y.v]) || x.n.localeCompare(y.n),
    name: (x, y) => x.n.localeCompare(y.n),
    country: (x, y) => (x.c || '').localeCompare(y.c || '') || x.n.localeCompare(y.n),
    listen: (x, y) => (listenCount(y) - listenCount(x)) || x.n.localeCompare(y.n),
    conf: (x, y) => (CONF_ORDER[x.cf] - CONF_ORDER[y.cf]) || x.n.localeCompare(y.n)
  }[state.sort] || ((x, y) => x.n.localeCompare(y.n));
  return rows.slice().sort(cmp);
}

function renderArtists() {
  const rows = sortArtists(filteredArtists());
  const vocal = rows.filter(a => a.v === 'acap' || a.v === 'duff').length;
  const done = checkedCount();
  const needLabel = { link: 'without a playable link', country: 'with no country recorded',
    inst: 'with unresolved instrumentation' }[state.need] || '';
  $('#count').innerHTML =
    `Showing <b>${rows.length}</b> of ${A.length} records${needLabel ? ' ' + needLabel : ''} · ` +
    `<b>${vocal}</b> vocal-only · ` +
    `<b>${done}</b> reviewed${done ? ' (saved in this browser only)' : ''} · click a name to open its source`;

  if (!rows.length) {
    const allDone = state.check === 'todo' && done > 0;
    $('#artistList').innerHTML = allDone
      ? `<div class="empty">Every record matching these filters is reviewed.<br>` +
        `<button class="btn" id="resetEmpty" type="button">Clear filters</button> ` +
        `<button class="link-btn" id="showChecked" type="button">See the reviewed ones</button></div>`
      : `<div class="empty">No records match those filters.<br><button class="btn" id="resetEmpty" type="button">Reset filters</button></div>`;
    $('#resetEmpty').addEventListener('click', clearFilters);
    const see = $('#showChecked');
    if (see) see.addEventListener('click', () => { state.check = 'done'; writeHash(); render(); });
    return;
  }

  const groups = [];
  if (state.region) {
    groups.push([state.region, rows]);
  } else {
    const order = DATA.taxonomy.regions;
    const map = new Map();
    rows.forEach(a => { if (!map.has(a.r)) map.set(a.r, []); map.get(a.r).push(a); });
    [...map.keys()]
      .sort((x, y) => order.indexOf(x) - order.indexOf(y))
      .forEach(r => groups.push([r, map.get(r)]));
  }

  $('#artistList').innerHTML = groups.map(([label, items]) => {
    const slug = 'r-' + label.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    return `<h2 class="group" id="${slug}">${esc(label)}<span class="n">${items.length}</span></h2>
<ul class="entries">${items.map(artistEntry).join('')}</ul>`;
  }).join('');
}

function clearFilters() {
  state.q = ''; state.region = ''; state.cat = ''; state.vocal = '';
  state.type = ''; state.conf = ''; state.vocalOnly = false; state.sort = 'vocal';
  state.check = ''; state.need = '';
  writeHash();
  render();
}

/* ---------------------------------------------------------- labels */
function renderOrgs() {
  const q = norm(state.q);
  const rows = O
    .filter(o => !q || norm([o.n, o.c, o.t, o.s, o.a, o.nt].join(' ')).includes(q))
    .filter(o => !state.conf || o.cf === state.conf)
    .slice()
    .sort((x, y) => (CONF_ORDER[x.cf] - CONF_ORDER[y.cf]) || x.n.localeCompare(y.n));

  $('#orgCount').innerHTML = `Showing <b>${rows.length}</b> of ${O.length} labels, broadcasters, festivals and platforms.`;
  $('#orgList').innerHTML = rows.length ? `<ul class="entries">${rows.map(o => {
    const name = o.u
      ? `<a class="e-name" href="${esc(o.u)}" target="_blank" rel="noopener">${esc(o.n)}</a>`
      : `<span class="e-name">${esc(o.n)}</span>`;
    return `<li class="entry">
  <div class="e-head">
    ${name}
    <span class="pill">${esc(o.t)}</span>
    <span class="conf ${esc(o.cf)}" title="Confidence: ${esc(o.cf)}"></span>
  </div>
  <div class="e-meta"><span class="e-dim">${esc(o.c)}${o.y && o.y !== '—' ? ' · from ' + esc(o.y) : ''}</span></div>
  ${o.s ? `<p class="e-desc"><b>Scenes</b> ${esc(o.s)}</p>` : ''}
  ${o.a ? `<p class="e-desc"><b>Roster</b> ${esc(o.a)}</p>` : ''}
  ${o.nt ? `<p class="e-desc">${esc(o.nt)}</p>` : ''}
  ${o.u ? `<div class="e-meta"><a class="e-src" href="${esc(o.u)}" target="_blank" rel="noopener">open site ↗</a></div>` : ''}
</li>`;
  }).join('')}</ul>` : `<div class="empty">Nothing matches that search.</div>`;
}

/* ---------------------------------------------------------- sources */
function renderSources() {
  const q = norm(state.q);
  const rows = S.filter(s => !q || norm([s.n, s.w, s.acc, s.q, s.lim, s.legal, s.nt].join(' ')).includes(q));

  $('#srcCount').innerHTML = `Showing <b>${rows.length}</b> of ${S.length} data sources, with copy-ready queries and the licence limits that govern them.`;
  $('#srcList').innerHTML = rows.length ? `<ul class="entries">${rows.map((s, i) => `
<li class="entry">
  <div class="e-head">
    <span class="e-name">${esc(s.n)}</span>
    <span class="pill">${esc(s.acc.split(/[,;]/)[0].slice(0, 26))}</span>
    <span class="conf ${esc(s.cf)}" title="Confidence: ${esc(s.cf)}"></span>
  </div>
  <p class="e-desc"><b>What it has</b> ${esc(s.w)}</p>
  <dl class="kv">
    <dt>Limits</dt><dd>${esc(s.lim)}</dd>
    <dt>Legal</dt><dd>${esc(s.legal)}</dd>
  </dl>
  ${s.q ? `<pre class="q" id="q-${i}">${esc(s.q)}</pre><button class="copy" type="button" data-copy="q-${i}">Copy query</button>` : ''}
  ${s.nt ? `<p class="e-desc" style="margin-top:8px">${esc(s.nt)}</p>` : ''}
</li>`).join('')}</ul>` : `<div class="empty">Nothing matches that search.</div>`;
}

/* ---------------------------------------------------------- links */
const LINK_LABEL = {
  apple: 'Apple Music', spotify: 'Spotify', deezer: 'Deezer', youtube: 'YouTube',
  amazon: 'Amazon Music', catalogue: 'Catalogue', official: 'Official site', linktree: 'All links',
  wiki: 'Wikipedia', press: 'Press', paper: 'Study', archive: 'Archive'
};
const LISTEN_TYPES = ['youtube', 'apple', 'spotify', 'deezer', 'amazon'];

const chips = (list, cls) => (list || []).map(l =>
  `<a class="chip ${cls} ${esc(l.t)}" href="${esc(l.u)}" target="_blank" rel="noopener">${esc(LINK_LABEL[l.t] || l.t)} ↗</a>`
).join('');

function listenChips(a) {
  const l = (a.links || []).filter(x => LISTEN_TYPES.includes(x.t));
  return l.length ? chips(l, 'listen') : '<span class="chip muted">no listening link</span>';
}

/* not artist pages, so they are offered as searches and labelled as such */
function searchChips(a) {
  const q = encodeURIComponent(a.n);
  const have = new Set((a.links || []).map(l => l.t));
  return [
    ['spotify', `https://open.spotify.com/search/${q}`],
    ['apple', `https://music.apple.com/search?term=${q}`],
    ['deezer', `https://www.deezer.com/search/${q}`],
    ['youtube', `https://www.youtube.com/results?search_query=${q}`]
  ].filter(([t]) => !have.has(t))
   .map(([t, u]) => `<a class="chip alt ${t}" href="${esc(u)}" target="_blank" rel="noopener">${esc(LINK_LABEL[t])} search ↗</a>`)
   .join('');
}

/* ---------------------------------------------------------- artist hub */
function renderArtistPage() {
  const a = A.find(x => x.id === state.artistId);
  const el = $('#artistPage');
  if (!a) {
    el.innerHTML = `<div class="empty">No record with that id.<br><a class="btn" href="#/artists">Back to the roster</a></div>`;
    return;
  }
  const links = a.links || [];
  const listen = links.filter(x => LISTEN_TYPES.includes(x.t));
  const other = links.filter(x => !LISTEN_TYPES.includes(x.t));
  const refs = a.refs || [];
  const rel = (a.rel || []).map(id => A.find(x => x.id === id)).filter(Boolean);
  const dir = a.ar && RTL_SCRIPT.test(a.ar) ? ' lang="ar" dir="rtl"' : '';

  el.innerHTML = `
  <a class="crumb" href="#/artists">← Artists &amp; groups</a>
  <div class="artist-head">
    <div>
      <h1>${esc(a.n)}</h1>
      ${a.ar ? `<div class="artist-native"${dir}>${esc(a.ar)}</div>` : ''}
    </div>
    <span class="conf ${esc(a.cf)}" title="Confidence: ${esc(a.cf)}"></span>
  </div>
  <div class="e-meta artist-tags">
    ${a.c ? `<span class="pill">${esc(a.c)}</span>` : ''}
    <span class="pill ${a.v === 'acap' ? 'acap' : a.v === 'duff' ? 'duff' : a.v === 'inst' ? 'inst' : ''}">${esc(a.vocalLabel)}</span>
    <span class="pill ${a.k === 'reciter' ? 'reciter' : ''}">${esc(a.catLabel)}</span>
    <span class="pill">${esc(a.t)}</span>
    ${a.l ? `<span class="pill">${esc(a.l)}</span>` : ''}
    ${a.e ? `<span class="pill">${esc(a.e)}</span>` : ''}
  </div>

  ${a.w ? `<h2 class="group">Key works</h2><p class="artist-works">${esc(a.w)}</p>` : ''}
  ${a.nt ? `<p class="artist-note">${esc(a.nt)}</p>` : ''}

  <h2 class="group">Listen<span class="n">${listen.length}</span></h2>
  <div class="linkrow">${listen.length ? chips(listen, 'listen') : '<span class="chip muted">No verified listening page yet</span>'}</div>
  <div class="linkrow">${searchChips(a)}</div>

  ${other.length ? `<h2 class="group">Label, catalogue &amp; official</h2>
  <div class="linkrow">${chips(other, 'other')}</div>` : ''}

  ${refs.length ? `<h2 class="group">References<span class="n">${refs.length}</span></h2>
  <p class="refnote">Documentation used to verify this record — a paper, a news piece or an encyclopaedia entry, not somewhere to hear the music.</p>
  <div class="linkrow">${chips(refs, 'ref')}</div>` : ''}

  ${rel.length ? `<h2 class="group">Look next<span class="n">${rel.length}</span></h2>
  <p class="refnote">Chosen for a shared country, category or instrumentation — a path onward, not a popularity chart.</p>
  <ul class="rel-list">${rel.map(r => `<li><a class="rel-card" href="#/artist/${encodeURIComponent(r.id)}">
    <span class="rel-name">${esc(r.n)}</span>
    <span class="rel-meta">${esc([r.c || 'unresolved', r.catLabel, r.vocalLabel].filter(Boolean).join(' · '))}</span>
  </a></li>`).join('')}</ul>` : ''}

  <div class="artist-foot">
    <button class="btn${isChecked(a) ? ' primary' : ''}" id="checkArtist" type="button" aria-pressed="${isChecked(a)}">${isChecked(a) ? '✓ Reviewed — undo' : '✓ Mark as reviewed'}</button>
    <button class="btn" id="copyPermalink" type="button">Copy link to this page</button>
    <span class="e-dim">${a.r ? esc(a.r) + ' · ' : 'Country and region unresolved · '}confidence ${esc(a.cf)}</span>
  </div>`;

  document.title = a.n + ' — The Nasheed Library';
  $('#copyPermalink').addEventListener('click', e => {
    const btn = e.currentTarget;
    const done = () => { const t = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = t; }, 1200); };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, done); else done();
  });
  $('#checkArtist').addEventListener('click', () => setChecked(a.id, !isChecked(a)));
}

/* ---------------------------------------------------------- references */
function renderReferences() {
  const documented = A.filter(a => (a.refs || []).length);
  const only = documented.filter(a => !(a.links || []).length);
  const withLinks = documented.filter(a => (a.links || []).length);
  $('#refPageCount').innerHTML =
    `<b>${documented.length}</b> records cite outside documentation · <b>${only.length}</b> of them have no listening or catalogue link at all, and are listed first.`;

  const row = a => `<li class="entry">
  <div class="e-head">
    <a class="e-name" href="#/artist/${encodeURIComponent(a.id)}">${esc(a.n)}</a>
    ${(a.links || []).length ? '' : '<span class="pill warn">references only</span>'}
    <span class="conf ${esc(a.cf)}"></span>
  </div>
  <div class="e-meta">
    ${a.c ? `<span class="pill">${esc(a.c)}</span>` : ''}
    <span class="e-dim">${esc(a.catLabel)}${a.e ? ' · ' + esc(a.e) : ''}</span>
  </div>
  <div class="linkrow">${chips(a.refs, 'ref')}</div>
</li>`;

  $('#refList').innerHTML =
    `<h2 class="group">References only<span class="n">${only.length}</span></h2>` +
    `<ul class="entries">${only.map(row).join('')}</ul>` +
    `<h2 class="group">Also documented, with links<span class="n">${withLinks.length}</span></h2>` +
    `<ul class="entries">${withLinks.map(row).join('')}</ul>`;
}

/* ---------------------------------------------------------- toc */
function buildToc() {
  const heads = $$('#guideProse h2');
  $('#toc').innerHTML = '<div class="nav-title">On this page</div>' +
    heads.map(h => `<a href="#${h.id}" data-toc="${h.id}">${esc(h.textContent)}</a>`).join('');

  if (!('IntersectionObserver' in window)) return;
  const links = new Map($$('#toc a').map(a => [a.dataset.toc, a]));
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      links.forEach(a => a.classList.remove('active'));
      const link = links.get(e.target.id);
      if (link) link.classList.add('active');
    });
  }, { rootMargin: '-96px 0px -70% 0px' });
  heads.forEach(h => io.observe(h));
  $('#toc a').classList.add('active');
}

/* ---------------------------------------------------------- wiring */
$('#q').addEventListener('input', e => {
  state.q = e.target.value.trim();
  const wasSearchPage = state.route === 'artists' || state.route === 'labels' || state.route === 'sources';
  if (!wasSearchPage && state.q) state.route = 'artists';
  writeHash();
  render();
});

$('#vocalToggle').addEventListener('click', () => {
  state.vocalOnly = !state.vocalOnly;
  writeHash();
  render();
});

[['#fRegion', 'region'], ['#fCat', 'cat'], ['#fVocal', 'vocal'],
 ['#fType', 'type'], ['#fConf', 'conf'], ['#sort', 'sort']].forEach(([sel, key]) => {
  $(sel).addEventListener('change', e => {
    state[key] = e.target.value;
    writeHash();
    render();
  });
});

$$('[data-checkview]').forEach(btn => btn.addEventListener('click', () => {
  state.check = btn.dataset.checkview || '';
  writeHash();
  render();
}));

$('#clearAll').addEventListener('click', clearFilters);

/* the checklist is local, so it can be backed up and moved between browsers */
$('#exportChecked').addEventListener('click', () => {
  const payload = { v: 1, exported: new Date().toISOString(), ids: Object.fromEntries(CHECKED) };
  const blob = new Blob([JSON.stringify(payload, null, 1) + '\n'], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'nasheed-checked.json'; a.click();
  URL.revokeObjectURL(url);
});

$('#importChecked').addEventListener('click', () => $('#importFile').click());

$('#importFile').addEventListener('change', e => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result));
      const ids = parsed && parsed.ids ? parsed.ids : parsed;
      if (!ids || typeof ids !== 'object') throw new Error('not a checklist');
      Object.entries(ids).forEach(([id, at]) => {
        if (typeof id === 'string' && id) CHECKED.set(id, typeof at === 'string' ? at : new Date().toISOString());
      });
      saveChecked();
      pruneChecked();
      render();
    } catch (err) {
      alert('That file is not a checklist export.');
    }
    e.target.value = '';
  };
  reader.readAsText(file);
});

/* another tab edited the checklist */
window.addEventListener('storage', e => {
  if (e.key !== CHECK_KEY) return;
  loadChecked();
  pruneChecked();
  render();
});

$('#csv').addEventListener('click', () => {
  const cols = ['name', 'name_native', 'country', 'region', 'language', 'era', 'solo_group',
    'category', 'instrumentation', 'key_works', 'link', 'confidence', 'note', 'reviewed'];
  const rows = [cols.join(',')].concat(filteredArtists().map(a => [
    a.n, a.ar, a.c, a.r, a.l, a.e, a.t, a.catLabel, a.vocalLabel, a.w, a.u, a.cf, a.nt,
    isChecked(a) ? 'yes' : 'no'
  ].map(v => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`).join(',')));
  const blob = new Blob(['\ufeff' + rows.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'nasheed_artists.csv'; a.click();
  URL.revokeObjectURL(url);
});

document.addEventListener('click', e => {
  const tick = e.target.closest('[data-check]');
  if (tick) {
    e.preventDefault();
    setChecked(tick.dataset.check, !CHECKED.has(tick.dataset.check));
    return;
  }
  const btn = e.target.closest('[data-copy]');
  if (btn) {
    const text = document.getElementById(btn.dataset.copy).textContent;
    const done = () => { const t = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = t; }, 1200); };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, done);
    else done();
    return;
  }
  const tocLink = e.target.closest('#toc a');
  if (tocLink) {
    $$('#toc a').forEach(a => a.classList.remove('active'));
    tocLink.classList.add('active');
    return;
  }
  const navLink = e.target.closest('.nav a, .hub-card, .brand');
  if (navLink) {
    $('#sidebar').classList.remove('open');
    $('#menuBtn').setAttribute('aria-expanded', 'false');
  }
});

$('#menuBtn').addEventListener('click', () => {
  const open = $('#sidebar').classList.toggle('open');
  $('#menuBtn').setAttribute('aria-expanded', String(open));
});

document.addEventListener('keydown', e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  if (e.key === '/' && !typing) { e.preventDefault(); $('#q').focus(); $('#q').select(); }
  if (e.key === 'Escape' && document.activeElement === $('#q')) {
    $('#q').value = ''; state.q = ''; writeHash(); render(); $('#q').blur();
  }
});

window.addEventListener('hashchange', () => {
  readHash();
  if (state.route === 'guide' && !location.hash.includes('g-')) window.scrollTo({ top: 0 });
  render();
});

/* ---------------------------------------------------------- boot */
fetch('data.json', { cache: 'no-cache' })
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(db => {
    DATA = db;
    A = db.artists; O = db.organizations; S = db.sources;
    loadChecked();
    pruneChecked();
    buildFacets();
    renderStats();
    buildToc();
    readHash();
    render();
  })
  .catch(err => {
    $('#main').innerHTML = `<div class="empty">
      <p><b>Could not load data.json</b> — ${esc(err.message)}</p>
      <p>This page loads the database over HTTP. Serve the folder (for example
      <code>python3 -m http.server</code>) rather than opening the file directly.</p>
    </div>`;
  });
