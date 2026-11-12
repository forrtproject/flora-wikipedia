-- Shared review storage for the review-card site (issue #10).
-- Run once in the Supabase SQL editor of a new project. Safe to re-run: it replaces the functions and
-- keeps existing rows.
--
-- Access model. The site is static and ships the project's public ("anon"/publishable) key, so anyone
-- with the page can call this API. Row-level security is on for every table with no policies, so the
-- anon role cannot read or write tables directly. All access goes through the functions below, which
-- run as their owner (security definer), validate their input, and expose only public fields.
--
-- Identity. A reviewer ID such as BS#1312 (initials + four digits) is the login. It is never returned by
-- board(): other people see initials and a random public_id. Four digits stop accidental mix-ups and
-- casual impersonation, not a determined attacker (10,000 guesses); see README.md.

create table if not exists reviewers (
  reviewer_id text primary key check (reviewer_id ~ '^[A-Z]{1,4}#[0-9]{4}$'),
  public_id   uuid not null unique default gen_random_uuid(),
  initials    text not null check (initials ~ '^[A-Z]{1,4}$'),
  email       text check (email is null or (length(email) <= 254 and email ~ '^[^@\s]+@[^@\s]+$')),
  created_at  timestamptz not null default now()
);

-- One record per reviewer and card (page). `record` keeps the site's existing per-page record shape:
-- page_id, page_title, reviewed_revision_id, items {card_id: decision}, other_fix_done,
-- draft_usefulness, notes, reviewer (initials), live_revision_checked, live_checked_at, updated_at.
create table if not exists reviews (
  page_id     text not null check (page_id ~ '^[0-9]{1,12}$'),
  reviewer_id text not null references reviewers on delete cascade,
  record      jsonb not null,
  updated_at  timestamptz not null default now(),
  primary key (page_id, reviewer_id)
);

-- "I'm reviewing this now". Shown as "Under review" for 24 hours unless switched off or a review is saved.
create table if not exists claims (
  page_id     text not null check (page_id ~ '^[0-9]{1,12}$'),
  reviewer_id text not null references reviewers on delete cascade,
  started_at  timestamptz not null default now(),
  primary key (page_id, reviewer_id)
);

-- One audit per person and card: did the reviewed work get finished (finished = true) or not.
create table if not exists audits (
  page_id     text not null check (page_id ~ '^[0-9]{1,12}$'),
  auditor_id  text not null references reviewers on delete cascade,
  finished    boolean not null,
  note        text not null default '' check (length(note) <= 2000),
  updated_at  timestamptz not null default now(),
  primary key (page_id, auditor_id)
);

alter table reviewers enable row level security;
alter table reviews   enable row level security;
alter table claims    enable row level security;
alter table audits    enable row level security;
revoke all on reviewers, reviews, claims, audits from anon, authenticated;

-- Caps that bound what a script holding the public key can do.
create or replace function _limits() returns jsonb language sql immutable as
$$ select '{"reviewers": 300, "record_bytes": 20000}'::jsonb $$;

create or replace function _who(p_reviewer_id text) returns text
language plpgsql stable security definer set search_path = public as $$
declare v text;
begin
  select reviewer_id into v from reviewers where reviewer_id = upper(trim(p_reviewer_id));
  if v is null then raise exception 'unknown reviewer ID' using errcode = '28000'; end if;
  return v;
end $$;

-- Create a reviewer ID. p_number picks the four digits (if free); otherwise a free one is drawn.
create or replace function register_reviewer(p_initials text, p_email text default null, p_number int default null)
returns jsonb language plpgsql volatile security definer set search_path = public as $$
declare ini text := upper(regexp_replace(coalesce(p_initials, ''), '[^A-Za-z]', '', 'g'));
        id text; tries int := 0;
begin
  if ini !~ '^[A-Z]{1,4}$' then raise exception 'initials must be 1 to 4 letters' using errcode = '22023'; end if;
  if (select count(*) from reviewers) >= (_limits()->>'reviewers')::int then
    raise exception 'reviewer limit reached' using errcode = '53400'; end if;
  if p_number is not null then
    if p_number not between 0 and 9999 then raise exception 'number must have four digits' using errcode = '22023'; end if;
    id := ini || '#' || lpad(p_number::text, 4, '0');
    if exists (select 1 from reviewers where reviewer_id = id) then
      raise exception 'that ID is taken' using errcode = '23505'; end if;
  else
    loop
      id := ini || '#' || lpad(floor(random() * 10000)::int::text, 4, '0');
      exit when not exists (select 1 from reviewers where reviewer_id = id);
      tries := tries + 1;
      if tries > 200 then raise exception 'no free number' using errcode = '53400'; end if;
    end loop;
  end if;
  insert into reviewers (reviewer_id, initials, email) values (id, ini, nullif(trim(p_email), ''));
  return jsonb_build_object('reviewer_id', id, 'initials', ini, 'public_id', (select public_id from reviewers where reviewer_id = id));
end $$;

create or replace function sign_in(p_reviewer_id text) returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('reviewer_id', reviewer_id, 'initials', initials, 'public_id', public_id)
  from reviewers where reviewer_id = upper(trim(p_reviewer_id))
$$;

-- Save (insert or replace) the caller's record for one page. Saving ends the caller's "under review" claim.
create or replace function save_review(p_reviewer_id text, p_page_id text, p_record jsonb) returns timestamptz
language plpgsql volatile security definer set search_path = public as $$
declare me text := _who(p_reviewer_id); ini text; now_ts timestamptz := now();
begin
  if jsonb_typeof(p_record) <> 'object' or pg_column_size(p_record) > (_limits()->>'record_bytes')::int then
    raise exception 'record too large or malformed' using errcode = '22023'; end if;
  if jsonb_typeof(coalesce(p_record->'items', '{}')) <> 'object' or exists (
       select 1 from jsonb_each_text(coalesce(p_record->'items', '{}'))
       where value not in ('edit', 'talk', 'no_change', 'later', 'skip')) then
    raise exception 'unknown decision' using errcode = '22023'; end if;
  select initials into ini from reviewers where reviewer_id = me;
  insert into reviews (page_id, reviewer_id, record, updated_at)
  values (p_page_id, me, p_record || jsonb_build_object('page_id', p_page_id, 'reviewer', ini), now_ts)
  on conflict (page_id, reviewer_id) do update set record = excluded.record, updated_at = excluded.updated_at;
  delete from claims where page_id = p_page_id and reviewer_id = me;
  return now_ts;
end $$;

create or replace function set_claim(p_reviewer_id text, p_page_id text, p_on boolean) returns void
language plpgsql volatile security definer set search_path = public as $$
declare me text := _who(p_reviewer_id);
begin
  if p_on then
    insert into claims (page_id, reviewer_id) values (p_page_id, me)
    on conflict (page_id, reviewer_id) do update set started_at = now();
  else
    delete from claims where page_id = p_page_id and reviewer_id = me;
  end if;
end $$;

-- Record whether the work on a page is finished. Someone who reviewed the page cannot audit it.
create or replace function save_audit(p_reviewer_id text, p_page_id text, p_finished boolean, p_note text default '')
returns void language plpgsql volatile security definer set search_path = public as $$
declare me text := _who(p_reviewer_id);
begin
  if exists (select 1 from reviews where page_id = p_page_id and reviewer_id = me) then
    raise exception 'you reviewed this page, so someone else needs to audit it' using errcode = '42501'; end if;
  insert into audits (page_id, auditor_id, finished, note) values (p_page_id, me, p_finished, coalesce(p_note, ''))
  on conflict (page_id, auditor_id) do update set finished = excluded.finished, note = excluded.note, updated_at = now();
end $$;

-- Everything the list and cards need, without reviewer IDs or emails.
create or replace function board() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'reviews', coalesce((select jsonb_agg(jsonb_build_object('page_id', v.page_id, 'public_id', r.public_id,
                 'initials', r.initials, 'record', v.record - 'reviewer_id', 'updated_at', v.updated_at))
               from reviews v join reviewers r using (reviewer_id)), '[]'),
    'claims', coalesce((select jsonb_agg(jsonb_build_object('page_id', c.page_id, 'public_id', r.public_id,
                 'initials', r.initials, 'started_at', c.started_at))
               from claims c join reviewers r using (reviewer_id) where c.started_at > now() - interval '24 hours'), '[]'),
    'audits', coalesce((select jsonb_agg(jsonb_build_object('page_id', a.page_id, 'public_id', r.public_id,
                 'initials', r.initials, 'finished', a.finished, 'note', a.note, 'updated_at', a.updated_at))
               from audits a join reviewers r on r.reviewer_id = a.auditor_id), '[]'))
$$;

-- The caller's own records, to restore them in a new browser.
create or replace function my_reviews(p_reviewer_id text) returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce(jsonb_agg(record || jsonb_build_object('updated_at', updated_at)), '[]')
  from reviews where reviewer_id = _who(p_reviewer_id)
$$;

revoke execute on function _who(text), _limits() from public, anon, authenticated;
grant execute on function register_reviewer(text, text, int), sign_in(text), save_review(text, text, jsonb),
  set_claim(text, text, boolean), save_audit(text, text, boolean, text), board(), my_reviews(text) to anon, authenticated;
