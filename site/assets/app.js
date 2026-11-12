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

const ROUTES = ['overview', 'artists', 'labels', 'sources', 'guide'];
const VOCAL_ORDER = { acap: 0, duff: 1, mixed: 2, inst: 3, unk: 4 };
const CONF_ORDER = { high: 0, med: 1, low: 2 };

const state = {
  route: 'overview',
  q: '', region: '', cat: '', vocal: '', type: '', conf: '',
  sort: 'vocal', vocalOnly: false
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

/* ---------------------------------------------------------- routing */
function readHash() {
  const raw = (location.hash || '').replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  const p = new URLSearchParams(qs || '');
  state.route = ROUTES.includes(path) ? path : 'overview';
  state.q = p.get('q') || '';
  state.region = p.get('region') || '';
  state.cat = p.get('cat') || '';
  state.vocal = p.get('vocal') || '';
  state.type = p.get('type') || '';
  state.conf = p.get('conf') || '';
  state.sort = p.get('sort') || 'vocal';
  state.vocalOnly = p.get('vocalOnly') === '1';
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
}

function showPage() {
  $$('.page').forEach(s => s.classList.toggle('active', s.id === 'page-' + state.route));
  $$('.nav a[data-nav]').forEach(a => {
    const on = a.dataset.nav === state.route;
    on ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
  });
  $$('.nav-sub a').forEach(a => a.removeAttribute('aria-current'));
  document.title = state.route === 'overview'
    ? 'The Nasheed Library'
    : $('#page-' + state.route + ' h1').textContent + ' — The Nasheed Library';
}

function render() {
  showPage();
  syncControls();
  if (state.route === 'artists') renderArtists();
  if (state.route === 'labels') renderOrgs();
  if (state.route === 'sources') renderSources();
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
  $('#stats').innerHTML = [
    [c.artists, 'artists & groups'],
    [c.vocalOnly, 'vocal-only or duff-only'],
    [`${c.acappella}`, 'strictly a cappella'],
    [c.countries, 'countries & scenes'],
    [c.labels, 'labels & platforms'],
    [c.sources, 'aggregation sources']
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');

  $$('[data-count]').forEach(el => { el.textContent = c[el.dataset.count]; });
  $('#hubArtists').textContent = `${c.artists} records · ${c.countries} countries →`;
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
    if (q && !norm([a.n, a.ar, a.c, a.r, a.l, a.e, a.w, a.nt, a.catLabel, a.vocalLabel].join(' ')).includes(q)) return false;
    return true;
  });
}

const RTL_SCRIPT = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F]/;
const native = s => `<span class="e-native"${RTL_SCRIPT.test(s) ? ' lang="ar" dir="rtl"' : ''}>${esc(s)}</span>`;

function artistEntry(a) {
  const name = a.u
    ? `<a class="e-name" href="${esc(a.u)}" target="_blank" rel="noopener">${esc(a.n)}</a>`
    : `<span class="e-name">${esc(a.n)}</span>`;
  const desc = (a.w && a.w !== '—')
    ? `<p class="e-desc"><b>${esc(a.w)}</b>${a.nt ? ' — ' + esc(a.nt) : ''}</p>`
    : (a.nt ? `<p class="e-desc">${esc(a.nt)}</p>` : '');
  const vocalPill = `<span class="pill ${esc(a.v === 'acap' ? 'acap' : a.v === 'duff' ? 'duff' : a.v === 'inst' ? 'inst' : '')}">${esc(a.vocalLabel)}</span>`;
  const catPill = `<span class="pill ${a.k === 'reciter' ? 'reciter' : ''}">${esc(a.catLabel)}</span>`;
  const bits = [a.l, a.e, a.t].filter(Boolean).join(' · ');
  return `<li class="entry v-${esc(a.v)}">
  <div class="e-head">
    ${name}
    ${a.ar ? native(a.ar) : ''}
    <span class="conf ${esc(a.cf)}" title="Confidence: ${esc(a.cf)}"></span>
  </div>
  ${desc}
  <div class="e-meta">
    <span class="pill">${esc(a.c)}</span>
    ${vocalPill}
    ${catPill}
    <span class="e-dim">${esc(bits)}</span>
    ${a.u ? `<a class="e-src" href="${esc(a.u)}" target="_blank" rel="noopener">source ↗</a>` : '<span class="e-src">no link</span>'}
  </div>
</li>`;
}

function sortArtists(rows) {
  const cmp = {
    vocal: (x, y) => (VOCAL_ORDER[x.v] - VOCAL_ORDER[y.v]) || x.n.localeCompare(y.n),
    name: (x, y) => x.n.localeCompare(y.n),
    country: (x, y) => x.c.localeCompare(y.c) || x.n.localeCompare(y.n),
    conf: (x, y) => (CONF_ORDER[x.cf] - CONF_ORDER[y.cf]) || x.n.localeCompare(y.n)
  }[state.sort] || ((x, y) => x.n.localeCompare(y.n));
  return rows.slice().sort(cmp);
}

function renderArtists() {
  const rows = sortArtists(filteredArtists());
  const vocal = rows.filter(a => a.v === 'acap' || a.v === 'duff').length;
  $('#count').innerHTML =
    `Showing <b>${rows.length}</b> of ${A.length} records · <b>${vocal}</b> vocal-only · click a name to open its source`;

  if (!rows.length) {
    $('#artistList').innerHTML =
      `<div class="empty">No records match those filters.<br><button class="btn" id="resetEmpty" type="button">Reset filters</button></div>`;
    $('#resetEmpty').addEventListener('click', clearFilters);
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

$('#clearAll').addEventListener('click', clearFilters);

$('#csv').addEventListener('click', () => {
  const cols = ['name', 'name_native', 'country', 'region', 'language', 'era', 'solo_group',
    'category', 'instrumentation', 'key_works', 'link', 'confidence', 'note'];
  const rows = [cols.join(',')].concat(filteredArtists().map(a => [
    a.n, a.ar, a.c, a.r, a.l, a.e, a.t, a.catLabel, a.vocalLabel, a.w, a.u, a.cf, a.nt
  ].map(v => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`).join(',')));
  const blob = new Blob(['\ufeff' + rows.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'nasheed_artists.csv'; a.click();
  URL.revokeObjectURL(url);
});

document.addEventListener('click', e => {
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
fetch('data.json')
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(db => {
    DATA = db;
    A = db.artists; O = db.organizations; S = db.sources;
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
