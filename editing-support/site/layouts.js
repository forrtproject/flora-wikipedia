'use strict';
// Card layout options for review (issue #4). Loaded after app.js; ?layout=brief|tabs|desk swaps the
// per-study renderer, ?layout=current (default) keeps the existing card. Uses app.js helpers.
const LAYOUT = new URLSearchParams(location.search).get('layout') || 'current';
const LAYOUTS = {current: 'Current', brief: '1 · Decision brief', tabs: '2 · Source tabs', desk: '3 · Comparison desk'};

// ---------- shared pieces ----------
const origin = (kind, text) => `<p class="origin origin-${kind}">${text}</p>`;
const ORIGIN = {
  wiki: o => origin('wiki', `Wikipedia snapshot${o ? ` · section “${esc(o.section)}”` : ''}`),
  ai: () => origin('ai', 'AI interpretation · not yet checked by people'),
};
const roleOf = (it, doi) => doi.toLowerCase() === it.original.doi.toLowerCase() ? 'original study'
  : it.replications.some(r => r.doi.toLowerCase() === doi.toLowerCase()) ? 'replication' : 'other source';

function articleQuote(it) {
  const s = it.suggestion, d = s.draft;
  const target = d.target_text && ['replace', 'modify', 'remove', 'insert_after'].includes(d.operation) ? d.target_text : '';
  const lead = target || s.claim_sites.find(x => x.is_visible_claim)?.visible_claim_quote || '';
  const occ = it.occurrences[0];
  return `${ORIGIN.wiki(occ)}
    ${lead ? `<blockquote class="target">${withRefs(lead, it.occurrences)}</blockquote>`
      : `<p>${esc(s.claim_sites[0]?.note || 'The study only appears in a list or reference section.')}</p>`}
    <details class="fold"><summary>Surrounding text and other places this study is cited (${it.occurrences.length})</summary>
      ${it.occurrences.map(o => `<h6>Section “${esc(o.section)}”${o.in_comment ? ' (hidden comment)' : ''}</h6>
        <div class="passage">${highlight(o.paragraph_plain, s.claim_sites.map(x => x.visible_claim_quote))}</div>`).join('')}
    </details>`;
}

// The AI's reason in one place: gist, plus disagreement and (for no change) why the replication does not bear on it.
function aiReason(it) {
  const s = it.suggestion, k = itemKind(it), [label, cls] = KIND[k];
  return `${ORIGIN.ai()}<div class="reason">
    <p><strong>${esc(ACTION[s.proposed_action])}</strong> <span class="badge ${cls}">${label}</span>${it.adds_replication ? ' <span class="badge repl">Adds a replication</span>' : ''}</p>
    <p>${esc(it.gist || s.rationale)}</p>
    ${it.two_run && !it.two_run.agree ? `<p class="twoRun"><strong>A second AI assessment disagrees:</strong> it suggests “${esc(ACTION[it.two_run.other.action])}”. ${esc(it.two_run.other.rationale)}</p>` : ''}
  </div>`;
}

// Passages from one paper: AI statement first, then the verbatim quote, clearly attributed.
function passagesFor(it, doi) {
  const s = it.suggestion, lc = doi.toLowerCase();
  const ver = (s.verifications || []).filter(v => (v.source || '').toLowerCase() === lc && v.quote);
  const ex = s.evidence_used.filter(e => e.doi.toLowerCase() === lc && e.excerpt);
  const items = [...ex.map(e => ({ai: e.what_it_supports, quote: e.excerpt, flag: ''})),
    ...ver.map(v => ({ai: v.claim, quote: v.quote, flag: v.result !== 'confirmed' ? RESULT[v.result] : null}))];
  const seen = new Set();
  return items.filter(x => !seen.has(x.quote) && seen.add(x.quote)).map(x => `<li>
    <blockquote class="excerpt"><span class="who">Quote from ${srcLink(doi)}</span><br>“${esc(x.quote)}”</blockquote>
    <p class="ai-note"><span class="who">AI:</span> ${x.flag ? `<span class="badge ${x.flag[1]}">${x.flag[0]}</span> ` : ''}${esc(x.ai)}</p></li>`);
}

// What / Where / Cite, then the points grouped by the paper they come from, each with that paper's passages.
function changePlan(it) {
  const s = it.suggestion, d = s.draft, k = itemKind(it);
  const points = s.content_points.filter(x => !/^needs/i.test(x.source));
  if (k === 'none' || k === 'other' || !['provided', 'conditional'].includes(d.status)) {
    return `<h4 id="edit-${it.card_id}">Why leave this passage as it is?</h4>
      ${LAYOUT === 'desk' ? '' : `<p><span class="who">AI: does the replication test this sentence?</span> ${esc(s.specific_study_match.note)}</p>`}
      ${points.length ? `<details class="fold"><summary>Points worth knowing (${points.length})</summary>${pointsBySource(it, points)}</details>` : ''}`;
  }
  return `<h4 id="edit-${it.card_id}">Proposed change</h4>${pointerBlock(it)}
    ${points.length ? `<h5 class="sub-h">Points to cover</h5>${pointsBySource(it, points)}` : ''}`;
}
function pointsBySource(it, points) {
  const groups = {};
  points.forEach(p => (groups[p.source.toLowerCase()] ||= []).push(p));
  return Object.entries(groups).map(([doi, ps]) => {
    const pass = passagesFor(it, doi);
    return `<div class="pgroup"><p class="pgroup-h">From ${srcLink(doi)} <span class="small">(${roleOf(it, doi)})</span> ${lvlBadge(ps[0].evidence_level, true)}</p>
      <ul class="tight">${ps.map(p => `<li>${esc(p.point)}</li>`).join('')}</ul>
      ${pass.length ? `<details class="fold"><summary>Read the supporting passages (${pass.length})</summary><ul class="verifs">${pass.join('')}</ul></details>` : ''}</div>`;
  }).join('');
}

function decideBlock(it) {
  const s = it.suggestion, q = s.required_checks || [];
  if (!q.length && !s.alternatives.length && !s.uncertainties.length) return '';
  return `<div class="decide"><h4 id="call-${it.card_id}">Decide before acting</h4>
    ${q.length ? `<ul class="tight">${q.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p class="small">No open questions about this edit.</p>'}
    ${s.uncertainties.length ? `<details class="fold"><summary>What remains uncertain (${s.uncertainties.length})</summary><ul class="tight">${s.uncertainties.map(u => `<li>${esc(u)}</li>`).join('')}</ul></details>` : ''}
    ${s.alternatives.length ? `<details class="fold"><summary>Other ways to handle this (${s.alternatives.length})</summary><ul class="tight">${s.alternatives.map(a => `<li>${esc(a.action)} <span class="small">${esc(a.when)}</span></li>`).join('')}</ul></details>` : ''}</div>`;
}

function paperCard(it, s, role, extra = '') {
  const pass = passagesFor(it, s.doi);
  return `<div class="paper"><p class="paper-role">${role}</p><p>${esc(s.citation)}<br>${doiLink(s.doi)}</p>
    <p class="small">What the AI read: ${lvlBadge(s.evidence_level)}${extra}</p>
    ${pass.length ? `<details class="fold"><summary>Passages quoted from this paper (${pass.length})</summary><ul class="verifs">${pass.join('')}</ul></details>` : ''}</div>`;
}
const replExtra = r => r.doi_detected_on_page ? ' · already cited in the article' : ' · not cited in the article yet';
function reviewsFold(it) {
  const revs = it.reviews_checked || [];
  if (!revs.length) return '';
  const n = revs.filter(r => r.mentions).length;
  return `<details class="fold"><summary>Review articles searched for the replication: ${n} of ${revs.length} mention it</summary><ul class="tight">${revs.map(r => `<li>${esc(r.title)} · ${srcLink(r.doi)} ${lvlBadge(r.evidence_level, true)} · ${!r.mentions ? 'no mention found'
    : r.reference_list_only ? 'in its reference list only' : '<strong>mentions it</strong>'}${r.mentions && r.snippets?.length ? `<blockquote class="excerpt"><span class="who">Quote from the review</span><br>“${esc(r.snippets[0])}”</blockquote>` : ''}</li>`).join('')}</ul></details>`;
}
function libraryFold(it, open = false) {
  return `<details class="fold" ${open ? 'open' : ''}><summary>Papers and passages</summary><div class="papers-grid">
    ${paperCard(it, it.original, 'Original study')}${it.replications.map(r => paperCard(it, r, 'Replication', replExtra(r))).join('')}</div></details>`;
}
function methodFold(it) {
  const s = it.suggestion, v = it.validation;
  return `<details class="fold"><summary>How this card was prepared</summary><dl class="kv">
    <dt>AI's full assessment</dt><dd>${esc(s.assessment)}</dd>
    <dt>Does the replication test this claim? (AI)</dt><dd>${esc(s.specific_study_match.note)}</dd>
    <dt>Does the article already cover it? (AI)</dt><dd>${esc(s.existing_acknowledgement.note)}</dd>
    <dt>Automatic checks</dt><dd>${v.errors.length ? `<span class="bad">${esc(v.errors.join('; '))}</span>` : 'Every quote was found word for word in the saved paper or article. This does not show that the AI read them correctly.'}</dd>
    <dt>Status</dt><dd>Prepared with AI${it.provenance.finished_at ? ' on ' + esc(it.provenance.finished_at.slice(0, 10)) : ''}; not yet checked by people.</dd></dl></details>`;
}
const studyHead = (it, i, n) => `${n > 1 ? `Study ${i + 1} of ${n}: ` : ''}${it.original.short}`;
const papersLine = it => `<p class="papers small"><span class="who">Papers:</span> original ${srcLink(it.original.doi)}${it.replications.map(r => ` · replication ${srcLink(r.doi)}`).join('')}</p>`;
const wrap = (it, i, n, body) => {
  const k = itemKind(it);
  return `<section class="item lay-${LAYOUT}" id="item-${it.card_id}" aria-labelledby="h-${it.card_id}">
    <details ${k !== 'none' || n === 1 || it.suggestion.alternatives.length ? 'open' : ''}><summary><h3 class="item-head" id="h-${it.card_id}">${esc(studyHead(it, i, n))}</h3></summary>${body}</details></section>`;
};

// ---------- layout 1: decision brief ----------
function itemBrief(it, i, n) {
  return wrap(it, i, n, `${papersLine(it)}${articleQuote(it)}${aiReason(it)}${changePlan(it)}${decideBlock(it)}
    <div class="more-h">More detail</div>${libraryFold(it)}${reviewsFold(it)}${methodFold(it)}`);
}

// ---------- layout 2: source-first tabs ----------
function itemTabs(it, i, n) {
  const id = it.card_id, tab = (k, label, on) => `<button type="button" role="tab" class="ltab" data-tabs="${id}" data-tab="${k}" aria-selected="${on}">${label}</button>`;
  const q = (it.suggestion.required_checks || []).length;
  return wrap(it, i, n, `${papersLine(it)}
    <p class="small task">Compare how the article uses the study with what the papers found, then look at the change plan.</p>
    <div class="ltabs" role="tablist">${tab('papers', 'Papers', true)}${tab('article', 'Article', false)}${tab('plan', `Change plan${q ? ` <span class="n">${q} question${q > 1 ? 's' : ''}</span>` : ''}`, false)}</div>
    <div class="lpanel" data-panel="${id}:papers"><div class="papers-grid">${paperCard(it, it.original, 'Original study')}${it.replications.map(r => paperCard(it, r, 'Replication', replExtra(r))).join('')}</div>
      ${reviewsFold(it)}${methodFold(it)}<p><button type="button" class="linklike" data-goto="${id}:article">Next: the article →</button></p></div>
    <div class="lpanel" data-panel="${id}:article" hidden>${articleQuote(it)}
      ${ORIGIN.ai()}<p>${esc(it.suggestion.existing_acknowledgement.note)}</p>
      <p><button type="button" class="linklike" data-goto="${id}:plan">Next: the change plan →</button></p></div>
    <div class="lpanel" data-panel="${id}:plan" hidden>${articleQuote(it)}${aiReason(it)}${changePlan(it)}${decideBlock(it)}</div>`);
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-tab], [data-goto]');
  if (!t) return;
  const [id, k] = t.dataset.goto ? t.dataset.goto.split(':') : [t.dataset.tabs, t.dataset.tab];
  document.querySelectorAll(`[data-tabs="${id}"]`).forEach(b => b.setAttribute('aria-selected', b.dataset.tab === k));
  document.querySelectorAll(`[data-panel^="${id}:"]`).forEach(p => p.hidden = p.dataset.panel !== `${id}:${k}`);
  if (t.dataset.goto) document.getElementById(`item-${id}`).scrollIntoView({block: 'start'});
});

// ---------- layout 3: comparison desk ----------
function itemDesk(it, i, n) {
  const s = it.suggestion;
  const best = doi => s.evidence_used.find(e => e.doi.toLowerCase() === doi.toLowerCase() && e.excerpt);
  const ev = (src, role) => {
    const e = best(src.doi);
    return `<div class="desk-src"><p class="paper-role">${role}: ${srcLink(src.doi)} ${lvlBadge(src.evidence_level, true)}</p>
      ${e ? `<blockquote class="excerpt"><span class="who">Quote from ${srcLink(src.doi)}</span><br>“${esc(e.excerpt)}”</blockquote>` : '<p class="small">No passage quoted from this paper.</p>'}</div>`;
  };
  return wrap(it, i, n, `${papersLine(it)}
    <div class="desk"><div class="desk-l">${articleQuote(it)}</div>
      <div class="desk-r">${origin('paper', 'Evidence from the papers')}${ev(it.original, 'Original')}${it.replications.map(r => ev(r, 'Replication')).join('')}</div></div>
    <div class="desk-ai">${aiReason(it)}<p class="small"><strong>Does the replication test this sentence? (AI)</strong> ${esc(s.specific_study_match.note)}</p></div>
    ${changePlan(it)}${decideBlock(it)}
    <div class="more-h">More detail</div>${libraryFold(it)}${reviewsFold(it)}${methodFold(it)}`);
}

// ---------- wiring ----------
if (LAYOUT !== 'current') {
  const render = {brief: itemBrief, tabs: itemTabs, desk: itemDesk}[LAYOUT];
  // app.js calls itemSection(it, i, n); replace it for the chosen option. The one-study overview line is dropped.
  itemSection = render;  // eslint-disable-line no-global-assign
  const baseOverview = overview;
  overview = p => p.items.length < 2 ? '' : baseOverview(p);  // eslint-disable-line no-global-assign
  document.body.classList.add('layout-' + LAYOUT);
}
// A switcher so reviewers can compare the options on the same card.
document.addEventListener('DOMContentLoaded', () => {
  const bar = document.createElement('nav');
  bar.className = 'layout-switch';
  bar.setAttribute('aria-label', 'Card layout options');
  bar.innerHTML = '<span>Card layout:</span>' + Object.entries(LAYOUTS).map(([k, l]) => `<a href="?layout=${k}&welcome=0${location.hash}" ${k === LAYOUT ? 'aria-current="true"' : ''}>${l}</a>`).join('');
  bar.addEventListener('click', e => { const a = e.target.closest('a'); if (a) { e.preventDefault(); location.href = a.getAttribute('href').replace(/#.*/, '') + location.hash; } });
  document.body.prepend(bar);
});
