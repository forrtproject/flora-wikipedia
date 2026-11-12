'use strict';
// Private review UI: one card per Wikipedia page, one item per database study cited on it.
// Read-only with respect to Wikipedia: the only Wikipedia call is a revision-ID lookup (MediaWiki read API)
// when a card is opened. Reviews are kept in this browser and, when configured, in a shared store (store.js).
// Saved records and drafts. In shared mode each reviewer ID has its own namespace (Store.ns); ANON holds
// records saved without an ID, including everything from browser-only mode.
const ANON = Store.prefix + 'page:';
let LS = Store.ns() + 'page:';
const setNamespace = () => { LS = Store.ns() + 'page:'; };
const WELCOME_KEY = 'flora-en-edit-proto:welcome-hidden';

// Plain-language labels for the model's controlled vocabulary.
const ACTION = {
  no_change: 'No change needed', contextualise: 'Add missing context', narrow_claim: 'Make the claim more precise',
  replace_source: 'Replace the source', upgrade_source: 'Add a better source',
  remove_unsupported_claim: 'Remove an unsupported claim', remove_citation: 'Remove a citation',
  talk_page: 'Discuss on the talk page', defer: 'Needs more checking first'
};
const EDIT_ACTIONS = new Set(['contextualise', 'narrow_claim', 'replace_source', 'upgrade_source',
  'remove_unsupported_claim', 'remove_citation', 'talk_page']);
const SCOPE = {
  paper: 'Article about this study', effect: 'Article about this effect', effect_section: 'Section about this effect',
  broad_topic: 'Broad topic article', biography_history: 'Biography or history', incidental: 'Passing mention',
  list_or_bibliography: 'List or bibliography entry'
};
const USE = {
  current_empirical_support: 'cited as current evidence', historical_attribution: 'cited as history (who found what)',
  example: 'cited as an example', bibliography_listing: 'listed as a publication', unclear: 'use unclear'
};
const LEVEL = {full_text: 'Full text read', abstract: 'Abstract only', metadata_only: 'Title and details only',
  needs_source: 'Source still to find'};
const DECISIONS = {
  edit: 'I edited the article (in my own words)', talk: 'I raised it on the talk page',
  no_change: 'No change needed', later: 'Needs more checking first', skip: 'Skip (not my area / no access)'
};
const DECISION_QUEUE = {edit: 'retain', talk: 'retain', no_change: 'drop', later: 'defer', skip: 'defer'};
const KIND = {edit: ['Edit suggested', 'edit'], judgement: ['Judgement call', 'warn'], optional: ['Optional addition', 'info'],
  other: ['No change needed', 'none'], none: ['No change needed', 'none']};
const STRENGTH = {fix: 'Fix: the Wikipedia article says something the source does not support',
  recommended_addition: 'Add missing evidence: a replication that bears on this claim is not mentioned',
  optional_addition: 'Optional: the Wikipedia article is accurate; this would only add to it', none: 'Nothing to change'};

let DATA = null, PAGES = [], ACTIVE = null, SEGMENT = 'repl', SOURCES = {};
const filters = {};

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const doiLink = d => d && !/^needs/i.test(d) ? `<a href="https://doi.org/${esc(d)}" target="_blank" rel="noopener">doi:${esc(d)}</a>` : '';
// A source as a short author-year link; the full reference is in the tooltip and the DOI is the target.
function srcLink(d) {
  if (!d || /^needs/i.test(d)) return '';
  d = d.replace(/^doi:/i, '').trim();
  const s = SOURCES[d.toLowerCase()];
  return s ? `<a href="https://doi.org/${esc(d)}" target="_blank" rel="noopener" title="${esc(s.citation)}">${esc(s.label)}</a>` : doiLink(d);
}
// Open access next to a paper (#17): an unlocked padlock, gold when the publisher's own page is free (links the
// DOI), green when a free copy is elsewhere (links that copy). Closed papers get no icon; the list's
// "Library access" badge and filter cover them. With `text`, the label follows the icon.
const UNLOCK = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" focusable="false"><path d="M4.5 7V5a3.5 3.5 0 0 1 6.8-1.2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><rect x="2.5" y="7" width="11" height="8" rx="1.6" fill="currentColor"/></svg>';
function accessLink(d, text) {
  d = (d || '').replace(/^doi:/i, '').trim();
  const a = SOURCES[d.toLowerCase()]?.access;
  if (!a || !(a.url || a.kind === 'publisher')) return '';
  const pub = !a.url, label = pub ? 'Free to read at the publisher' : a.label;
  return `<a class="oa ${pub ? 'oa-gold' : 'oa-green'}" href="${esc(pub ? 'https://doi.org/' + d : a.url)}" target="_blank" rel="noopener" title="${esc(label)}" aria-label="${esc(label)}">${UNLOCK}${text ? `<span>${esc(label)}</span>` : ''}</a>`;
}
// What the model read. In lists, full text is the default and stays unmarked; anything less is named.
const lvlBadge = (l, quiet) => quiet && l === 'full_text' ? '' : `<span class="lvl ${l === 'full_text' ? '' : l === 'abstract' ? 'abs' : 'thin'}">${esc(LEVEL[l] || l)}</span>`;


function itemKind(it) { return it.kind || (EDIT_ACTIONS.has(it.suggestion.proposed_action) ? 'edit' : 'none'); }
// A no-change suggestion shown as a judgement call (#9): never headline it "No change needed".
const actionLabel = it => it.judgement_basis === 'replication_bears_on_claim' ? 'The AI suggests no change' : ACTION[it.suggestion.proposed_action];
const minorNotes = p => (p.adjacent.length || p.items.some(it => (it.suggestion.alternatives || []).length))
  && (pageKind(p) === 'other' || (pageKind(p) === 'judgement' && p.items.every(it => it.suggestion.proposed_action === 'no_change')));
const KORDER = {edit: 0, judgement: 1, optional: 2, other: 3, none: 4};
function pageKind(p) {
  const ks = p.items.map(itemKind);
  for (const k of ['edit', 'judgement', 'optional']) if (ks.includes(k)) return k;
  if (p.adjacent.length || p.items.some(it => (it.suggestion.alternatives || []).length)) return 'other';  // no change, minor notes
  return 'none';
}
// Our main scope: edits that bring in a replication the page does not yet cite. Whether that edit is
// recommended or optional is already carried by the kind label, so this is a plain yes/no marker.
const pageRepl = p => p.items.some(it => it.adds_replication);
// Whether every original and replication on the page can be read without a library subscription (#17).
const needsLibrary = p => p.items.some(it => [it.original, ...it.replications].some(s => SOURCES[s.doi.toLowerCase()]?.access?.kind === 'none'));
const flags = p => ({blp: p.items.some(i => i.suggestion.flags.blp), medrs: p.items.some(i => i.suggestion.flags.medrs)});

// Browser storage can be missing or blocked (private windows, previews): never let that break the page.
function lsGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function lsSet(k, v) { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* not stored */ } }
function ledgerGet(id) { try { return JSON.parse(lsGet(LS + id)) || null; } catch { return null; } }
function ledgerPut(id, rec) { lsSet(LS + id, JSON.stringify(rec)); }
// Drafts: the form as last typed, kept until "Save review". A card counts as reviewed only once saved.
function draftGet(id) { try { return JSON.parse(lsGet(LS + id + ':draft')) || null; } catch { return null; } }
function draftPut(id, d) { lsSet(LS + id + ':draft', d ? JSON.stringify(d) : null); }
const reviewed = p => { const r = ledgerGet(p.page_id); return !!r && p.items.every(it => r.items?.[it.card_id]); };
const hasDraft = p => !!draftGet(p.page_id);

// ---------- group progress (shared store only) ----------
// A review counts for the group once every publication on the card has a decision and at least one is
// "edited", "talk page" or "no change needed". It then waits for an audit: two people other than its
// reviewers confirming the work is finished.
const SETTLED = ['edit', 'talk', 'no_change'], ACTED = ['edit', 'talk'], AUDITS_NEEDED = 2;
const GROUP = {open: 'Nobody yet', under_review: 'Under review', to_audit: 'To be audited', audited: 'Audited'};
function groupState(p) {
  const s = Store.forPage(p.page_id), mine = Store.me()?.public_id;
  const complete = s.reviews.filter(r => p.items.every(it => r.record.items?.[it.card_id])
    && Object.values(r.record.items).some(d => SETTLED.includes(d)));
  // An audit counts only if it was made after the latest change of decisions in a counting review, and
  // never from anyone who reviewed the page.
  const decided = Math.max(0, ...complete.map(r => Date.parse(r.decided_at || r.updated_at)));
  const reviewers = new Set(s.reviews.map(r => r.public_id));
  const current = s.audits.filter(a => complete.length && !reviewers.has(a.public_id) && Date.parse(a.updated_at) >= decided);
  const confirmed = current.filter(a => a.finished);
  const state = !complete.length ? (s.claims.length ? 'under_review' : 'open') : confirmed.length >= AUDITS_NEEDED ? 'audited' : 'to_audit';
  return {...s, complete, current, confirmed, state, acted: complete.some(r => Object.values(r.record.items).some(d => ACTED.includes(d))),
    mine, claimedByMe: !!mine && s.claims.some(c => c.public_id === mine), reviewedByMe: !!mine && reviewers.has(mine),
    myAudit: mine ? current.find(a => a.public_id === mine) : null};
}
const names = rows => [...new Set(rows.map(r => r.initials))].join(', ');
function groupBadges(p) {
  if (!Store.shared) return '';
  const g = groupState(p);
  const claim = g.claims.length ? `<span class="badge review" title="Someone has marked this article as under review">Under review: ${esc(names(g.claims))}</span>` : '';
  if (g.state === 'audited') return claim + ' <span class="badge audited">✓ Audited</span>';
  if (g.state === 'to_audit') return claim + ` <span class="badge audit" title="Reviewed by ${esc(names(g.complete))}">To be audited ${g.confirmed.length}/${AUDITS_NEEDED}</span>`;
  return claim;
}

// ---------- list and filters ----------
const SEGMENTS = [
  ['repl', 'Adds a replication', p => !!pageRepl(p)],
  ['worth', 'Worth a look', p => ['edit', 'judgement'].includes(pageKind(p))], ['edit', 'Edit suggested', p => pageKind(p) === 'edit'],
  ['judgement', 'Judgement call', p => pageKind(p) === 'judgement'], ['optional', 'Optional addition', p => pageKind(p) === 'optional'],
  ['none', 'No change needed', p => ['other', 'none'].includes(pageKind(p))], ['all', 'All articles', () => true]];
const FACETS = [
  ['mine', 'My progress', p => reviewed(p) ? 'Reviewed' : hasDraft(p) ? 'Draft, not saved' : 'Not reviewed yet', true],
  ...(Store.shared ? [['group', 'Group progress', p => { const g = groupState(p);
    return [GROUP[g.state], g.claims.length && g.state !== 'under_review' && GROUP.under_review].filter(Boolean); }, true, Object.values(GROUP)]] : []),
  ['access', 'Reading the papers', p => needsLibrary(p) ? 'Some need library access' : 'All free to read', true],
  ['scope', 'Kind of article', p => SCOPE[p.items[0].suggestion.article_scope] || p.items[0].suggestion.article_scope, true],
  ['many', 'Publications on the page', p => p.items.length > 1 ? 'Several' : 'One', true],
  ['care', 'Extra care', p => [flags(p).blp && 'Living person (BLP)', flags(p).medrs && 'Health / medical (MEDRS)',
    p.live_check.changed_since_frozen && 'Article edited since'].filter(Boolean), true],
  ['evidence', 'What we could read', p => [...new Set(p.items.map(i => LEVEL[i.best_evidence]))], false],
];
const facetVals = (p, f) => { const v = f[2](p); return Array.isArray(v) ? v : [v]; };

function buildFilters() {
  const group = f => {
    const counts = {};
    PAGES.forEach(p => facetVals(p, f).forEach(v => counts[v] = (counts[v] || 0) + 1));
    const keys = f[4] ? f[4].filter(v => counts[v]) : Object.keys(counts).sort();  // f[4]: a fixed order (workflow stages)
    return `<fieldset class="fgroup"><legend>${esc(f[1])}</legend>` + keys.map(v =>
      `<label><input type="checkbox" data-f="${f[0]}" value="${esc(v)}" ${filters[f[0]]?.has(v) ? 'checked' : ''}> <span>${esc(v)}</span><span class="n">${counts[v]}</span></label>`).join('') + '</fieldset>';
  };
  document.getElementById('filter-groups').innerHTML = FACETS.filter(f => f[3]).map(group).join('') +
    `<details class="more"><summary>More filters</summary>${FACETS.filter(f => !f[3]).map(group).join('')}</details>`;
  document.querySelectorAll('#filter-groups input').forEach(i => i.addEventListener('change', () => {
    const s = filters[i.dataset.f] ||= new Set();
    i.checked ? s.add(i.value) : s.delete(i.value);
    renderList();
  }));
}
// "My progress" and "Group progress" change as people review: rebuild the filters when they change, keeping ticks.
let PROGRESS_SIG = '';
function refreshProgressFacet() {
  const live = FACETS.filter(f => ['mine', 'group'].includes(f[0]));
  const sig = PAGES.map(p => live.map(f => facetVals(p, f).join('+')).join('/')).join('|');
  if (sig !== PROGRESS_SIG) { PROGRESS_SIG = sig; buildFilters(); }
}
const activeFilters = () => Object.values(filters).reduce((n, s) => n + s.size, 0);
function clearFilters() { Object.keys(filters).forEach(k => delete filters[k]); buildFilters(); renderList(); }
// The main aim stands apart; "Worth a look" visibly contains the two kinds it combines.
function buildSegments() {
  const btn = (k, cls = '') => {
    const [, label, f] = SEGMENTS.find(s => s[0] === k), dot = KIND[k] ? `<span class="dot ${KIND[k][1]}" aria-hidden="true"></span>` : '';
    return `<button type="button" class="${cls}" data-seg="${k}" aria-pressed="${SEGMENT === k}">${dot}${esc(label)} <span class="n">${PAGES.filter(f).length}</span></button>`;
  };
  document.getElementById('segments').innerHTML = `
    <div class="seg-row" role="group" aria-labelledby="seg-main-l"><span class="seg-l" id="seg-main-l">Main aim</span>${btn('repl', 'seg-main')}</div>
    <div class="seg-row" role="group" aria-labelledby="seg-kind-l"><span class="seg-l" id="seg-kind-l">By kind of suggestion</span>
      <span class="seg-group" role="group" aria-label="Worth a look: edit suggested and judgement call together">${btn('worth', 'seg-head')}${btn('edit', 'seg-sub')}${btn('judgement', 'seg-sub')}</span>
      ${btn('optional')}${btn('none')}${btn('all')}</div>`;
  document.querySelectorAll('#segments button').forEach(b => b.onclick = () => { SEGMENT = b.dataset.seg; buildSegments(); renderList(); });
}
function visible() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const seg = SEGMENTS.find(s => s[0] === SEGMENT)[2];
  return PAGES.filter(p => seg(p) && FACETS.every(f => !filters[f[0]]?.size || facetVals(p, f).some(v => filters[f[0]].has(v)))
    && (!q || p.search.includes(q)));
}
function renderList() {
  refreshProgressFacet();
  const list = visible(), nf = activeFilters();
  const tf = document.getElementById('toggle-filters');
  tf.innerHTML = nf ? `Filters <span class="count">${nf} on</span>` : 'Filters';
  tf.classList.toggle('on', nf > 0);
  document.getElementById('clear-filters').hidden = !nf;
  document.getElementById('summary').innerHTML = `${list.length} of ${PAGES.length} articles shown` +
    (nf ? ` · ${nf} filter${nf > 1 ? 's' : ''} on <button type="button" class="linklike" id="summary-clear">clear</button>` : '');
  document.getElementById('summary-clear')?.addEventListener('click', clearFilters);
  document.getElementById('cards').innerHTML = list.map(p => {
    const [label, cls] = KIND[pageKind(p)], fl = flags(p);
    const studies = p.items.length > 1 ? `${p.items.length} publications: ${p.items.map(i => i.original.short.split(':')[0]).join('; ')}` : p.items[0].original.short;
    return `<li><button type="button" class="card-btn${ACTIVE === p.page_id ? ' active' : ''}" data-id="${p.page_id}" aria-current="${ACTIVE === p.page_id}">
      <span class="t">${esc(p.page.title)}</span>
      <span class="m">${esc(studies)}</span>
      <span class="badges"><span class="badge ${cls}">${label}</span>
      ${pageRepl(p) ? '<span class="badge repl">Adds a replication</span>' : ''}${minorNotes(p) ? '<span class="badge">Minor notes</span>' : ''}
      ${fl.blp ? '<span class="badge care">Living person</span>' : ''}${fl.medrs ? '<span class="badge care">Health</span>' : ''}
      ${p.live_check.changed_since_frozen ? '<span class="badge warn">Edited since</span>' : ''}${needsLibrary(p) ? '<span class="badge lib" title="At least one paper has no known free copy">Library access</span>' : ''}
      ${reviewed(p) ? `<span class="badge done">✓ ${Store.shared ? 'you reviewed' : 'reviewed'}</span>` : ''}${hasDraft(p) ? `<span class="badge draft">${reviewed(p) ? 'Unsaved changes' : 'Draft'}</span>` : ''}
      ${groupBadges(p)}</span></button></li>`;
  }).join('') || '<li class="small">No articles match. Try "All articles" or clear some filters.</li>';
  document.querySelectorAll('.card-btn').forEach(b => b.addEventListener('click', () => show(b.dataset.id, true)));
  updateLedgerCount();
}

// ---------- item blocks ----------
function markRefs(text) {
  return esc(text).replace(/\[FOCAL REF:([^\]]*)\]/g, (m, x) => `<mark class="focal" title="Citation of the study discussed here">[this study:${x}]</mark>`)
    .replace(/\[PAIRED REF:([^\]]*)\]/g, (m, x) => `<mark class="paired" title="Citation of a replication">[replication:${x}]</mark>`)
    .replace(/\[ref:([^\]]*)\]/g, '<span class="ref">[ref:$1]</span>');
}
// Compact citation markers for the sentence at issue; the full reference is in the tooltip.
const MARKER = /\[(FOCAL REF|PAIRED REF|ref):([^\]]*)\]/g;
function compactRefs(text) {
  let out = '', last = 0;
  for (const m of text.matchAll(MARKER)) {
    const full = m[2].trim(), yr = full.match(/\((\d{4})\)/)?.[1];
    const [cls, label] = m[1] === 'FOCAL REF' ? ['focal', 'this study'] : m[1] === 'PAIRED REF' ? ['paired', 'replication']
      : ['other', yr ? `other source, ${yr}` : 'other source'];
    out += esc(text.slice(last, m.index)) + `<span class="cite ${cls}" title="${esc(full)}">[${label}]</span>`;
    last = m.index + m[0].length;
  }
  return out + esc(text.slice(last));
}
// Find a quoted sentence in the article passages and return it with the citations it carries,
// including those right after it, so readers can see which source backs which part.
function withRefs(quote, occs) {
  const ws = c => /\s/.test(c), q = quote.replace(/\s+/g, ' ').trim();
  for (const o of occs) {
    const raw = o.paragraph_plain, at = [];
    let plain = '';
    for (let i = 0; i < raw.length; i++) {
      if (raw[i] === '[') { const m = raw.slice(i).match(/^\[(FOCAL REF|PAIRED REF|ref):[^\]]*\]/); if (m) { i += m[0].length - 1; continue; } }
      if (ws(raw[i])) { if (!plain.length || plain.endsWith(' ')) continue; plain += ' '; } else plain += raw[i];
      at.push(i);
    }
    const k = plain.indexOf(q);
    if (k < 0) continue;
    let end = at[k + q.length - 1] + 1;
    for (let m; (m = raw.slice(end).match(/^\s*\[(FOCAL REF|PAIRED REF|ref):[^\]]*\]/));) end += m[0].length;
    return compactRefs(raw.slice(at[k], end));
  }
  return esc(quote);
}
function highlight(text, quotes) {
  let h = markRefs(text);
  for (const q of quotes) {
    const e = esc(q.trim());
    if (e.length >= 40 && h.includes(e)) h = h.replace(e, `<mark class="claim">${e}</mark>`);
  }
  return h;
}
const normT = t => t.toLowerCase().replace(/\s+/g, ' ').trim();

function issueBlock(it) {
  const s = it.suggestion, d = s.draft;
  const target = d.target_text && ['replace', 'modify', 'remove', 'insert_after'].includes(d.operation) ? d.target_text : '';
  const claims = s.claim_sites.filter(x => x.is_visible_claim).map(x => x.visible_claim_quote);
  const lead = target || claims[0] || '';
  const others = claims.filter(q => !normT(lead).includes(normT(q)) && !normT(q).includes(normT(lead)));
  const label = target ? (d.operation === 'insert_after' ? 'The suggestion adds something after this sentence' : 'The sentence at issue')
    : claims.length ? 'Where the Wikipedia article relies on the study' : 'The study is not used for a visible claim';
  return `<h4>${esc(label)}</h4>
    ${lead ? `<blockquote class="target">${withRefs(lead, it.occurrences)}</blockquote>` : `<p>${esc(s.claim_sites[0]?.note || 'It only appears in a list or reference section.')}</p>`}
    ${others.length ? `<p class="small">Also cited for: ${others.map(q => `“${esc(q.length > 160 ? q.slice(0, 157) + '…' : q)}”`).join(' · ')}</p>` : ''}`;
}

const RESULT = {confirmed: ['✓ Confirmed', 'ok'], contradicted: ['✗ Contradicted', 'bad'], not_in_source: ['✗ Not in the source', 'bad'],
  source_unavailable: ['? Source not obtained', 'warn']};
const RESULT_WORD = {confirmed: 'confirmed', contradicted: 'contradicted', not_in_source: 'not in the source', source_unavailable: 'source not obtained'};

// "Your call": the editorial questions the AI could not settle about the suggestion above.
function yourCallBlock(it) {
  const s = it.suggestion, judge = s.required_checks || [];
  return `${judge.length ? `<h4 id="call-${it.card_id}">Your call on this edit</h4>
    <p class="small">Questions about the suggestion above that the AI could not settle. They are part of the same edit, not separate problems.</p>
    <ul class="tight">${judge.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    ${s.uncertainties.length ? `<details><summary>What remains uncertain (${s.uncertainties.length})</summary><ul class="tight">${s.uncertainties.map(u => `<li>${esc(u)}</li>`).join('')}</ul></details>` : ''}`;
}

// "What we checked": a count up front; points that need attention are shown, confirmed ones fold away.
function checksBlock(it) {
  const v = it.suggestion.verifications || [];
  if (!v.length) return '';
  const tally = {};
  v.forEach(x => tally[x.result] = (tally[x.result] || 0) + 1);
  const parts = Object.keys(RESULT).filter(k => tally[k]).map(k => `${tally[k]} ${RESULT_WORD[k]}`);
  const point = x => `<li>${x.result !== 'confirmed' ? `<span class="badge ${RESULT[x.result][1]}">${RESULT[x.result][0]}</span> ` : ''}<span class="who">AI:</span> ${esc(x.claim)}
      ${x.quote ? `<blockquote class="excerpt"><span class="who">Quote from ${srcLink(x.source)}</span> ${lvlBadge(x.evidence_level, true)}<br>“${esc(x.quote)}”</blockquote>`
        : `<span class="small">· ${srcLink(x.source)} ${lvlBadge(x.evidence_level, true)}</span>`}</li>`;
  const off = v.filter(x => x.result !== 'confirmed'), ok = v.filter(x => x.result === 'confirmed');
  return `<h5>What we checked</h5>
    <p class="check-sum"><strong>${v.length} check${v.length > 1 ? 's' : ''}: ${parts.join(', ')}.</strong>
      <span class="small">Each point is the AI's statement, followed by the passage it relies on, quoted from the paper named. The quotes appear word for word in the paper, but the AI may have misread them: check anything your edit will rely on.</span></p>
    ${off.length ? `<ul class="verifs">${off.map(point).join('')}</ul>` : ''}
    ${ok.length ? `<details><summary>${off.length ? 'Show' : 'Show all'} ${ok.length} confirmed point${ok.length > 1 ? 's' : ''}</summary><ul class="verifs">${ok.map(point).join('')}</ul></details>` : ''}`;
}

function evidenceBlock(it) {
  const used = it.suggestion.evidence_used;
  const excerpts = doi => used.filter(e => e.doi.toLowerCase() === doi.toLowerCase() && e.excerpt);
  const row = (role, s, extra) => {
    const ex = excerpts(s.doi);
    return `<tr><th scope="row">${role}</th><td>${esc(s.citation)}<br>${doiLink(s.doi)} ${accessLink(s.doi, true)}${extra || ''}
      ${ex.length ? `<details><summary>Passages quoted from this paper (${ex.length})</summary>${ex.map(e => `<blockquote class="excerpt">“${esc(e.excerpt)}”<br><span class="small"><span class="who">AI's note:</span> ${esc(e.what_it_supports)}</span></blockquote>`).join('')}</details>` : ''}</td>
      <td>${lvlBadge(s.evidence_level)}</td></tr>`;
  };
  const known = [it.original.doi, ...it.replications.map(r => r.doi)].map(x => x.toLowerCase());
  const extra = used.filter(e => !known.includes(e.doi.toLowerCase()));
  const revs = it.reviews_checked || [];
  const found = revs.filter(r => r.mentions);
  return `<h5>The papers</h5>
    <table class="evidence"><thead><tr><th>Role</th><th>Paper</th><th>What we could read</th></tr></thead><tbody>
    ${row('Original', it.original)}
    ${it.replications.map(r => row('Replication', r, `<br><span class="small">Database label: ${esc(r.flora_outcome)} (screening label, not citable)${r.doi_detected_on_page ? ' · already cited in the Wikipedia article' : ''}</span>`)).join('')}
    </tbody></table>
    ${extra.length ? `<details><summary>Other sources used for this card (${extra.length})</summary><ul class="tight">${extra.map(e => `<li>${srcLink(e.doi)} ${lvlBadge(e.evidence_level, true)} ${esc(e.what_it_supports)}${e.excerpt ? `<blockquote class="excerpt">“${esc(e.excerpt)}”</blockquote>` : ''}</li>`).join('')}</ul></details>` : ''}
    ${revs.length ? `<details><summary>Review articles we checked for the replication: ${found.length} of ${revs.length} cite or mention it</summary><ul class="tight">${revs.map(r => `<li>${esc(r.title)} · ${srcLink(r.doi)} ${lvlBadge(r.evidence_level, true)} · ${!r.mentions ? 'no mention found'
      : r.reference_list_only ? '<strong>cites it</strong> (in its reference list; no passage in the text found)' : '<strong>mentions it</strong>'}${r.mentions && r.snippets?.length ? `<blockquote class="excerpt"><span class="who">Quote from the review:</span><br>“${esc(r.snippets[0])}”</blockquote>` : ''}</li>`).join('')}</ul></details>` : ''}`;
}

// The suggested edit as a pointer (where, what kind of change, which sources), never as article prose:
// contributors write the text themselves from the points below.
const OPERATION = {insert_after: 'Add a sentence after the sentence quoted above', replace: 'Reword the sentence quoted above',
  modify: 'Adjust the sentence quoted above', remove: 'Remove the sentence quoted above'};
function pointerBlock(it) {
  const d = it.suggestion.draft;
  if (!['provided', 'conditional'].includes(d.status)) return '';
  const cites = (d.citations || []).filter(x => x && !/^needs/i.test(x));
  const op = d.target_text && OPERATION[d.operation];
  return `<dl class="edit-kv">${op ? `<dt>What</dt><dd>${esc(op)}</dd>` : ''}<dt>Where</dt><dd>${esc(d.location)}</dd>
    ${cites.length ? `<dt>Cite</dt><dd>${cites.map(srcLink).join('; ')}</dd>` : ''}</dl>`
    + `
    ${d.status === 'conditional' ? '<p class="small">This depends on one of the questions under “Your call on this edit”.</p>' : ''}`;
}

function writingBlock(it) {
  const s = it.suggestion;
  const points = s.content_points.filter(x => !/^needs/i.test(x.source));
  const pointer = pointerBlock(it), isEdit = EDIT_ACTIONS.has(s.proposed_action);
  const head = pointer ? `<h4 id="edit-${it.card_id}">Suggested edit</h4>${pointer}` : '';
  if (!points.length && !s.alternatives.length) return head;
  const unread = points.some(x => x.evidence_level !== 'full_text');
  return `${head}${points.length ? `<h5 class="sub-h">${pointer ? 'Points to cover' : isEdit ? 'Suggested points to cover' : 'Points worth knowing'}</h5>` : ''}
    ${unread ? '<p class="small">Points marked “Abstract only” or “Title and details only” were prepared without the full paper: check them against it.</p>' : ''}
    ${points.length ? `<ul class="tight">${points.map(x => `<li>${esc(x.point)} <span class="small">· ${srcLink(x.source)} ${lvlBadge(x.evidence_level, true)}</span></li>`).join('')}</ul>` : ''}
    ${s.alternatives.length ? `<details ${itemKind(it) === 'none' ? 'open' : ''}><summary>Other problems found and alternative fixes (${s.alternatives.length})</summary><ul class="tight">${s.alternatives.map(a => `<li>${esc(a.action)} <span class="small">${esc(a.when)}</span></li>`).join('')}</ul></details>` : ''}`;
}

function contextBlock(it) {
  const quotes = it.suggestion.claim_sites.map(x => x.visible_claim_quote);
  return `<details><summary>Where this study appears in the Wikipedia article (${it.occurrences.length})</summary>
    <p class="small"><mark class="focal">[this study]</mark> marks its citation, <mark class="paired">[replication]</mark> a replication's; <mark class="claim">underlined</mark> text is what the citation supports. Rendering is approximate; check the live page.</p>
    ${it.occurrences.map(o => `<h6>Section “${esc(o.section)}”${o.in_comment ? ' (hidden comment, not visible to readers)' : ''}</h6>
      <div class="passage">${highlight(o.paragraph_plain, quotes)}</div>
      <details><summary>Whole section</summary><div class="passage">${highlight(o.section_plain, quotes)}</div></details>`).join('')}</details>`;
}

function provenanceBlock(it) {
  const p = it.provenance, v = it.validation;
  const match = {matched: 'Yes', mismatch: 'No', not_applicable: 'Not applicable', partial: 'Partly', uncertain: 'Uncertain'};
  const covered = {yes: 'Yes', no: 'No', partial: 'Partly', unclear: 'Unclear'};
  return `<details class="provenance"><summary>How this suggestion was made</summary><dl class="kv">
    <dt>AI assessment</dt><dd>${esc(it.suggestion.assessment)}</dd>
    <dt>Does the replication test this claim?</dt><dd>${esc(match[it.suggestion.specific_study_match.status] || 'Uncertain')}: ${esc(it.suggestion.specific_study_match.note)}</dd>
    <dt>Does the Wikipedia article already cover it?</dt><dd>${esc(covered[it.suggestion.existing_acknowledgement.status] || 'Unclear')}: ${esc(it.suggestion.existing_acknowledgement.note)}</dd>
    <dt>Automatic checks</dt><dd>${v.errors.length ? `<span class="bad">${esc(v.errors.join('; '))}</span>` : 'Quotes, sources and numbers match the saved texts. This does not show that the suggestion is right.'}</dd>
    <dt>Status</dt><dd>Prepared with AI${p.finished_at ? ' on ' + esc(p.finished_at.slice(0, 10)) : ''}; not yet checked by people.</dd></dl></details>`;
}

const studyName = it => SOURCES[it.original.doi.toLowerCase()]?.label || it.original.short.split(':')[0];

// One study: the decision material first (gist, sentence, suggestion, edit, your call), then the
// material for checking the AI's work, set apart and quieter.
function itemSection(it, i, n) {
  const s = it.suggestion, k = itemKind(it), [label, cls] = KIND[k];
  const head = `${n > 1 ? `Publication ${i + 1} of ${n}: ` : ''}${it.original.short}`;
  // No-change cards say why up front (#9), so a reader can disagree on sight rather than take the label on trust.
  const bears = it.judgement_basis === 'replication_bears_on_claim';
  const whyNone = k === 'none' || k === 'other' || bears ? `${bears ? '<p class="twoRun"><strong>Judgement call: a replication bears on a claim this Wikipedia article relies on.</strong> The AI suggests no change; weigh its reasons and decide.</p>' : ''}<p class="why-none"><span class="who">Why the AI suggests no change:</span></p><ul class="tight">
      <li><strong>Does the replication test this sentence?</strong> ${esc(s.specific_study_match.note)}</li>
      <li><strong>Does the Wikipedia article already cover it?</strong> ${esc(s.existing_acknowledgement.note)}</li></ul>
      <p class="small">This is the AI's reading. If you think the replication does bear on the sentence, record your own decision below.</p>` : '';
  const more = [whyNone, it.rationale_rest ? `<p>${esc(it.rationale_rest)}</p>` : '',
    it.adds_replication ? '<p class="small">Adds a replication: the suggested edit cites a replication that this Wikipedia article does not cite yet.</p>' : '',
    it.two_run && !it.two_run.agree ? `<p class="twoRun"><strong>Judgement call: two independent AI assessments disagree.</strong> This one suggests “${esc(ACTION[it.two_run.shown.action])}”; the other suggests “${esc(ACTION[it.two_run.other.action])}”: ${esc(it.two_run.other.rationale)}</p>` : '',
    `<p class="small">${esc(SCOPE[s.article_scope] || s.article_scope)}, ${esc(USE[s.citation_function] || s.citation_function)}.${s.edit_strength && s.edit_strength !== 'none' ? ' ' + esc(STRENGTH[s.edit_strength]) + '.' : ''}</p>`].join('');
  const papers = `<p class="papers small"><span class="who">Papers:</span> original ${srcLink(it.original.doi)}${accessLink(it.original.doi)}${it.replications.map(r => ` · replication ${srcLink(r.doi)}${accessLink(r.doi)}`).join('')}</p>`;
  const body = `${papers}${issueBlock(it)}
    <h4>Suggestion</h4>
    <p class="gist"><strong>${esc(actionLabel(it))}</strong> <span class="sep" aria-hidden="true">·</span> ${label === actionLabel(it) ? '' : `<span class="badge ${cls}">${label}</span> <span class="sep" aria-hidden="true">·</span> `}${esc(it.gist || s.rationale)}</p>
    <div class="proposal ${cls}">${more}</div>
    ${writingBlock(it)}${yourCallBlock(it)}
    <div class="checking"><h4>Checking the AI's work</h4>
      ${checksBlock(it)}${evidenceBlock(it)}${contextBlock(it)}${provenanceBlock(it)}</div>`;
  return `<section class="item" id="item-${it.card_id}" aria-labelledby="h-${it.card_id}">
    <details ${k !== 'none' || n === 1 || s.alternatives.length ? 'open' : ''}><summary><h3 class="item-head" id="h-${it.card_id}">${esc(head)}</h3></summary>${body}</details></section>`;
}

function overview(p) {
  if (p.items.length < 2) return `<p class="overview one"><strong>1 publication to review on this page:</strong> ${esc(p.items[0].original.short)} · ${esc(actionLabel(p.items[0]))}</p>`;
  return `<section class="overview"><h3>${p.items.length} publications to review on this page</h3>
    <p class="small">Each is a paper the Wikipedia article cites that others have tried to replicate. One paper can report several studies; a replication may test only some of them.</p>
    <ol>${p.items.map(it => `<li><a href="#item-${it.card_id}" data-jump="${it.card_id}">${esc(it.original.short)}</a> · ${esc(actionLabel(it))}</li>`).join('')}</ol></section>`;
}

function otherFixesBlock(p) {
  if (!p.adjacent.length) return '';
  return `<section class="other-fixes" id="other-fixes"><h3>Other problems spotted on this page</h3>
    <p class="small">Unrelated to the replication question. The AI checked each against the article text; check it yourself before acting.</p>
    <ul class="tight">${p.adjacent.map(x => `<li><blockquote class="target small-q">${esc(x.sentence)}</blockquote>${esc(x.issue)} <strong>Suggested:</strong> ${esc(x.suggested_action)}</li>`).join('')}</ul></section>`;
}

// Form values: an unsaved draft wins over the saved record.
function decisionBlock(p, rec, draft) {
  const f = draft || rec;
  return `<section class="ledger" id="record" aria-labelledby="record-h"><h3 id="record-h">Record your review</h3>
    ${Store.shared ? `<p class="small">Your review is kept in this browser and shared with the group when you save it${Store.me() ? '' : ' (sign in under “Your reviews” first)'}.</p>`
    : '<p class="small proto-note">Prototype limitation: reviews are saved only in this browser until shared storage is added. Export them to keep a copy.</p>'}
    <p class="small">Make any edit on Wikipedia itself (<a href="${esc(p.page.live_url)}" target="_blank" rel="noopener">open the article ↗</a>), then record here what you did.
      What you enter is kept as a draft as you go; the card counts as reviewed once you click “Save review”.</p>
    ${p.items.map((it, i) => `<fieldset><legend>${p.items.length > 1 ? `Publication ${i + 1}: ` : 'Your decision: '}${esc(studyName(it))} <span class="small">(suggested: ${esc(actionLabel(it))})</span></legend>
      ${Object.entries(DECISIONS).map(([k, v]) => `<label class="radio"><input type="radio" name="dec-${it.card_id}" value="${k}" ${f.items?.[it.card_id] === k ? 'checked' : ''}> ${esc(v)}</label>`).join('')}</fieldset>`).join('')}
    ${p.adjacent.length ? `<label class="radio"><input type="checkbox" id="l-other" ${f.other_fix_done ? 'checked' : ''}> I dealt with the other problem(s) spotted on this page</label>` : ''}
    <label for="l-useful">Was this card useful?</label>
    <select id="l-useful"><option value="">–</option>${['useful', 'partly useful', 'not useful', 'misleading'].map(v => `<option ${f.draft_usefulness === v ? 'selected' : ''}>${v}</option>`).join('')}</select>
    <label for="l-notes">Notes (reasons, sources you checked, what you plan to write)</label>
    <textarea id="l-notes">${esc(f.notes || '')}</textarea>
    <p id="l-hint" class="small warntext" hidden>You disagreed with a suggestion: please add a short reason in the notes.</p>
    <div class="row"><button type="button" id="l-save" class="primary">Save review</button>
    <span id="l-status" class="small" role="status">${statusText(rec, draft)}</span></div></section>`;
}
const stamp = t => esc((t || '').slice(0, 16).replace('T', ' '));
function statusText(rec, draft) {
  if (draft) return `Draft kept ${stamp(draft.saved_at)}: not counted as reviewed until you click “Save review”.`;
  return rec.updated_at ? `Saved ${stamp(rec.updated_at)}` : 'Not saved yet';
}

const baseRec = p => ({page_id: p.page_id, page_title: p.page.title, reviewed_revision_id: p.page.frozen_revid, items: {}});

// Sticky bar: the card title (once the heading has scrolled away) and jump links to the parts of the card.
function cardBar(p) {
  // Several publications: the overview box below the title links to each, so the bar does not repeat them.
  const links = p.items.length > 1 ? []
    : [[`edit-${p.items[0].card_id}`, 'Suggested edit'], [`call-${p.items[0].card_id}`, 'Your call']]
      .filter(([id]) => p.items[0].suggestion && (id.startsWith('edit-') ? ['provided', 'conditional'].includes(p.items[0].suggestion.draft.status)
        : (p.items[0].suggestion.required_checks || []).length));
  if (p.adjacent.length) links.push(['other-fixes', 'Other problems']);
  return `<div class="card-bar" id="card-bar"><button type="button" class="back" id="back">← List</button><span class="card-bar-title" aria-hidden="true">${esc(p.page.title)}</span>
    <nav aria-label="On this card">${links.map(([id, l]) => `<a href="#${id}" data-to="${id}">${esc(l)}</a>`).join('')}
      <a href="#record" data-to="record" class="to-record">Record your review ↓</a></nav></div>`;
}

function formState(p) {
  return {items: Object.fromEntries(p.items.map(it => [it.card_id, document.querySelector(`input[name="dec-${it.card_id}"]:checked`)?.value || ''])
      .filter(([, v]) => v)),
    other_fix_done: document.getElementById('l-other')?.checked || false,
    draft_usefulness: document.getElementById('l-useful').value, notes: document.getElementById('l-notes').value};
}
const sameForm = (a, b) => JSON.stringify(a.items || {}) === JSON.stringify(b.items || {}) && !!a.other_fix_done === !!b.other_fix_done
  && (a.draft_usefulness || '') === (b.draft_usefulness || '') && (a.notes || '') === (b.notes || '');

let NOTES_TIMER = null;
function show(id, focus) {
  ACTIVE = id;
  const p = PAGES.find(x => x.page_id === id), pg = p.page, lc = p.live_check, rec = ledgerGet(id) || baseRec(p), fl = flags(p);
  history.replaceState(null, '', '#' + id);
  document.getElementById('layout').classList.add('has-card');
  const detail = document.getElementById('detail');
  detail.innerHTML = `
    ${cardBar(p)}
    <h2 id="card-title" tabindex="-1">${esc(pg.title)}</h2>
    <div class="links"><span class="links-l">Wikipedia:</span> <a href="${esc(pg.live_url)}" target="_blank" rel="noopener">Open article</a>
      <a href="${esc(pg.talk_url)}" target="_blank" rel="noopener">Talk page</a>
      <a href="${esc(pg.diff_url)}" target="_blank" rel="noopener">Changes since this snapshot</a>
      <a href="${esc(pg.frozen_url)}" target="_blank" rel="noopener">Snapshot version</a></div>
    ${Store.shared ? '<div class="claimbar" id="claimbar"></div>' : ''}
    <div class="revbar ${lc.changed_since_frozen ? 'warn' : ''}" id="revbar">
      <span id="rev-msg">${lc.changed_since_frozen ? `⚠ The article has been edited since this snapshot (${esc(pg.frozen_timestamp.slice(0, 10))}). Check the changes before acting.`
        : `Snapshot from ${esc(pg.frozen_timestamp.slice(0, 10))}; unchanged when last checked (${esc((lc.checked_at || '').slice(0, 10))}).`}</span>
      <button type="button" id="l-check">Check now</button></div>
    ${fl.blp ? '<p class="care-note">Living person: findings are about studies, not people. Follow <a href="https://en.wikipedia.org/wiki/Wikipedia:Biographies_of_living_persons" target="_blank" rel="noopener">WP:BLP</a> and do not imply misconduct.</p>' : ''}
    ${fl.medrs ? '<p class="care-note">Health or medical content: single studies and replications are usually not enough (<a href="https://en.wikipedia.org/wiki/Wikipedia:Identifying_reliable_sources_(medicine)" target="_blank" rel="noopener">WP:MEDRS</a>).</p>' : ''}
    ${overview(p)}${p.items.map((it, i) => itemSection(it, i, p.items.length)).join('')}${otherFixesBlock(p)}${Store.shared ? '<section class="group" id="group" aria-labelledby="group-h"></section>' : ''}${decisionBlock(p, rec, draftGet(id))}`;
  // Scroll within the card pane on desktop, the page on mobile; open a folded study before jumping into it.
  detail.scrollTop = 0;
  const jump = target => {
    const el = document.getElementById(target);
    if (!el) return;
    el.closest('details')?.setAttribute('open', '');
    el.querySelector?.('details')?.setAttribute('open', '');
    el.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
  };
  detail.querySelectorAll('[data-to]').forEach(a => a.onclick = e => { e.preventDefault(); jump(a.dataset.to); });
  detail.querySelectorAll('[data-jump]').forEach(a => a.onclick = e => { e.preventDefault(); jump('item-' + a.dataset.jump); });
  const bar = document.getElementById('card-bar');
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([e]) => bar.classList.toggle('stuck', !e.isIntersecting), {root: matchMedia('(max-width: 1100px)').matches ? null : detail})
      .observe(document.getElementById('card-title'));
  }

  document.getElementById('back').onclick = () => { document.getElementById('layout').classList.remove('has-card'); document.querySelector(`.card-btn[data-id="${id}"]`)?.focus(); };
  // Autosave: every change to the form is kept as a draft; a draft equal to the saved record is dropped.
  clearTimeout(NOTES_TIMER);  // a notes autosave pending from the previous drawing of a card must not fire
  // The form belongs to the reviewer ID it was drawn for. If the ID changed since (another tab), redraw
  // instead of keeping a draft or saving, so one person's form is never stored or sent as another's.
  const drawnFor = LS;
  const stale = () => { if (drawnFor === Store.ns() + 'page:') return false; setNamespace(); paintIdentity(); reshow(); return true; };
  const keepDraft = () => {
    if (stale()) return;
    const f = formState(p), saved = ledgerGet(id) || baseRec(p);
    const same = sameForm(f, saved);
    draftPut(id, same ? null : {...f, saved_at: new Date().toISOString()});
    document.getElementById('l-status').textContent = statusText(saved, draftGet(id)).replace(/&amp;/g, '&');
    renderList();
  };
  const form = document.getElementById('record');
  form.addEventListener('change', e => { if (e.target.id !== 'l-save') keepDraft(); });
  document.getElementById('l-notes').addEventListener('input', () => { clearTimeout(NOTES_TIMER); NOTES_TIMER = setTimeout(keepDraft, 600); });
  document.getElementById('l-save').onclick = async () => {
    clearTimeout(NOTES_TIMER);
    if (stale()) return;
    const f = formState(p), notes = f.notes;
    // A reason is required only when a decision departs from that study's suggestion.
    const disagrees = p.items.some(it => {
      const d = f.items[it.card_id], k = itemKind(it);
      if (k === 'judgement' || k === 'optional') return false;  // either answer is fine without a reason
      const expected = k === 'edit' ? ['edit', 'talk'] : ['no_change'];
      return d && d !== 'skip' && !expected.includes(d);
    });
    const hint = document.getElementById('l-hint');
    hint.hidden = !(disagrees && !notes.trim());
    if (!hint.hidden) { keepDraft(); document.getElementById('l-notes').focus(); return; }
    const r = {...(ledgerGet(id) || baseRec(p)), ...f, reviewer: Store.me()?.initials || document.getElementById('reviewer').value, updated_at: new Date().toISOString()};
    ledgerPut(id, r);
    draftPut(id, null);
    const missingItems = p.items.filter(it => !f.items[it.card_id]).length;
    const said = missingItems
      ? `Saved. Choose a decision for ${missingItems === 1 ? 'the remaining publication' : `all ${missingItems} remaining publications`} to mark the card as reviewed.`
      : 'Saved: the card counts as reviewed.';
    const status = document.getElementById('l-status');
    status.textContent = said;
    renderList();
    if (!Store.shared) return;
    status.textContent = said + ' Sharing…';
    const sent = await Store.push(id, r);
    await Store.refresh();
    if (ACTIVE !== id) return;
    status.textContent = said + (sent.ok ? ' Shared with the group.'
      : !Store.me() ? ' Kept in this browser: sign in under “Your reviews” to share it.'
      : ` Kept in this browser; not shared yet (${sent.error}). It will be sent next time.`);
    renderAll();
  };
  // The snapshot check runs whenever a card is opened; the button repeats it. The result is kept with a
  // saved review (not a new record) so exports show which version the reviewer last saw.
  const checkLive = async () => {
    const msg = document.getElementById('rev-msg');
    msg.textContent = 'Checking Wikipedia for changes since this snapshot…';
    try {
      const resp = await fetch(`https://en.wikipedia.org/w/api.php?action=query&prop=revisions&pageids=${pg.pageid}&rvprop=ids|timestamp&format=json&formatversion=2&origin=*`);
      const rev = (await resp.json()).query.pages[0].revisions[0];
      const same = String(rev.revid) === String(pg.frozen_revid);
      if (ACTIVE !== id) return null;
      if (ledgerGet(id)) ledgerPut(id, {...ledgerGet(id), live_revision_checked: rev.revid, live_checked_at: new Date().toISOString()});
      document.getElementById('revbar').className = 'revbar ' + (same ? 'okbar' : 'warn');
      msg.textContent = same ? '✓ Unchanged: the live article is the version this card describes.'
        : `⚠ Edited on ${rev.timestamp.slice(0, 10)}. Open "Changes since this snapshot" to see whether the issue is still there.`;
      return !same;
    } catch (e) {
      if (ACTIVE === id) msg.textContent = 'Could not reach Wikipedia: ' + e;
      return null;
    }
  };
  document.getElementById('l-check').onclick = checkLive;
  paintGroup(p);
  renderList();
  if (focus) document.getElementById('card-title').focus({preventScroll: true});
  checkLive().then(changed => { if (ACTIVE === id) maybeAuditPrompt(p, changed ?? !!lc.changed_since_frozen); });
}

// ---------- group progress on a card ----------
const ago = t => { const m = Math.round((Date.now() - Date.parse(t)) / 60000);
  return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 48 * 60 ? `${Math.round(m / 60)} h ago` : `on ${t.slice(0, 10)}`; };
const decisionsText = (p, r) => p.items.map(it => (p.items.length > 1 ? `${studyName(it)}: ` : '') + (DECISIONS[r.record.items?.[it.card_id]] || 'no decision yet')).join('; ');
function openMine(focusId) {
  const m = document.getElementById('mine-menu');
  // After this click has finished bubbling, so the close-on-outside-click handler does not shut it again.
  setTimeout(() => { m.open = true; document.getElementById(focusId || 'sid-id')?.focus(); }, 0);
}
// The "I'm reviewing this now" toggle and the group section; repainted when the shared store changes.
function paintGroup(p) {
  if (!Store.shared || ACTIVE !== p.page_id) return;
  const g = groupState(p), bar = document.getElementById('claimbar'), sec = document.getElementById('group');
  if (!bar || !sec || sec.contains(document.activeElement)) return;  // do not repaint under someone typing an audit note
  const others = g.claims.filter(c => c.public_id !== g.mine);
  bar.innerHTML = `<button type="button" id="claim" aria-pressed="${g.claimedByMe}" class="${g.claimedByMe ? 'on' : ''}">${g.claimedByMe ? '✓ You are reviewing this' : 'I’m reviewing this now'}</button>
    <span class="small">${others.length ? `${esc(names(others))} ${others.length > 1 ? 'are' : 'is'} reviewing it (since ${esc(ago(others[0].started_at))}).`
      : g.claimedByMe ? 'Others see this article as under review until you save your review or switch this off.' : 'Mark the article so others know you are working on it.'}</span>
    ${g.state === 'audited' ? '<span class="badge audited">✓ Audited</span>' : g.state === 'to_audit' ? `<span class="badge audit">To be audited ${g.confirmed.length}/${AUDITS_NEEDED}</span>` : ''}`;
  document.getElementById('claim').onclick = async () => {
    if (!Store.me()) return openMine();
    const r = await Store.claim(p.page_id, !g.claimedByMe);
    if (!r.ok) bar.querySelector('.small').textContent = 'Could not reach the shared store: ' + r.error;
    await Store.refresh(); renderAll();
  };
  const theirs = g.reviews.filter(r => r.public_id !== g.mine);
  const audits = g.audits.map(a => `<li${g.current.includes(a) ? '' : ' class="stale"'}><strong>${esc(a.initials)}</strong> ${a.finished ? 'confirmed the work is finished' : 'found it not finished yet'} (${esc(ago(a.updated_at))})${a.note ? `: ${esc(a.note)}` : ''}${g.current.includes(a) ? '' : ' <span class="small">(before the latest review, so it no longer counts)</span>'}</li>`).join('');
  const canAudit = g.complete.some(r => r.public_id !== g.mine) && !g.reviewedByMe;
  sec.innerHTML = `<h3 id="group-h">Group progress</h3>
    <p>${g.state === 'audited' ? `Audited: ${g.confirmed.length} people confirmed the work is finished.`
      : g.state === 'to_audit' ? `Reviewed, to be audited: ${g.confirmed.length} of the ${AUDITS_NEEDED} confirmations needed from people other than the reviewer.`
      : 'Nobody has saved a complete review of this article yet.'}</p>
    ${theirs.length ? `<ul class="tight group-reviews">${theirs.map(r => `<li><strong>${esc(r.initials)}</strong> (${esc(ago(r.updated_at))}): ${esc(decisionsText(p, r))}${r.record.draft_usefulness ? ` · card ${esc(r.record.draft_usefulness)}` : ''}
      ${r.record.notes ? `<blockquote class="small-q">${esc(r.record.notes)}</blockquote>` : ''}</li>`).join('')}</ul>` : ''}
    ${audits ? `<h4>Audits</h4><ul class="tight">${audits}</ul>` : ''}
    ${canAudit ? auditControls(g) : g.reviewedByMe && g.complete.length ? '<p class="small">You reviewed this article, so two other people need to audit it.</p>' : ''}`;
  wireAudit(sec, p);
}
function auditControls(g, popup) {
  if (!Store.me()) return `<p class="small">To audit this review, <button type="button" class="linklike" data-signin>sign in under “Your reviews”</button>.</p>`;
  const was = g.myAudit ? `<p class="small">You said: ${g.myAudit.finished ? 'finished' : 'not finished yet'} (${esc(ago(g.myAudit.updated_at))}). You can change it.</p>` : '';
  return `<div class="audit-form">${popup ? '' : '<p><strong>Audit:</strong> is the work on this article finished?</p>'}${was}
    <label class="small" for="a-note${popup ? '-m' : ''}">Note (optional)</label><textarea id="a-note${popup ? '-m' : ''}" class="a-note" rows="2">${esc(g.myAudit?.note || '')}</textarea>
    <div class="row"><button type="button" class="primary" data-audit="1">${g.acted ? 'Mark as finished' : 'I agree: no change needed'}</button>
      <button type="button" data-audit="0">${g.acted ? 'Not finished yet' : 'I disagree'}</button>
      ${popup ? '<button type="button" data-later>Decide later</button>' : ''}<span class="small a-status" role="status"></span></div></div>`;
}
function wireAudit(root, p, done) {
  const drawnFor = Store.me()?.reviewer_id;  // audit controls act only for the ID they were drawn for
  root.querySelectorAll('[data-signin]').forEach(b => b.onclick = () => { done?.(); openMine(); });
  root.querySelectorAll('[data-later]').forEach(b => b.onclick = () => done?.());
  root.querySelectorAll('[data-audit]').forEach(b => b.onclick = async () => {
    if (Store.me()?.reviewer_id !== drawnFor) { done?.(); setNamespace(); paintIdentity(); reshow(); return; }
    const st = root.querySelector('.a-status');
    st.textContent = 'Saving…';
    const r = await Store.audit(p.page_id, b.dataset.audit === '1', root.querySelector('.a-note')?.value);
    if (!r.ok) { st.textContent = 'Not saved: ' + r.error; return; }
    await Store.refresh();
    done?.(); renderAll();
  });
}
// When a card that someone else reviewed is opened: if they edited and the article has changed since the
// snapshot, the work is probably done; if they found no change needed, that still needs a second look.
function maybeAuditPrompt(p, changed) {
  if (!Store.shared) return;
  const g = groupState(p), key = Store.prefix + 'prompted:' + p.page_id;
  const theirs = g.complete.filter(r => r.public_id !== g.mine);
  if (!theirs.length || g.state === 'audited' || g.reviewedByMe || g.myAudit) return;
  if (g.acted && !changed) return;
  try { if (sessionStorage.getItem(key)) return; sessionStorage.setItem(key, '1'); } catch { /* ask again next time */ }
  const who = theirs.map(r => `<li><strong>${esc(r.initials)}</strong> (${esc(ago(r.updated_at))}): ${esc(decisionsText(p, r))}${r.record.notes ? `<blockquote class="small-q">${esc(r.record.notes)}</blockquote>` : ''}</li>`).join('');
  const box = document.getElementById('audit-box'), modal = document.getElementById('audit-modal');
  box.innerHTML = g.acted
    ? `<h2 id="audit-title">This article has likely been finished</h2>
      <p>Someone recorded an edit or talk-page post for “${esc(p.page.title)}”, and the article has changed since our snapshot.</p><ul class="tight">${who}</ul>
      <p><a href="${esc(p.page.diff_url)}" target="_blank" rel="noopener">See the changes since the snapshot ↗</a></p>
      <p class="small">If the change is there and sound, mark the article as finished. It counts as audited once ${AUDITS_NEEDED} people other than the reviewer have confirmed it (${g.confirmed.length} so far).</p>`
    : `<h2 id="audit-title">A reviewer found no change needed</h2>
      <p>Someone who reviewed “${esc(p.page.title)}” decided that no change is needed. That still needs a second look: read the card and the article, then say whether you agree.</p><ul class="tight">${who}</ul>
      <p class="small">The article counts as audited once ${AUDITS_NEEDED} people other than the reviewer agree (${g.confirmed.length} so far).</p>`;
  box.insertAdjacentHTML('beforeend', auditControls(g, true) + (Store.me() ? '' : '<div class="row"><button type="button" data-later>Close</button></div>'));
  const prev = document.activeElement;
  const close = () => { modal.hidden = true; prev?.focus?.(); };
  modal.hidden = false;
  modal.onkeydown = e => { if (e.key === 'Escape') close(); };
  wireAudit(box, p, close);
  box.querySelector('button')?.focus();
}
function renderAll() {
  renderList();
  const p = PAGES.find(x => x.page_id === ACTIVE);
  if (p) paintGroup(p);
}

// ---------- ledger export ----------
const EXPORT_KEY = 'flora-en-edit-proto:last-export';
function updateLedgerCount() {
  const drafts = PAGES.filter(hasDraft).length;
  const done = PAGES.filter(reviewed).length;
  document.getElementById('mine-n').textContent = `${done} of ${PAGES.length}`;
  document.getElementById('ledger-count').innerHTML = `<strong>${done} of ${PAGES.length}</strong> articles reviewed` +
    (drafts ? ` · <span class="badge draft">${drafts} with a draft</span>` : '');
  // Remind people to export once they have saved work that no export contains yet.
  const last = lsGet(EXPORT_KEY) || '';
  const fresh = PAGES.map(p => ledgerGet(p.page_id)).filter(r => r?.updated_at && r.updated_at > last).length;
  const el = document.getElementById('export-reminder');
  el.hidden = !fresh;
  document.getElementById('mine-menu').classList.toggle('unexported', !!fresh);
  el.textContent = `${fresh} saved review${fresh > 1 ? 's are' : ' is'} not in an export yet. Reviews stay only in this browser: export them to keep a copy or share them.`;
  if (Store.shared) {  // the shared store replaces the export reminder; warn only about reviews not sent yet
    // Signed out, every review saved here is unshared (it has no reviewer ID yet).
    const unsent = Store.me() ? Store.pending().length : PAGES.filter(p => ledgerGet(p.page_id)?.updated_at).length;
    el.hidden = !unsent;
    document.getElementById('mine-menu').classList.toggle('unexported', !!unsent);
    el.innerHTML = `${unsent} saved review${unsent > 1 ? 's are' : ' is'} kept in this browser but not shared yet` +
      (Store.me() ? `. <button type="button" class="linklike" id="retry-sync">Try again</button>` : ': sign in to share.');
    document.getElementById('retry-sync')?.addEventListener('click', syncNow);
  }
}
// ---------- identity (shared store only) ----------
function paintIdentity() {
  if (!Store.shared) return;
  const box = document.getElementById('mine-id'), who = Store.me();
  box.hidden = false;
  document.getElementById('initials-label').hidden = true;
  box.innerHTML = (Store.demo ? '<p class="small warntext">Demo mode: shared reviews are pretend and stay in this browser.</p>' : '') + (who
    ? `<p class="small">Signed in as <strong class="rid">${esc(who.reviewer_id)}</strong>. Keep this ID: it is how you sign in on another device.
        Others see only your initials. <button type="button" class="linklike" id="sign-out">Sign out</button></p>` +
      (anonRecords().length ? `<p class="small">${anonRecords().length} review${anonRecords().length > 1 ? 's' : ''} in this browser
        ${anonRecords().length > 1 ? 'were' : 'was'} saved without a reviewer ID. If you wrote ${anonRecords().length > 1 ? 'them' : 'it'}:
        <button type="button" id="adopt">Share as ${esc(who.reviewer_id)}</button></p>` : '')
    : `<form id="sign-in" class="id-form"><label class="small" for="sid-id">Your reviewer ID</label>
        <span class="row"><input id="sid-id" placeholder="e.g. BS#1312" autocomplete="username" maxlength="9"><button type="submit">Sign in</button></span></form>
      <details class="new-id"><summary class="small">New here? Get a reviewer ID</summary>
      <form id="register" class="id-form"><span class="row"><label class="small">Initials <input id="reg-ini" maxlength="4" size="4" required></label>
        <label class="small">Number <input id="reg-num" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" size="4" placeholder="any"></label></span>
        <label class="small" for="reg-email">Email (optional, so the organisers can remind you of your ID)</label>
        <input id="reg-email" type="email" autocomplete="email">
        <button type="submit">Get my ID</button></form></details>`) + '<p class="small warntext" id="id-msg" role="status"></p>';
  const msg = t => { document.getElementById('id-msg').textContent = t; };
  document.getElementById('sign-out')?.addEventListener('click', () => { Store.signOut(); setNamespace(); paintIdentity(); reshow(); });
  document.getElementById('adopt')?.addEventListener('click', adopt);
  document.getElementById('sign-in')?.addEventListener('submit', async e => {
    e.preventDefault(); msg('Signing in…');
    const r = await Store.signIn(document.getElementById('sid-id').value);
    if (!r.ok) return msg(r.error);
    await afterSignIn();
  });
  document.getElementById('register')?.addEventListener('submit', async e => {
    e.preventDefault(); msg('Creating your ID…');
    const r = await Store.register(document.getElementById('reg-ini').value, document.getElementById('reg-email').value, document.getElementById('reg-num').value);
    if (!r.ok) return msg('Could not create an ID: ' + r.error);
    await afterSignIn();
  });
}
// After signing in: bring this reviewer's shared records into this browser (newer copy wins), send
// anything saved here that the shared store does not have yet, and repaint.
async function afterSignIn() {
  setNamespace();
  // The records go into the namespace of the reviewer who signed in, named explicitly: another tab may
  // change the sign-in (and this tab's LS) while the request is out.
  const who = Store.me(), into = who && Store.nsFor(who) + 'page:', r = await Store.mine();
  if (!who || Store.me()?.public_id !== who.public_id) return;
  if (r.ok) for (const rec of r.v || []) {
    let here = null; try { here = JSON.parse(lsGet(into + rec.page_id)); } catch { /* none */ }
    if (PAGES.some(x => x.page_id === rec.page_id) && (!here || (here.updated_at || '') < rec.updated_at)) lsSet(into + rec.page_id, JSON.stringify(rec));
  }
  await syncNow();
  paintIdentity();
  reshow();
}
// Records saved without a reviewer ID: shared only when their author says so, then moved to that ID.
function anonRecords() {
  if (!Store.me()) return [];
  return PAGES.map(p => { try { return JSON.parse(lsGet(ANON + p.page_id)); } catch { return null; } }).filter(r => r?.updated_at);
}
async function adopt() {
  for (const rec of anonRecords()) {
    const here = ledgerGet(rec.page_id);
    if (!here || (here.updated_at || '') < rec.updated_at) {
      const r = {...rec, reviewer: Store.me().initials, updated_at: new Date().toISOString()};
      ledgerPut(rec.page_id, r);
      Store.queue(rec.page_id, r);
    }
    if (!draftGet(rec.page_id) && lsGet(ANON + rec.page_id + ':draft')) lsSet(LS + rec.page_id + ':draft', lsGet(ANON + rec.page_id + ':draft'));
    lsSet(ANON + rec.page_id, null); lsSet(ANON + rec.page_id + ':draft', null);
  }
  await syncNow();
  paintIdentity();
  reshow();
}
function reshow() {
  const p = PAGES.find(x => x.page_id === ACTIVE);
  if (p) show(p.page_id, false); else renderAll();
}
// Signing in or out in another tab changes the ID here too: switch records and redraw.
window.addEventListener('storage', e => {
  if (!Store.shared || e.key !== Store.meKey) return;
  document.getElementById('audit-modal').hidden = true;  // drawn for the previous ID
  setNamespace(); paintIdentity(); reshow();
  Store.refresh().then(renderAll);
});
async function syncNow() {
  if (Store.shared) { await Store.flush(); await Store.refresh(); }
  renderAll();
}
function markExported() { lsSet(EXPORT_KEY, new Date().toISOString()); updateLedgerCount(); }
function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], {type}));
  a.download = name; a.click();
}
function ledgerRows() {
  const rows = [];
  for (const p of PAGES) {
    const r = ledgerGet(p.page_id);
    if (!r?.items) continue;
    for (const it of p.items) {
      const d = r.items[it.card_id];
      if (!d) continue;
      rows.push({page_id: p.page_id, page_title: p.page.title, card_id: it.card_id, study: it.original.short,
        reviewed_revision_id: r.reviewed_revision_id, live_revision_checked: r.live_revision_checked || '',
        stale_revision: r.live_revision_checked ? String(r.live_revision_checked) !== String(p.page.frozen_revid) : 'unchecked',
        decision: d, decision_label: DECISIONS[d], queue_decision: DECISION_QUEUE[d],
        other_fix_done: r.other_fix_done || false, card_usefulness: r.draft_usefulness || '', reviewer: r.reviewer || '',
        updated_at: r.updated_at, ai_suggested_action: it.suggestion.proposed_action, notes: r.notes || ''});
    }
  }
  return rows;
}

// ---------- welcome ----------
let STEP = 0;
function showStep(i) {
  const steps = [...document.querySelectorAll('#welcome .step')], last = steps.length - 1;
  STEP = Math.max(0, Math.min(i, last));
  steps.forEach((s, k) => s.hidden = k !== STEP);
  document.getElementById('step-count').textContent = `Step ${STEP + 1} of ${steps.length}`;
  document.getElementById('step-back').hidden = STEP === 0;
  document.getElementById('step-next').textContent = STEP === last ? 'Start reviewing' : 'Next';
  document.getElementById('welcome-close').hidden = STEP === last;
  document.querySelector('#welcome .modal-box').scrollTop = 0;
}
function openWelcome() {
  const m = document.getElementById('welcome');
  document.getElementById('welcome-hide').checked = lsGet(WELCOME_KEY) === '1';
  m.hidden = false;
  showStep(0);
  document.getElementById('step-next').focus({preventScroll: true});
}
function closeWelcome() {
  lsSet(WELCOME_KEY, document.getElementById('welcome-hide').checked ? '1' : '0');
  document.getElementById('welcome').hidden = true;
  document.getElementById('open-help').focus();
}

// ---------- help panel: stays open beside the card while you review ----------
let GUIDE_LOADED = false;
function buildHelp() {
  // "How this works" reuses the walkthrough's steps, one after another, with headings a level down.
  document.getElementById('help-how').innerHTML = [...document.querySelectorAll('#welcome .step')].map(st => {
    const c = st.cloneNode(true);
    c.hidden = false;
    c.removeAttribute('class');
    c.querySelectorAll('[id]').forEach(x => x.removeAttribute('id'));
    c.querySelectorAll('h3').forEach(h => h.outerHTML = `<h4>${h.innerHTML}</h4>`);
    c.querySelectorAll('h2').forEach(h => h.outerHTML = `<h3>${h.innerHTML}</h3>`);
    return c.outerHTML;
  }).join('');
}
async function loadGuide() {
  if (GUIDE_LOADED) return true;
  const box = document.getElementById('help-guide');
  try {
    const doc = new DOMParser().parseFromString(await (await fetch('guide.html')).text(), 'text/html');
    const prose = doc.querySelector('.prose');
    // Demote headings a level, keeping their ids so links can land on a section.
    const demote = (from, to) => prose.querySelectorAll(from).forEach(h => h.outerHTML = `<${to}${h.id ? ` id="${h.id}"` : ''}>${h.innerHTML}</${to}>`);
    demote('h4', 'h5'); demote('h3', 'h4'); demote('h2', 'h3');
    prose.querySelectorAll('a[href]').forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
    box.innerHTML = prose.innerHTML + '<p class="small"><a href="guide.html" target="_blank" rel="noopener">Open the workflow in its own tab ↗</a></p>';
    GUIDE_LOADED = true;
    return true;
  } catch (e) {
    box.innerHTML = '<p><a href="guide.html" target="_blank" rel="noopener">Open the contributor workflow in a new tab ↗</a></p>';
  }
}
function helpTab(which) {
  ['how', 'guide'].forEach(k => {
    const on = k === which, tab = document.getElementById('tab-' + k);
    tab.setAttribute('aria-selected', on);
    tab.tabIndex = on ? 0 : -1;
    document.getElementById('help-' + k).hidden = !on;
  });
  if (which === 'guide') loadGuide();
}
// Opens the panel on a tab; with `anchor`, scrolls to that heading (else to the top), so a "Why?"
// link always lands on its answer rather than wherever the panel was left.
async function openHelp(which = 'how', anchor = '') {
  document.getElementById('help-panel').hidden = false;
  document.body.classList.add('help-open');
  document.getElementById('open-help').setAttribute('aria-expanded', 'true');
  helpTab(which);
  document.getElementById('tab-' + which).focus();
  const box = document.getElementById('help-' + which);
  if (which === 'guide') await loadGuide();
  const target = anchor && box.querySelector('#' + CSS.escape(anchor));
  if (target) {
    box.scrollTop = target.offsetTop - box.offsetTop - 8;
    target.classList.add('flash');
    setTimeout(() => target.classList.remove('flash'), 1800);
  } else box.scrollTop = 0;
}
function closeHelp() {
  document.getElementById('help-panel').hidden = true;
  document.body.classList.remove('help-open');
  document.getElementById('open-help').setAttribute('aria-expanded', 'false');
  document.getElementById('open-help').focus();
}

async function init() {
  DATA = await (await fetch('data/suggestions.json')).json();
  PAGES = DATA.pages;
  SOURCES = DATA.sources || {};
  PAGES.sort((a, b) => (pageRepl(a) && KORDER[pageKind(a)] < 2 ? 0 : 1) - (pageRepl(b) && KORDER[pageKind(b)] < 2 ? 0 : 1) || KORDER[pageKind(a)] - KORDER[pageKind(b)] || a.page.title.localeCompare(b.page.title));
  if (Store.demo) Demo.init(PAGES.slice(0, 4));
  PAGES.forEach(p => p.search = [p.page.title, ...p.items.flatMap(it => [it.original.short, it.original.citation,
    it.suggestion.rationale, ...it.occurrences.map(o => o.paragraph_plain)])].join(' ').toLowerCase());
  const rv = document.getElementById('reviewer');
  rv.value = lsGet('flora-en-edit-proto:reviewer') || '';
  rv.onchange = e => lsSet('flora-en-edit-proto:reviewer', e.target.value);
  document.getElementById('q').addEventListener('input', renderList);
  // Filters start folded away on every screen size; the button says how many are on.
  const setFilters = on => {
    document.getElementById('layout').classList.toggle('show-filters', on);
    document.getElementById('filters').hidden = !on;
    document.getElementById('toggle-filters').setAttribute('aria-expanded', on);
  };
  document.getElementById('toggle-filters').onclick = () => setFilters(document.getElementById('filters').hidden);
  document.getElementById('close-filters').onclick = () => { setFilters(false); document.getElementById('toggle-filters').focus(); };
  document.getElementById('clear-filters').onclick = clearFilters;
  if (Store.shared) document.getElementById('welcome-storage').innerHTML = '<strong>Your reviews are shared with the group.</strong> ' +
    'Under “Your reviews”, at the top right, get a reviewer ID (your initials and four digits, such as BS#1312) or sign in with the one ' +
    'you have. What you type is kept as a draft in this browser; a card counts as reviewed once you click “Save review”, and others can then audit it.';
  buildHelp();  // after the line above: the help panel copies the walkthrough
  document.getElementById('open-help').onclick = () => document.getElementById('help-panel').hidden ? openHelp() : closeHelp();
  document.getElementById('help-close').onclick = closeHelp;
  document.getElementById('tab-how').onclick = () => helpTab('how');
  document.getElementById('tab-guide').onclick = () => helpTab('guide');
  document.querySelector('.help-tabs').addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const next = document.getElementById('tab-how').getAttribute('aria-selected') === 'true' ? 'guide' : 'how';
    helpTab(next); document.getElementById('tab-' + next).focus();
  });
  document.getElementById('help-panel').addEventListener('keydown', e => { if (e.key === 'Escape') closeHelp(); });
  document.querySelectorAll('[data-open-help]').forEach(b => b.onclick = () => openHelp(b.dataset.openHelp || 'how', b.dataset.anchor || ''));
  const mine = document.getElementById('mine-menu');
  mine.addEventListener('toggle', () => mine.classList.toggle('to-left',
    mine.getBoundingClientRect().left + mine.querySelector('.mine-panel').offsetWidth > document.documentElement.clientWidth - 8));
  document.querySelectorAll('.top .menu').forEach(menu => {
    document.addEventListener('click', e => { if (menu.open && e.target.isConnected && !menu.contains(e.target)) menu.open = false; });  // a button the menu just replaced is not outside
    menu.addEventListener('keydown', e => { if (e.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); } });
  });
  document.getElementById('welcome-close').onclick = closeWelcome;
  document.getElementById('step-back').onclick = () => showStep(STEP - 1);
  document.getElementById('step-next').onclick = () => STEP === document.querySelectorAll('#welcome .step').length - 1 ? closeWelcome() : showStep(STEP + 1);
  document.getElementById('welcome').addEventListener('keydown', e => { if (e.key === 'Escape') closeWelcome(); });
  document.getElementById('export-json').onclick = () => { download('flora-en-ledger.json', JSON.stringify({exported_at: new Date().toISOString(), build: DATA.build_id,
    pages: PAGES.map(p => ledgerGet(p.page_id)).filter(Boolean)}, null, 2), 'application/json'); markExported(); };
  document.getElementById('export-csv').onclick = () => {
    const rows = ledgerRows();
    const cols = ['page_id', 'page_title', 'card_id', 'study', 'reviewed_revision_id', 'live_revision_checked', 'stale_revision', 'decision', 'decision_label', 'queue_decision', 'other_fix_done', 'card_usefulness', 'reviewer', 'updated_at', 'ai_suggested_action', 'notes'];
    const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
    download('flora-en-ledger.csv', [cols.join(',')].concat(rows.map(r => cols.map(k => q(r[k])).join(','))).join('\n'), 'text/csv');
    markExported();
  };
  document.getElementById('import-json').onchange = async e => {
    const obj = JSON.parse(await e.target.files[0].text());
    let n = 0, skipped = 0;
    for (const r of obj.pages || []) {
      const p = PAGES.find(x => x.page_id === r.page_id);
      if (!p || String(r.reviewed_revision_id) !== String(p.page.frozen_revid)) { skipped++; continue; }
      ledgerPut(r.page_id, r); n++;
      if (Store.shared) Store.queue(r.page_id, r);
    }
    document.getElementById('summary').textContent = `Imported ${n} page reviews; skipped ${skipped} for unknown pages or a different article version.` +
      (Store.shared ? (Store.me() ? ' They are shared under your reviewer ID.' : ' Sign in to share them.') : '');
    syncNow();
  };
  if (Store.shared) {
    paintIdentity();
    await Store.refresh();
    if (Store.me()) Store.flush().then(() => Store.refresh()).then(renderAll);
    setInterval(() => { if (document.visibilityState === 'visible') Store.refresh().then(renderAll); }, 60000);
  }
  buildSegments(); buildFilters(); renderList();
  const h = location.hash.slice(1);
  if (h && PAGES.some(p => p.page_id === h)) { SEGMENT = 'all'; buildSegments(); show(h, false); }
  // ?welcome=0 suppresses the first-visit screen (used for automated screenshots).
  if (lsGet(WELCOME_KEY) !== '1' && new URLSearchParams(location.search).get('welcome') !== '0') openWelcome();
}
init();
