# Shared review storage (Supabase)

The review-card site saves reviews in each reviewer's browser. With a Supabase project, saved reviews are also
shared: the list shows which articles are under review, waiting for an audit or audited, and a reviewer can sign
in on another device. Without the project the site works as before (browser only). To try the shared features
without a project, open the site with `?store=demo`: a pretend backend in the browser, with made-up reviewers.

## Set-up (about 10 minutes, free plan)

1. Sign in at <https://supabase.com> and create a project on the free plan (for example
   `flora-wikipedia-reviews`, region close to the reviewers). Keep the database password in a password manager;
   the site does not need it.
2. Open **SQL Editor → New query**, paste the whole of [`schema.sql`](schema.sql) and click **Run**. Running it
   again later is safe: it replaces the functions and keeps the rows. Then do the same with
   [`pages.sql`](pages.sql), the list of cards the store accepts. When the set of cards changes, regenerate it with
   `python3 editing-support/supabase/make_pages_sql.py` and run it again.
3. Open **Project Settings → API Keys** (older dashboards: **Settings → API**) and copy
   - the **Project URL** (`https://<project-ref>.supabase.co`), and
   - the **publishable** key (`sb_publishable_…`) or, on older projects, the **anon public** key (`eyJ…`).

   Never use the **secret** or **service_role** key: it bypasses all access rules.
4. Save both in a private file outside the repository, readable only by you:

   ```sh
   mkdir -p ~/.config/flora-wikipedia
   printf 'FLORA_SUPABASE_URL=%s\nFLORA_SUPABASE_ANON_KEY=%s\n' 'https://<project-ref>.supabase.co' '<publishable key>' \
     > ~/.config/flora-wikipedia/supabase.env
   chmod 600 ~/.config/flora-wikipedia/supabase.env
   ```

   The environment variables of the same names override the file.
5. Rebuild the site (`bash editing-support/build.sh`). The build writes `config.js` next to `index.html`; without
   the values it writes a browser-only `config.js`. Open the site: "Your reviews" now offers "Your reviewer ID".

The publishable/anon key is public by design: every visitor's browser receives it, so a published copy of the site
(for example the `gh-pages` branch) contains it. It is kept out of the source repository so a project can be
replaced without a commit, and because it grants only what `schema.sql` allows.

## What the schema allows

Row-level security is on for all tables and the public key has no table rights. Everything goes through a few
functions that check their input:

| Function | Who | What |
|---|---|---|
| `register_reviewer(initials, email?, number?)` | anyone | creates an ID such as `BS#1312` (chosen or random digits) |
| `sign_in(id)` | anyone | returns initials and a random public ID, or nothing |
| `save_review(id, page_id, record)` | holder of an ID | one record per reviewer and card; ends their "under review" mark; `decided_at` moves only when the decisions change |
| `set_claim(id, page_id, on)` | holder of an ID | "I'm reviewing this now", shown for 24 hours |
| `save_audit(id, page_id, finished, note)` | holder of an ID who did not review the card, once someone else has | finished / not finished |
| `board()` | anyone | all reviews, current claims and audits, with initials and public IDs only |
| `my_reviews(id)` | holder of an ID | that reviewer's records, to restore them in a new browser |

Every function accepts only the cards listed in `pages`. Limits: at most 300 reviewer IDs and 20 kB per review record (`_limits()` in `schema.sql`). Emails are stored only in
`reviewers.email`, visible to project owners in the dashboard and never returned by the functions.

Rules computed in the site (`groupState` in `site/app.js`): a review counts once every publication on the card has a
decision and at least one decision is "edited", "talk page" or "no change needed". The card is then "to be audited"
until two people who did not review it mark it finished; it is then "audited". An audit counts only if it was
made after the latest change of decisions in a counting review, so changing a decision asks for a fresh audit (editing
only the notes does not).

In the browser, records are kept per reviewer ID. Reviews saved without an ID (or from before shared storage) are
shared only when someone signed in clicks "Share as …" under "Your reviews".

## Running the project

- **Export everything**: in the SQL editor,
  `select r.initials, v.page_id, v.record, v.updated_at from reviews v join reviewers r using (reviewer_id);`
  (or the table editor's CSV export). Each reviewer can still export their own CSV/JSON from the site.
- **Forgotten ID**: look up the initials (and email, if given) in the `reviewers` table and send the ID.
- **Remove someone's data**: `delete from reviewers where reviewer_id = 'BS#1312';` (their reviews, claims and audits
  go with it).
- **Free-plan pause**: Supabase pauses free projects after a period without activity; restore it from the dashboard.
  The site keeps saving to the browser meanwhile and sends queued reviews once the project answers again.

## Testing the schema

`test_schema.mjs` runs `schema.sql` on an in-memory Postgres (PGlite) as the anon role and checks the access rules:

```sh
cd editing-support/supabase && npm i --no-save @electric-sql/pglite && node test_schema.mjs
```

`editing-support/tests/test_shared_store.py` runs it as part of pytest when PGlite is installed there.
