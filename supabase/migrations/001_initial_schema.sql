-- ============================================================
-- Resume Builder OTG — Initial Supabase Schema
-- Run this in the Supabase SQL editor for your project.
-- ============================================================

-- ── 1. profiles ─────────────────────────────────────────────
create table if not exists public.profiles (
  id                  uuid primary key references auth.users(id) on delete cascade,
  full_name           text not null default '',
  email               text not null default '',
  phone               text not null default '',
  location            text not null default '',
  linkedin            text not null default '',
  portfolio_url       text not null default '',
  photo_path          text not null default '',
  headline            text not null default '',
  career_stage        text not null default 'Student',
  summary             text not null default '',
  target_roles        jsonb not null default '[]'::jsonb,
  target_industries   jsonb not null default '[]'::jsonb,
  preferred_locations jsonb not null default '[]'::jsonb,
  work_authorization  text not null default '',
  onboarding_complete boolean not null default false,
  onboarding_started_at timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "users can read own profile"
  on public.profiles for select using (auth.uid() = id);

create policy "users can insert own profile"
  on public.profiles for insert with check (auth.uid() = id);

create policy "users can update own profile"
  on public.profiles for update using (auth.uid() = id);


-- ── 2. user_settings ────────────────────────────────────────
create table if not exists public.user_settings (
  user_id                      uuid primary key references auth.users(id) on delete cascade,
  preferred_provider           text not null default 'OpenAI',
  default_model                text not null default '',
  api_key_encrypted            text not null default '',
  api_key_last4                text not null default '',
  api_key_valid                boolean not null default false,
  api_key_validation_message   text not null default '',
  created_at                   timestamptz not null default now(),
  updated_at                   timestamptz not null default now()
);

alter table public.user_settings enable row level security;

create policy "users can read own settings"
  on public.user_settings for select using (auth.uid() = user_id);

create policy "users can insert own settings"
  on public.user_settings for insert with check (auth.uid() = user_id);

create policy "users can update own settings"
  on public.user_settings for update using (auth.uid() = user_id);


-- ── 3. profile_sources ──────────────────────────────────────
create table if not exists public.profile_sources (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  source_type         text not null default 'manual_notes',
  source_name         text not null default '',
  storage_path        text not null default '',
  raw_text            text not null default '',
  parsed_status       text not null default 'pending',
  parsed_payload_json jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now()
);

alter table public.profile_sources enable row level security;

create policy "users can read own sources"
  on public.profile_sources for select using (auth.uid() = user_id);

create policy "users can insert own sources"
  on public.profile_sources for insert with check (auth.uid() = user_id);

create policy "users can update own sources"
  on public.profile_sources for update using (auth.uid() = user_id);

create policy "users can delete own sources"
  on public.profile_sources for delete using (auth.uid() = user_id);


-- ── 4. profile_items ────────────────────────────────────────
create table if not exists public.profile_items (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  source_id           uuid references public.profile_sources(id) on delete set null,
  item_type           text not null default 'experience',
  title               text not null default '',
  organization        text not null default '',
  location            text not null default '',
  start_date          text not null default '',
  end_date            text not null default '',
  is_current          boolean not null default false,
  description         text not null default '',
  bullets             jsonb not null default '[]'::jsonb,
  skills              jsonb not null default '[]'::jsonb,
  tools               jsonb not null default '[]'::jsonb,
  industry_tags       jsonb not null default '[]'::jsonb,
  function_tags       jsonb not null default '[]'::jsonb,
  keywords            jsonb not null default '[]'::jsonb,
  confidence_score    numeric not null default 0.5,
  verification_status text not null default 'suggested',
  visibility          text not null default 'active',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.profile_items enable row level security;

create policy "users can read own items"
  on public.profile_items for select using (auth.uid() = user_id);

create policy "users can insert own items"
  on public.profile_items for insert with check (auth.uid() = user_id);

create policy "users can update own items"
  on public.profile_items for update using (auth.uid() = user_id);

create policy "users can delete own items"
  on public.profile_items for delete using (auth.uid() = user_id);


-- ── 5. tracked_jobs ─────────────────────────────────────────
create table if not exists public.tracked_jobs (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  job_title        text not null default '',
  company          text not null default '',
  job_description  text not null default '',
  role_family      text not null default '',
  industry         text not null default '',
  job_url          text not null default '',
  location         text not null default '',
  status           text not null default 'Bookmarked',
  next_action      text not null default '',
  applied_date     date,
  profile_item_ids jsonb not null default '[]'::jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

alter table public.tracked_jobs enable row level security;

create policy "users can read own jobs"
  on public.tracked_jobs for select using (auth.uid() = user_id);

create policy "users can insert own jobs"
  on public.tracked_jobs for insert with check (auth.uid() = user_id);

create policy "users can update own jobs"
  on public.tracked_jobs for update using (auth.uid() = user_id);

create policy "users can delete own jobs"
  on public.tracked_jobs for delete using (auth.uid() = user_id);


-- ── 6. job_notes ────────────────────────────────────────────
create table if not exists public.job_notes (
  id         uuid primary key default gen_random_uuid(),
  job_id     uuid not null references public.tracked_jobs(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  note_type  text not null default 'general',
  content    text not null default '',
  created_at timestamptz not null default now()
);

alter table public.job_notes enable row level security;

create policy "users can read own notes"
  on public.job_notes for select using (auth.uid() = user_id);

create policy "users can insert own notes"
  on public.job_notes for insert with check (auth.uid() = user_id);

create policy "users can update own notes"
  on public.job_notes for update using (auth.uid() = user_id);

create policy "users can delete own notes"
  on public.job_notes for delete using (auth.uid() = user_id);


-- ── 7. job_timeline_events ──────────────────────────────────
create table if not exists public.job_timeline_events (
  id            uuid primary key default gen_random_uuid(),
  job_id        uuid not null references public.tracked_jobs(id) on delete cascade,
  event_type    text not null,
  description   text not null default '',
  metadata_json jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

alter table public.job_timeline_events enable row level security;

create policy "users can read own events"
  on public.job_timeline_events for select
  using (exists (
    select 1 from public.tracked_jobs j
    where j.id = job_timeline_events.job_id and j.user_id = auth.uid()
  ));

create policy "users can insert own events"
  on public.job_timeline_events for insert
  with check (exists (
    select 1 from public.tracked_jobs j
    where j.id = job_timeline_events.job_id and j.user_id = auth.uid()
  ));


-- ── 8. job_optimization_runs ────────────────────────────────
create table if not exists public.job_optimization_runs (
  id                          uuid primary key default gen_random_uuid(),
  job_id                      uuid not null references public.tracked_jobs(id) on delete cascade,
  user_id                     uuid not null references auth.users(id) on delete cascade,
  match_before                integer not null default 0,
  match_after                 integer not null default 0,
  delta                       integer not null default 0,
  improvements                jsonb not null default '[]'::jsonb,
  resume_storage_path         text not null default '',
  cover_letter_storage_path   text not null default '',
  profile_item_ids            jsonb not null default '[]'::jsonb,
  run_at                      timestamptz not null default now()
);

alter table public.job_optimization_runs enable row level security;

create policy "users can read own runs"
  on public.job_optimization_runs for select using (auth.uid() = user_id);

create policy "users can insert own runs"
  on public.job_optimization_runs for insert with check (auth.uid() = user_id);


-- ── Storage bucket ───────────────────────────────────────────
-- Create this bucket in the Supabase dashboard or via the Storage API.
-- Suggested name: user-documents
-- Suggested path structure:
--   {user_id}/resumes/
--   {user_id}/sources/
--   {user_id}/exports/
--   {user_id}/profile/photo.jpg
