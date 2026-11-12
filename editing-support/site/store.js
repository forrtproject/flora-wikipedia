'use strict';
// Storage adapter for reviews (issue #10). Two modes:
// - local (default): reviews live only in this browser, as before.
// - shared: config.js sets window.FLORA_STORE = {url, anonKey} for a Supabase project set up with
//   editing-support/supabase/schema.sql. Reviews are still written to this browser first (draft, fallback,
//   export) and then sent to the shared store; anything not yet sent is retried.
// ?store=demo runs the shared mode against a pretend backend kept in this browser, with a few seeded
// reviews from made-up reviewers, so the shared features can be tried without a project.
const Store = (() => {
  const cfg = window.FLORA_STORE || {};
  const demo = new URLSearchParams(location.search).get('store') === 'demo';
  const shared = demo || !!(cfg.url && cfg.anonKey);
  const PFX = demo ? 'flora-demo:' : 'flora-en-edit-proto:';
  const ME_KEY = PFX + 'me', PENDING_KEY = PFX + 'unsynced';
  const get = k => { try { return localStorage.getItem(k); } catch { return null; } };
  const set = (k, v) => { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* not stored */ } };
  const getJSON = (k, d) => { try { return JSON.parse(get(k)) ?? d; } catch { return d; } };

  let board = {reviews: [], claims: [], audits: []}, online = null, lastError = '';

  async function rpc(name, args = {}) {
    if (demo) return Demo.call(name, args);
    const headers = {apikey: cfg.anonKey, 'Content-Type': 'application/json'};
    if (/^eyJ/.test(cfg.anonKey)) headers.Authorization = 'Bearer ' + cfg.anonKey;  // legacy JWT-style anon key
    const r = await fetch(`${cfg.url.replace(/\/$/, '')}/rest/v1/rpc/${name}`, {method: 'POST', headers, body: JSON.stringify(args)});
    const body = await r.json().catch(() => null);
    if (!r.ok) throw new Error(body?.message || `${r.status} ${r.statusText}`);
    return body;
  }
  // Wraps a call so a lost connection is recorded rather than thrown at the reader.
  async function attempt(fn) {
    try { const v = await fn(); online = true; lastError = ''; return {ok: true, v}; }
    catch (e) {
      online = false;
      lastError = e instanceof TypeError ? 'no connection to the shared store' : String(e.message || e);
      return {ok: false, error: lastError};
    }
  }

  const me = () => shared ? getJSON(ME_KEY, null) : null;
  const pending = () => getJSON(PENDING_KEY, []);
  const setPending = ids => set(PENDING_KEY, ids.length ? JSON.stringify([...new Set(ids)]) : null);

  async function refresh() {
    if (!shared) return false;
    const r = await attempt(() => rpc('board'));
    if (r.ok) board = r.v;
    return r.ok;
  }
  // Send one saved record. Without a sign-in, or offline, it waits in the queue.
  async function push(pageId, rec) {
    if (!shared) return {ok: true, local: true};
    setPending([...pending(), pageId]);
    const who = me();
    if (!who) return {ok: false, error: 'not signed in'};
    const r = await attempt(() => rpc('save_review', {p_reviewer_id: who.reviewer_id, p_page_id: pageId, p_record: rec}));
    if (r.ok) setPending(pending().filter(x => x !== pageId));
    return r;
  }
  const queue = pageId => setPending([...pending(), pageId]);
  async function flush(read) {
    let sent = 0;
    for (const id of pending()) {
      const rec = read(id);
      if (!rec) { setPending(pending().filter(x => x !== id)); continue; }
      if ((await push(id, rec)).ok) sent++; else break;
    }
    return sent;
  }
  async function signIn(id) {
    const r = await attempt(() => rpc('sign_in', {p_reviewer_id: id}));
    if (r.ok && r.v) set(ME_KEY, JSON.stringify(r.v));
    return r.ok ? (r.v ? {ok: true, me: r.v} : {ok: false, error: 'No reviewer has that ID. Check the letters and the four digits.'}) : r;
  }
  async function register(initials, email, number) {
    const r = await attempt(() => rpc('register_reviewer', {p_initials: initials, p_email: email || null, p_number: number === '' || number == null ? null : Number(number)}));
    if (r.ok) set(ME_KEY, JSON.stringify(r.v));
    return r.ok ? {ok: true, me: r.v} : r;
  }
  const signOut = () => set(ME_KEY, null);
  const mine = async () => { const who = me(); return who ? attempt(() => rpc('my_reviews', {p_reviewer_id: who.reviewer_id})) : {ok: false}; };
  const claim = async (pageId, on) => attempt(() => rpc('set_claim', {p_reviewer_id: me().reviewer_id, p_page_id: pageId, p_on: on}));
  const audit = async (pageId, finished, note) =>
    attempt(() => rpc('save_audit', {p_reviewer_id: me().reviewer_id, p_page_id: pageId, p_finished: finished, p_note: note || ''}));

  const forPage = id => ({reviews: board.reviews.filter(r => r.page_id === id), claims: board.claims.filter(c => c.page_id === id),
    audits: board.audits.filter(a => a.page_id === id)});

  return {shared, demo, prefix: PFX, me, signIn, register, signOut, refresh, push, queue, flush, pending, mine, claim, audit, forPage,
    status: () => ({online, lastError})};
})();

// A pretend backend for ?store=demo. Mirrors the rules in supabase/schema.sql closely enough to try the flow.
const Demo = (() => {
  const K = 'flora-demo:db';
  const load = () => { try { return JSON.parse(localStorage.getItem(K)); } catch { return null; } };
  const save = db => { try { localStorage.setItem(K, JSON.stringify(db)); } catch { /* demo only */ } };
  const now = () => new Date().toISOString();
  const ago = h => new Date(Date.now() - h * 3600e3).toISOString();
  let db = null;
  // Seed: four made-up reviewers and a few cards in each state. Uses the first pages of the loaded data.
  function seed(pages) {
    const people = [['AB#1001', 'AB'], ['CD#1002', 'CD'], ['EF#1003', 'EF'], ['GH#1004', 'GH']]
      .map(([id, ini]) => ({reviewer_id: id, initials: ini, public_id: 'demo-' + ini.toLowerCase()}));
    const rec = (p, dec, notes, h) => ({page_id: p.page_id, page_title: p.page.title, reviewed_revision_id: p.page.frozen_revid,
      items: Object.fromEntries(p.items.map(it => [it.card_id, dec])), other_fix_done: false, draft_usefulness: 'useful', notes, updated_at: ago(h)});
    const [a, b, c, d] = pages;
    db = {reviewers: people, reviews: [], claims: [], audits: []};
    const rv = (who, p, dec, notes, h) => db.reviews.push({page_id: p.page_id, reviewer_id: who, record: {...rec(p, dec, notes, h), reviewer: who.slice(0, 2)}, updated_at: ago(h)});
    if (a) { rv('AB#1001', a, 'edit', 'Added one attributed sentence on the 2012 replication to the Criticism section.', 5);
      db.audits.push({page_id: a.page_id, auditor_id: 'CD#1002', finished: true, note: 'Sentence is in and sourced.', updated_at: ago(2)}); }
    if (b) rv('CD#1002', b, 'no_change', 'The article already describes the replication in the Reception section.', 20);
    if (c) db.claims.push({page_id: c.page_id, reviewer_id: 'EF#1003', started_at: ago(0.5)});
    if (d) { rv('GH#1004', d, 'talk', 'Raised on the talk page; regulars agreed to add it.', 30);
      db.audits.push({page_id: d.page_id, auditor_id: 'AB#1001', finished: true, note: '', updated_at: ago(10)},
        {page_id: d.page_id, auditor_id: 'EF#1003', finished: true, note: 'Done.', updated_at: ago(8)}); }
    save(db);
  }
  const who = id => { const r = db.reviewers.find(x => x.reviewer_id === String(id || '').trim().toUpperCase()); if (!r) throw new Error('unknown reviewer ID'); return r; };
  const pub = r => ({public_id: r.public_id, initials: r.initials});
  const fns = {
    register_reviewer({p_initials, p_email, p_number}) {
      const ini = String(p_initials || '').replace(/[^A-Za-z]/g, '').toUpperCase();
      if (!/^[A-Z]{1,4}$/.test(ini)) throw new Error('initials must be 1 to 4 letters');
      let id = p_number != null ? `${ini}#${String(p_number).padStart(4, '0')}` : null;
      if (id && db.reviewers.some(r => r.reviewer_id === id)) throw new Error('that ID is taken');
      while (!id || db.reviewers.some(r => r.reviewer_id === id)) id = `${ini}#${String(Math.floor(Math.random() * 1e4)).padStart(4, '0')}`;
      const r = {reviewer_id: id, initials: ini, public_id: 'demo-' + Math.random().toString(36).slice(2), email: p_email};
      db.reviewers.push(r); save(db);
      return {reviewer_id: id, initials: ini, public_id: r.public_id};
    },
    sign_in({p_reviewer_id}) { try { const r = who(p_reviewer_id); return {reviewer_id: r.reviewer_id, ...pub(r)}; } catch { return null; } },
    save_review({p_reviewer_id, p_page_id, p_record}) {
      const r = who(p_reviewer_id), t = now();
      db.reviews = db.reviews.filter(x => !(x.page_id === p_page_id && x.reviewer_id === r.reviewer_id));
      db.reviews.push({page_id: p_page_id, reviewer_id: r.reviewer_id, record: {...p_record, page_id: p_page_id, reviewer: r.initials}, updated_at: t});
      db.claims = db.claims.filter(x => !(x.page_id === p_page_id && x.reviewer_id === r.reviewer_id));
      save(db); return t;
    },
    set_claim({p_reviewer_id, p_page_id, p_on}) {
      const r = who(p_reviewer_id);
      db.claims = db.claims.filter(x => !(x.page_id === p_page_id && x.reviewer_id === r.reviewer_id));
      if (p_on) db.claims.push({page_id: p_page_id, reviewer_id: r.reviewer_id, started_at: now()});
      save(db); return null;
    },
    save_audit({p_reviewer_id, p_page_id, p_finished, p_note}) {
      const r = who(p_reviewer_id);
      if (db.reviews.some(x => x.page_id === p_page_id && x.reviewer_id === r.reviewer_id)) throw new Error('you reviewed this page, so someone else needs to audit it');
      db.audits = db.audits.filter(x => !(x.page_id === p_page_id && x.auditor_id === r.reviewer_id));
      db.audits.push({page_id: p_page_id, auditor_id: r.reviewer_id, finished: p_finished, note: p_note || '', updated_at: now()});
      save(db); return null;
    },
    board() {
      const byId = id => pub(db.reviewers.find(r => r.reviewer_id === id));
      const fresh = Date.now() - 24 * 3600e3;
      return {reviews: db.reviews.map(x => ({page_id: x.page_id, ...byId(x.reviewer_id), record: x.record, updated_at: x.updated_at})),
        claims: db.claims.filter(x => Date.parse(x.started_at) > fresh).map(x => ({page_id: x.page_id, ...byId(x.reviewer_id), started_at: x.started_at})),
        audits: db.audits.map(x => ({page_id: x.page_id, ...byId(x.auditor_id), finished: x.finished, note: x.note, updated_at: x.updated_at}))};
    },
    my_reviews({p_reviewer_id}) { const r = who(p_reviewer_id); return db.reviews.filter(x => x.reviewer_id === r.reviewer_id).map(x => ({...x.record, updated_at: x.updated_at})); },
  };
  return {
    init(pages) { db = load(); if (!db) seed(pages); },
    async call(name, args) { await new Promise(r => setTimeout(r, 80)); return JSON.parse(JSON.stringify(fns[name](args))); },
  };
})();
