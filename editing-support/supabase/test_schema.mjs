// Checks schema.sql on an in-memory Postgres (PGlite) as Supabase's anon role.
// Run from editing-support/supabase:  npm i --no-save @electric-sql/pglite && node test_schema.mjs
// (node_modules and package files here are gitignored)
import { PGlite } from '@electric-sql/pglite';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const sql = fs.readFileSync(fileURLToPath(new URL('schema.sql', import.meta.url)), 'utf8');
const db = new PGlite();
await db.exec('create role anon nologin; create role authenticated nologin; grant usage on schema public to anon, authenticated;');
await db.exec(sql);
await db.exec(sql);  // re-running the setup keeps working
await db.exec("insert into pages (page_id) values ('123'), ('456'), ('789')");
await db.exec('set role anon');
const one = async (q, p) => (await db.query(q, p)).rows[0]?.r;
const fails = async (q, re, p) => assert.rejects(db.query(q, p), re, q);

// Tables are closed to the public key; only the functions are open.
for (const t of ['pages', 'reviewers', 'reviews', 'claims', 'audits']) await fails(`select * from ${t}`, /permission denied/);
await fails("insert into reviewers (reviewer_id, initials) values ('X#0001', 'X')", /permission denied/);
await fails("select _who('x')", /permission denied/);
await fails("select _page('123')", /permission denied/);

const a = await one("select register_reviewer('b.s.', 'a@example.org', 1312) r");
assert.equal(a.reviewer_id, 'BS#1312');
await fails("select register_reviewer('BS', null, 1312)", /taken/);
await fails("select register_reviewer('12', null)", /initials/);
const b = await one("select register_reviewer('cd') r"), c = await one("select register_reviewer('ef') r");
assert.match(b.reviewer_id, /^CD#\d{4}$/);
assert.equal((await one("select sign_in(' bs#1312 ') r")).public_id, a.public_id);
assert.equal(await one("select sign_in('BS#1313') r"), null);

await one(`select save_review('BS#1312', '123', '{"items": {"x": "edit"}, "notes": "n", "reviewer": "ZZ"}') r`);
await fails(`select save_review('BS#1312', '123', '{"items": {"x": "hack"}}')`, /unknown decision/);
await fails(`select save_review('BS#1312', '12a', '{"items": {}}')`, /unknown page/);
await fails(`select save_review('BS#1312', '999999', '{"items": {}}')`, /unknown page/);  // not a card on the site
await fails("select set_claim('BS#1312', '999999', true)", /unknown page/);
await fails("select save_audit($1, '789', true)", /nobody else/, [b.reviewer_id]);  // no review yet
await fails(`select save_review('ZZ#0000', '123', '{"items": {}}')`, /unknown reviewer/);
await fails(`select save_review('BS#1312', '123', jsonb_build_object('notes', repeat(md5(random()::text), 2000)))`, /too large/);

await one('select set_claim($1, $2, true) r', [c.reviewer_id, '123']);
await one('select set_claim($1, $2, true) r', [c.reviewer_id, '456']);
await one(`select save_review($1, '456', '{"items": {"y": "no_change"}}') r`, [c.reviewer_id]);  // saving ends the claim
await fails("select save_audit('BS#1312', '123', true)", /someone else/);
await one("select save_audit($1, '123', true, 'done') r", [b.reviewer_id]);

// decided_at moves only when the decisions change, so a notes-only edit keeps earlier audits valid.
const decided = async () => (await one('select board() r')).reviews.find(r => r.page_id === '123').decided_at;
const d0 = await decided();
await one(`select save_review('BS#1312', '123', '{"items": {"x": "edit"}, "notes": "longer note"}') r`);
assert.equal(await decided(), d0);
await one(`select save_review('BS#1312', '123', '{"items": {"x": "talk"}, "notes": "longer note"}') r`);
assert.notEqual(await decided(), d0);
await one(`select save_review('BS#1312', '123', '{"items": {"x": "edit"}, "notes": "n"}') r`);

const board = await one('select board() r');
assert.equal(board.reviews.length, 2);
assert.equal(board.reviews.find(r => r.page_id === '123').record.reviewer, 'BS');  // initials come from the server
assert.deepEqual(board.claims.map(x => x.page_id), ['123']);
assert.equal(board.audits[0].initials, 'CD');
assert.ok(!JSON.stringify(board).includes('#'), 'board() must not reveal reviewer IDs');
assert.ok(!JSON.stringify(board).includes('example.org'), 'board() must not reveal emails');
assert.equal((await one("select my_reviews('BS#1312') r")).length, 1);
console.log('schema.sql: all checks passed');
