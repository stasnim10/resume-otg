-- Apply before deploying the remote connector. All files stay private.
create table if not exists public.mcp_connections (
  user_id uuid not null references auth.users(id) on delete cascade,
  client_id text not null,
  client_name text not null default '',
  created_at timestamptz not null default now(),
  primary key (user_id, client_id)
);
alter table public.mcp_connections enable row level security;
grant select, insert, update, delete on public.mcp_connections to authenticated;
revoke all on public.mcp_connections from anon;
create policy "mcp connection owners read" on public.mcp_connections for select
  to authenticated using (auth.uid() = user_id and
    ((auth.jwt()->>'client_id') is null or auth.jwt()->>'client_id' = client_id));
create policy "mcp connection owners manage" on public.mcp_connections for all
  to authenticated using (auth.uid() = user_id and (auth.jwt()->>'client_id') is null)
  with check (auth.uid() = user_id and (auth.jwt()->>'client_id') is null);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('mcp-resumes', 'mcp-resumes', false, 10485760,
  array['application/vnd.openxmlformats-officedocument.wordprocessingml.document'])
on conflict (id) do nothing;

create policy "mcp resume owners read" on storage.objects for select to authenticated
using (bucket_id = 'mcp-resumes' and (storage.foldername(name))[1] = auth.uid()::text and
  ((auth.jwt()->>'client_id') is null or exists (
    select 1 from public.mcp_connections c where c.user_id = auth.uid() and c.client_id = auth.jwt()->>'client_id')));
create policy "mcp resume owners insert" on storage.objects for insert to authenticated
with check (bucket_id = 'mcp-resumes' and (storage.foldername(name))[1] = auth.uid()::text and
  ((auth.jwt()->>'client_id') is null or ((storage.foldername(name))[2] = 'exports' and exists (
    select 1 from public.mcp_connections c where c.user_id = auth.uid() and c.client_id = auth.jwt()->>'client_id'))));
create policy "mcp resume owners update" on storage.objects for update to authenticated
using (bucket_id = 'mcp-resumes' and (storage.foldername(name))[1] = auth.uid()::text and (auth.jwt()->>'client_id') is null)
with check (bucket_id = 'mcp-resumes' and (storage.foldername(name))[1] = auth.uid()::text and (auth.jwt()->>'client_id') is null);
create policy "mcp resume owners delete" on storage.objects for delete to authenticated
using (bucket_id = 'mcp-resumes' and (storage.foldername(name))[1] = auth.uid()::text and (auth.jwt()->>'client_id') is null);

-- Existing policies were written for direct app sessions. Prevent connector
-- tokens from accessing unrelated tables, including saved provider API keys.
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' and tablename <> 'mcp_connections'
  loop
    execute format('create policy "direct app sessions only" on public.%I as restrictive for all to authenticated using ((auth.jwt()->>''client_id'') is null) with check ((auth.jwt()->>''client_id'') is null)', t.tablename);
  end loop;
end $$;

-- Configure this function as the Supabase Custom Access Token Hook.
-- Approved MCP clients get an audience restricted to the MCP resource. Preserve
-- the authenticated audience as well for Supabase Storage/PostgREST access.
create or replace function public.mcp_access_token_hook(event jsonb)
returns jsonb language plpgsql stable set search_path = '' as $$
declare claims jsonb; connector text;
begin
  claims := event->'claims';
  connector := coalesce(event->>'client_id', claims->>'client_id');
  if connector is not null and exists (
    select 1 from public.mcp_connections where user_id = (event->>'user_id')::uuid and client_id = connector
  ) then
    claims := jsonb_set(claims, '{aud}', '["authenticated", "https://mcp.resumeotg.app/mcp"]'::jsonb);
    event := jsonb_set(event, '{claims}', claims);
  end if;
  return event;
end $$;
grant usage on schema public to supabase_auth_admin;
grant select on public.mcp_connections to supabase_auth_admin;
create policy "auth admin reads mcp approvals" on public.mcp_connections for select to supabase_auth_admin using (true);
grant execute on function public.mcp_access_token_hook to supabase_auth_admin;
revoke execute on function public.mcp_access_token_hook from public, anon, authenticated;
