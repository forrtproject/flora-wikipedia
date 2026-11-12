'use strict';
// Card layouts (issue #4). Loaded after app.js. The default is the group's combined design (?layout=combo);
// ?layout=current|brief|tabs|desk keep the earlier options for comparison. Uses app.js helpers.
const LAYOUT = new URLSearchParams(location.search).get('layout') || 'combo';
const LAYOUTS = {combo: 'Combined (group design, default)', current: 'First version', brief: 'Decision brief', tabs: 'Source tabs', desk: 'Comparison desk'};

// ---------- shared pieces ----------
// "section" or "subsection" (with its parent), linked to that heading in the snapshot (#13).
const anchor = s => encodeURIComponent(s.replace(/\[\[(?:[^\]|]*\|)?([^\]]*)\]\]/g, '$1').replace(/'{2,}/g, '').trim().replace(/ /g, '_'))
  .replace(/%3A/g, ':').replace(/%2C/g, ',');
function sectionLabel(o, page, link = true) {
  if (o.section === '(lead)') return 'the lead (opening paragraphs)';
  const plain = s => s.replace(/<[^>]+>/g, '').trim(), sec = plain(o.section);
  const sub = (o.section_level || 2) > 2, name = `“${esc(sec)}”`;
  const named = link && page ? `<a href="${esc(page.frozen_url)}#${anchor(sec)}" target="_blank" rel="noopener" title="Open this ${sub ? 'subsection' : 'section'} in the snapshot">${name}</a>` : name;
  return `${sub ? 'subsection' : 'section'} ${named}${sub && o.section_parent ? ` of “${esc(plain(o.section_parent))}”` : ''}`;
}
const origin = (kind, text) => `<p class="origin origin-${kind}"><span>${text}</span></p>`;
const ORIGIN = {
  wiki: o => origin('wiki', `Wikipedia snapshot${o ? ` · ${sectionLabel(o)}` : ''}`),
  ai: () => origin('ai', 'AI interpretation · not yet checked by people'),
};
const roleOf = (it, doi) => doi.toLowerCase() === it.original.doi.toLowerCase() ? 'original study'
  : it.replications.some(r => r.doi.toLowerCase() === doi.toLowerCase()) ? 'replication' : 'other source';

function articleQuote(it) {
  const s = it.suggestion, d = s.draft;
  const target = d.target_text && ['replace', 'modify', 'remove', 'insert_after'].includes(d.operation) ? d.target_text : '';
  const lead = target || s.claim_sites.find(x => x.is_visible_claim)?.visible_claim_quote || '';
  const plain = t => normT(t.replace(/\[(FOCAL REF|PAIRED REF|ref):[^\]]*\]/g, ''));
  const occ = lead ? it.occurrences.find(o => plain(o.paragraph_plain).includes(normT(lead))) : null;
  const quotes = s.claim_sites.map(x => x.visible_claim_quote);
  return `${origin('wiki', `Wikipedia snapshot ${esc(it.page?.frozen_timestamp?.slice(0, 10) || '')}${occ ? ` · ${sectionLabel(occ, it.page)}` : lead ? ' · section not matched' : ''}`)}
    ${lead ? `<blockquote class="target">${withRefs(lead, it.occurrences)}</blockquote>`
      : `<p>${esc(s.claim_sites[0]?.note || 'The study only appears in a list or reference section.')}</p>`}
    <details class="fold"><summary>Surrounding text and other places this study is cited (${it.occurrences.length})</summary>
      <p class="small"><mark class="focal">[this study]</mark> marks its citation, <mark class="paired">[replication]</mark> a replication's; <mark class="claim">underlined</mark> text is what the citation supports. Rendering is approximate; check the live page.</p>
      ${it.occurrences.map(o => `<h6>${sectionLabel(o, it.page).replace(/^./, c => c.toUpperCase())}${o.in_comment ? ' (hidden comment, not visible to readers)' : ''}</h6>
        <div class="passage">${highlight(o.paragraph_plain, quotes)}</div>
        <details><summary>Whole section</summary><div class="passage">${highlight(o.section_plain, quotes)}</div></details>`).join('')}
    </details>`;
}

// The AI's reason in one place: gist, plus disagreement and (for no change) why the replication does not bear on it.
function aiReason(it) {
  const s = it.suggestion, k = itemKind(it), [label, cls] = KIND[k];
  return `${ORIGIN.ai()}<div class="reason">
    <p><strong>${esc(ACTION[s.proposed_action])}</strong>${label === ACTION[s.proposed_action] ? '' : ` <span class="badge ${cls}">${label}</span>`}${it.adds_replication ? ' <span class="badge repl">Adds a replication</span>' : ''}</p>
    <p>${esc(it.gist || s.rationale)}</p>
    ${it.rationale_rest ? `<details class="fold"><summary>More of the AI's reasoning</summary><p>${esc(it.rationale_rest)}</p></details>` : ''}
    ${it.two_run && !it.two_run.agree ? `<p class="twoRun"><strong>A second AI assessment disagrees:</strong> it suggests “${esc(ACTION[it.two_run.other.action])}”. ${esc(it.two_run.other.rationale)}</p>` : ''}
  </div>`;
}

// Passages from one paper: AI statement first, then the verbatim quote, clearly attributed.
function passagesFor(it, doi) {
  const s = it.suggestion, lc = doi.toLowerCase();
  const ver = (s.verifications || []).filter(v => (v.source || '').toLowerCase() === lc && v.quote);
  const ex = s.evidence_used.filter(e => e.doi.toLowerCase() === lc && e.excerpt);
  const byQuote = new Map();
  [...ver.map(v => ({ai: v.claim, quote: v.quote, flag: v.result !== 'confirmed' ? RESULT[v.result] : null, lvl: v.evidence_level})),
   ...ex.map(e => ({ai: e.what_it_supports, quote: e.excerpt, flag: null, lvl: e.evidence_level}))]
    .forEach(x => { const q = byQuote.get(x.quote); q ? q.notes.push(x) : byQuote.set(x.quote, {quote: x.quote, lvl: x.lvl, notes: [x]}); });
  return [...byQuote.values()].map(x => `<li>${quoteBox(it, doi, x.quote, x.lvl, true)}
    ${x.notes.map(n => `<p class="ai-note"><span class="who">AI:</span> ${n.flag ? `<span class="badge ${n.flag[1]}">${n.flag[0]}</span> ` : ''}${esc(n.ai)}</p>`).join('')}</li>`);
}

// With `bare`, the heading above already names the paper and what was read, so the quote stands alone (#15).
const quoteBox = (it, doi, q, lvl, bare) => `<blockquote class="excerpt">${bare ? '' : `<span class="who">Quote from ${srcLink(doi)} · ${roleOf(it, doi)} · ${esc(LEVEL[lvl] || 'read')}${accessLink(doi, true) ? ` · ${accessLink(doi, true)}` : ''}</span><br>`}“${esc(q)}”</blockquote>`;

// Every AI check, including those without a quote and those on other sources: nothing is lost to deduplication.
function checksFold(it) {
  const v = it.suggestion.verifications || [];
  if (!v.length) return '';
  return `<details class="fold"><summary>All AI checks of facts against the papers (${v.length})</summary>
    <p class="small">Each check is an AI statement with the passage it relied on. The quote was found word for word in the saved paper; whether it supports the statement is the AI's judgement.</p>
    <ul class="verifs">${v.map(x => `<li><p class="ai-note"><span class="who">AI:</span> <span class="badge ${RESULT[x.result][1]}">${x.result === 'confirmed' ? 'AI: supported by this passage' : RESULT[x.result][0]}</span> ${esc(x.claim)}</p>
      ${x.quote ? quoteBox(it, x.source, x.quote, x.evidence_level) : `<p class="small">No passage: ${srcLink(x.source) || 'source'} ${lvlBadge(x.evidence_level)}</p>`}</li>`).join('')}</ul></details>`;
}

// What / Where / Cite, then the points grouped by the paper they come from, each with that paper's passages.
function changePlan(it) {
  const s = it.suggestion, d = s.draft, k = itemKind(it);
  const points = s.content_points.filter(x => !/^needs/i.test(x.source));
  if (s.proposed_action === 'defer' || (EDIT_ACTIONS.has(s.proposed_action) && !['provided', 'conditional'].includes(d.status))) {
    return `<h4 id="edit-${it.card_id}">No change plan yet</h4><p>${esc(s.rationale)}</p>`;
  }
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
    return `<div class="pgroup"><p class="pgroup-h"><span class="who">AI research points based on</span> ${srcLink(doi)} <span class="small">(${roleOf(it, doi)})</span> ${lvlBadge(ps[0].evidence_level)}</p>
      <ul class="tight">${ps.map(p => `<li>${esc(p.point)}</li>`).join('')}</ul>
      ${pass.length ? `<details class="fold"><summary>Inspect passages quoted from this paper (${pass.length}; not matched to individual points)</summary><ul class="verifs">${pass.join('')}</ul></details>` : ''}</div>`;
  }).join('');
}

function decideBlock(it) {
  const s = it.suggestion, q = s.required_checks || [];
  if (!q.length && !s.alternatives.length && !s.uncertainties.length) return '';
  return `<div class="decide"><h4 id="call-${it.card_id}">${q.length ? 'Decide before acting' : 'Open points'}</h4>
    ${q.length ? `<ul class="tight">${q.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    ${s.uncertainties.length ? `<details class="fold"><summary>What remains uncertain (${s.uncertainties.length})</summary><ul class="tight">${s.uncertainties.map(u => `<li>${esc(u)}</li>`).join('')}</ul></details>` : ''}
    ${s.alternatives.length ? `<details class="fold"><summary>Other ways to handle this (${s.alternatives.length})</summary><ul class="tight">${s.alternatives.map(a => `<li>${esc(a.action)} <span class="small">${esc(a.when)}</span></li>`).join('')}</ul></details>` : ''}</div>`;
}

function paperCard(it, s, role, extra = '') {
  const pass = passagesFor(it, s.doi);
  return `<div class="paper"><p class="paper-role">${role}</p><p>${esc(s.citation)}<br>${doiLink(s.doi)}</p>
    <p class="small">What the AI read: ${lvlBadge(s.evidence_level)}${extra}${accessLink(s.doi) ? ` · ${accessLink(s.doi)}` : ''}</p>
    ${pass.length ? `<details class="fold"><summary>Passages quoted from this paper (${pass.length})</summary><ul class="verifs">${pass.join('')}</ul></details>` : ''}</div>`;
}
const replExtra = r => r.doi_detected_on_page ? ' · already cited in the Wikipedia article' : ' · not cited in the Wikipedia article yet';
function reviewsFold(it) {
  const revs = it.reviews_checked || [];
  if (!revs.length) return '';
  const n = revs.filter(r => r.mentions).length;
  return `<details class="fold"><summary>AI search of ${revs.length} review articles for the replication: ${n} cite it</summary>
    <p class="small">An automatic search of these reviews only, for the replication's first author and year. “No mention found” does not mean no review discusses it.</p><ul class="tight">${revs.map(r => `<li>${esc(r.title)} · ${srcLink(r.doi)} ${lvlBadge(r.evidence_level, true)} · ${!r.mentions ? 'no mention found'
    : r.reference_list_only ? 'cites it in its reference list only (no passage found)' : '<strong>discusses it in the text</strong>'}${r.mentions && r.snippets?.length ? `<blockquote class="excerpt"><span class="who">Quote from the review</span><br>“${esc(r.snippets[0])}”</blockquote>` : ''}</li>`).join('')}</ul></details>`;
}
const otherSources = it => {
  const known = [it.original.doi, ...it.replications.map(r => r.doi)].map(x => x.toLowerCase());
  return [...new Set(it.suggestion.evidence_used.map(e => e.doi.toLowerCase()).filter(d => !known.includes(d)))];
};
function papersGrid(it) {
  return `<div class="papers-grid">${paperCard(it, it.original, 'Original study')}${it.replications.map(r => paperCard(it, r, 'Replication', replExtra(r))).join('')}
    ${otherSources(it).map(d => paperCard(it, {doi: d, citation: SOURCES[d]?.citation || d, evidence_level: it.suggestion.evidence_used.find(e => e.doi.toLowerCase() === d).evidence_level}, 'Other source')).join('')}</div>`;
}
function libraryFold(it, open = false) {
  return `<details class="fold" ${open ? 'open' : ''}><summary>Papers and passages</summary>${papersGrid(it)}</details>`;
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
const studyHead = (it, i, n) => `${n > 1 ? `Publication ${i + 1} of ${n}: ` : ''}${it.original.short}`;
const papersLine = it => `<p class="papers small"><span class="who">Papers:</span> original ${srcLink(it.original.doi)}${it.replications.map(r => ` · replication ${srcLink(r.doi)}`).join('')}</p>`;
const wrap = (it, i, n, body) => {
  return `<section class="item lay-${LAYOUT}" id="item-${it.card_id}" aria-labelledby="h-${it.card_id}">
    <details ${n === 1 || i === 0 ? 'open' : ''}><summary><h3 class="item-head" id="h-${it.card_id}">${esc(studyHead(it, i, n))}</h3></summary>${body}</details></section>`;
};

// ---------- layout 1: decision brief ----------
function itemBrief(it, i, n) {
  return wrap(it, i, n, `${papersLine(it)}${articleQuote(it)}${aiReason(it)}${changePlan(it)}${decideBlock(it)}
    <div class="more-h">More detail</div>${libraryFold(it)}${checksFold(it)}${reviewsFold(it)}${methodFold(it)}`);
}

// ---------- layout 2: source-first tabs ----------
function itemTabs(it, i, n) {
  const id = it.card_id, sg = it.suggestion, k = itemKind(it), [label, cls] = KIND[k];
  const noChange = k === 'none' || k === 'other';
  const q = (sg.required_checks || []).length;
  const tab = (t, text, on) => `<button type="button" role="tab" class="ltab" id="tab-${id}-${t}" aria-controls="panel-${id}-${t}" data-tabs="${id}" data-tab="${t}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${text}</button>`;
  const panel = (t, body, on) => `<div class="lpanel" role="tabpanel" id="panel-${id}-${t}" aria-labelledby="tab-${id}-${t}" data-panel="${id}:${t}" ${on ? '' : 'hidden'}>${body}</div>`;
  return wrap(it, i, n, `${papersLine(it)}
    <p class="tabs-rec">${origin('ai', 'AI recommendation · not yet checked by people')}<strong>${esc(ACTION[sg.proposed_action])}</strong>${label === ACTION[sg.proposed_action] ? '' : ` <span class="badge ${cls}">${label}</span>`}</p>
    <p class="small task">Compare how the article uses the study with what the papers found, then read the AI's ${noChange ? 'reasons' : 'change plan'}.</p>
    <div class="ltabs" role="tablist" aria-label="Study material">${tab('papers', 'Papers', true)}${tab('article', 'Article', false)}${tab('plan', `${noChange ? 'Why no change?' : 'Change plan'}${q ? ` <span class="n">${q} question${q > 1 ? 's' : ''}</span>` : ''}`, false)}</div>
    ${panel('papers', `${papersGrid(it)}${checksFold(it)}${reviewsFold(it)}${methodFold(it)}<p><button type="button" class="linklike" data-goto="${id}:article">Next: the article →</button></p>`, true)}
    ${panel('article', `${articleQuote(it)}${ORIGIN.ai()}<p><strong>Does the article already cover the replication?</strong> ${esc(sg.existing_acknowledgement.note)}</p>
      <p><button type="button" class="linklike" data-goto="${id}:plan">Next: ${noChange ? 'why no change' : 'the change plan'} →</button></p>`, false)}
    ${panel('plan', `${articleQuote(it)}${aiReason(it)}${changePlan(it)}${decideBlock(it)}`, false)}`);
}
function selectTab(id, t, focus) {
  document.querySelectorAll(`[data-tabs="${id}"]`).forEach(b => { const on = b.dataset.tab === t; b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
  document.querySelectorAll(`[data-panel^="${id}:"]`).forEach(p => p.hidden = p.dataset.panel !== `${id}:${t}`);
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-tab], [data-goto]');
  if (t) {
    const [id, k] = t.dataset.goto ? t.dataset.goto.split(':') : [t.dataset.tabs, t.dataset.tab];
    selectTab(id, k, !!t.dataset.goto);
    return;
  }
  // Jump links into a hidden panel (card bar "Suggested edit" / "Your call"): show the panel first.
  const a = e.target.closest('[data-to]');
  const target = a && document.getElementById(a.dataset.to);
  const p = target?.closest('[data-panel]');
  if (p?.hidden) { const [id, k] = p.dataset.panel.split(':'); selectTab(id, k); }
}, true);
document.addEventListener('keydown', e => {
  const b = e.target.closest?.('.ltab');
  if (!b || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
  const tabs = [...document.querySelectorAll(`[data-tabs="${b.dataset.tabs}"]`)], i = tabs.indexOf(b);
  selectTab(b.dataset.tabs, tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length].dataset.tab, true);
});

// "ORIGINAL: BAIRD ET AL. (2012) · Full text read · Free copy ↗": one line names the paper, what was read and where to check it.
const srcHead = (src, role, lvl) => `<p class="paper-role">${role}: ${srcLink(src.doi)} <span class="src-meta">· ${esc(LEVEL[lvl || src.evidence_level] || 'read')}${accessLink(src.doi, true) ? ` · ${accessLink(src.doi, true)}` : ''}</span></p>`;

// ---------- layout 3: comparison desk ----------
// The right column shows the first passage quoted from each paper. It was not chosen for this comparison,
// so it says so, and the AI's view of whether the replication tests the sentence sits above it.
function itemDesk(it, i, n) {
  const s = it.suggestion;
  const first = doi => s.evidence_used.find(e => e.doi.toLowerCase() === doi.toLowerCase() && e.excerpt);
  const ev = (src, role) => {
    const e = first(src.doi);
    return `<div class="desk-src">${srcHead(src, role, e?.evidence_level)}
      ${e ? quoteBox(it, src.doi, e.excerpt, e.evidence_level, true) : '<p class="small">No passage quoted from this paper.</p>'}</div>`;
  };
  return wrap(it, i, n, `${papersLine(it)}
    <div class="desk"><div class="desk-l">${articleQuote(it)}</div>
      <div class="desk-r">${origin('paper', 'Evidence from the papers')}
        <p class="ai-note desk-match"><span class="who">AI: does the replication test this sentence?</span> ${esc(s.specific_study_match.note)}</p>
        ${ev(it.original, 'Original')}${it.replications.map(r => ev(r, 'Replication')).join('')}
        <p class="small">First passage quoted from each paper, not selected for this comparison; all passages are under “Papers and passages”.</p></div></div>
    <div class="desk-ai">${aiReason(it)}</div>
    ${changePlan(it)}${decideBlock(it)}
    <div class="more-h">More detail</div>${libraryFold(it)}${checksFold(it)}${reviewsFold(it)}${methodFold(it)}`);
}

// ---------- layout 4: combined (group design, issue #4) ----------
// Source tabs with the comparison desk inside: Comparison | Papers | Details & AI review in one box, then the AI's
// interpretation with the proposed change (What / Where / Cite), then how the card was prepared.
function quotesFor(it, doi) {  // the same passages as passagesFor, grouped by quote, keeping the AI notes apart
  const s = it.suggestion, lc = doi.toLowerCase(), byQuote = new Map();
  [...(s.verifications || []).filter(v => (v.source || '').toLowerCase() === lc && v.quote)
    .map(v => ({ai: v.claim, quote: v.quote, flag: v.result !== 'confirmed' ? RESULT[v.result] : null})),
   ...s.evidence_used.filter(e => e.doi.toLowerCase() === lc && e.excerpt).map(e => ({ai: e.what_it_supports, quote: e.excerpt, flag: null}))]
    .forEach(x => { const q = byQuote.get(x.quote); q ? q.notes.push(x) : byQuote.set(x.quote, {quote: x.quote, notes: [x]}); });
  return [...byQuote.values()];
}
const comboSources = it => [[it.original, 'Original study'], ...it.replications.map(r => [r, 'Replication']),
  ...otherSources(it).map(d => [{doi: d, citation: SOURCES[d]?.citation || d, evidence_level: it.suggestion.evidence_used.find(e => e.doi.toLowerCase() === d).evidence_level}, 'Other source'])];
function comboPapers(it) {  // full-width tiles; quotes only, no AI interpretation
  return comboSources(it).map(([src, role]) => {
    const qs = quotesFor(it, src.doi);
    return `<div class="paper paper-wide"><p class="paper-role">${role}</p><p>${esc(src.citation)}<br>${doiLink(src.doi)}${accessLink(src.doi) ? ` · ${accessLink(src.doi)}` : ''}</p>
      <p class="small">What the AI read: ${lvlBadge(src.evidence_level)}${role === 'Replication' ? replExtra(src) : ''}</p>
      ${qs.length ? `<details class="fold"><summary>Passages quoted from this paper (${qs.length})</summary>${qs.map(q => quoteBox(it, src.doi, q.quote, src.evidence_level, true)).join('')}</details>`
        : '<p class="small">No passage quoted from this paper.</p>'}</div>`;
  }).join('');
}
function comboDetails(it) {
  const s = it.suggestion, points = s.content_points.filter(x => !/^needs/i.test(x.source));
  const pts = points.length ? `<h4>Points to cover</h4>${pointsBySourcePlain(it, points)}` : '';
  const split = comboSources(it).map(([src, role]) => {
    const qs = quotesFor(it, src.doi);
    if (!qs.length) return '';
    return `<div class="split-src">${srcHead(src, role.replace(' study', ''))}
      <div class="split-h" aria-hidden="true"><span>AI interpretation</span><span>Quote from the paper</span></div>
      ${qs.map(q => `<div class="split-row"><div class="split-ai">${q.notes.map(n => `<p>${n.flag ? `<span class="badge ${n.flag[1]}">${n.flag[0]}</span> ` : ''}${esc(n.ai)}</p>`).join('')}</div>
        <div class="split-q">${quoteBox(it, src.doi, q.quote, src.evidence_level, true)}</div></div>`).join('')}</div>`;
  }).join('');
  const noQuote = (s.verifications || []).filter(v => !v.quote);
  return `${pts}<h4>Checking the AI's reading of the papers</h4>
    <p class="small">Each row pairs an AI statement with the passage it relied on. The quote was found word for word in the saved paper; whether it supports the statement is the AI's judgement.</p>
    ${split || '<p class="small">No passages were quoted.</p>'}
    ${noQuote.length ? `<details class="fold"><summary>AI checks without a quoted passage (${noQuote.length})</summary><ul class="verifs">${noQuote.map(x => `<li><span class="badge ${RESULT[x.result][1]}">${RESULT[x.result][0]}</span> ${esc(x.claim)} <span class="small">${srcLink(x.source)} ${lvlBadge(x.evidence_level)}</span></li>`).join('')}</ul></details>` : ''}
    ${reviewsFold(it)}`;
}
function pointsBySourcePlain(it, points) {
  const groups = {};
  points.forEach(p => (groups[p.source.toLowerCase()] ||= []).push(p));
  return Object.entries(groups).map(([doi, ps]) => `<div class="pgroup"><p class="pgroup-h"><span class="who">AI research points based on</span> ${srcLink(doi)} <span class="small">(${roleOf(it, doi)})</span> ${lvlBadge(ps[0].evidence_level)}</p>
    <ul class="tight">${ps.map(p => `<li>${esc(p.point)}</li>`).join('')}</ul></div>`).join('');
}
function comboPlan(it) {  // the AI interpretation box: reason, then What / Where / Cite or why no change
  const s = it.suggestion, d = s.draft, k = itemKind(it), [label, cls] = KIND[k];
  const isPlan = s.proposed_action !== 'defer' && ['provided', 'conditional'].includes(d.status) && k !== 'none' && k !== 'other';
  return `${ORIGIN.ai()}<div class="reason" id="edit-${it.card_id}">
    <p><strong>${esc(ACTION[s.proposed_action])}</strong>${label === ACTION[s.proposed_action] ? '' : ` <span class="badge ${cls}">${label}</span>`}${it.adds_replication ? ' <span class="badge repl">Adds a replication</span>' : ''}</p>
    <p>${esc(it.gist || s.rationale)}</p>
    ${isPlan ? pointerBlock(it) : `<p><span class="who">Does the replication test this sentence?</span> ${esc(s.specific_study_match.note)}</p>
      <p><span class="who">Does the Wikipedia article already cover it?</span> ${esc(s.existing_acknowledgement.note)}</p>`}
    ${it.rationale_rest ? `<details class="fold"><summary>More of the AI's reasoning</summary><p>${esc(it.rationale_rest)}</p></details>` : ''}
    ${it.two_run && !it.two_run.agree ? `<p class="twoRun"><strong>A second AI assessment disagrees:</strong> it suggests “${esc(ACTION[it.two_run.other.action])}”. ${esc(it.two_run.other.rationale)}</p>` : ''}
    ${isPlan && s.content_points.length ? `<p class="small">The points to cover are under “Details &amp; AI review” above.</p>` : ''}</div>`;
}
function itemCombo(it, i, n) {
  const id = it.card_id, sg = it.suggestion, k = itemKind(it), [label, cls] = KIND[k];
  const tab = (t, text, on) => `<button type="button" role="tab" class="ltab" id="tab-${id}-${t}" aria-controls="panel-${id}-${t}" data-tabs="${id}" data-tab="${t}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${text}</button>`;
  const panel = (t, body, on) => `<div class="lpanel" role="tabpanel" id="panel-${id}-${t}" aria-labelledby="tab-${id}-${t}" data-panel="${id}:${t}" ${on ? '' : 'hidden'}>${body}</div>`;
  const first = doi => sg.evidence_used.find(e => e.doi.toLowerCase() === doi.toLowerCase() && e.excerpt);
  const ev = (src, role) => { const e = first(src.doi);
    return `<div class="desk-src">${srcHead(src, role, e?.evidence_level)}${e ? quoteBox(it, src.doi, e.excerpt, e.evidence_level, true) : '<p class="small">No passage quoted from this paper.</p>'}</div>`; };
  const comparison = `<div class="desk"><div class="desk-l">${articleQuote(it)}</div>
    <div class="desk-r">${origin('paper', 'Evidence from the papers')}
      <p class="ai-note desk-match"><span class="who">AI: does the replication test this sentence?</span> ${esc(sg.specific_study_match.note)}</p>
      ${ev(it.original, 'Original')}${it.replications.map(r => ev(r, 'Replication')).join('')}
      <p class="small">First passage quoted from each paper, not selected for this comparison; all passages are under “Papers”.</p>
      ${decideBlock(it)}</div></div>`;
  return wrap(it, i, n, `${papersLine(it)}
    <p class="tabs-rec">${origin('ai', 'AI recommendation · not yet checked by people')}<strong>${esc(ACTION[sg.proposed_action])}</strong>${label === ACTION[sg.proposed_action] ? '' : ` <span class="badge ${cls}">${label}</span>`}</p>
    <div class="combo-box"><div class="ltabs" role="tablist" aria-label="Study material">${tab('cmp', 'Comparison', true)}${tab('papers', 'Papers', false)}${tab('details', 'Details &amp; AI review', false)}</div>
      ${panel('cmp', comparison, true)}${panel('papers', comboPapers(it), false)}${panel('details', comboDetails(it), false)}</div>
    ${comboPlan(it)}${methodFold(it)}`);
}

// ---------- wiring ----------
if (LAYOUT !== 'current') {
  const render = {brief: itemBrief, tabs: itemTabs, desk: itemDesk, combo: itemCombo}[LAYOUT];
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
