create table if not exists public.fsc_generation_logs (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  vin text not null,
  mode text not null,
  file_count integer not null,
  sent_filename text not null,
  user_chat_id text not null
);

create table if not exists public.user_consents (
  user_chat_id text primary key,
  accepted_at timestamptz not null default now(),
  accepted_version text not null default '1.1.0'
);

create table if not exists public.fsc_rate_limits (
  user_chat_id text primary key,
  last_generated_at timestamptz not null default now()
);

create table if not exists public.fsc_daily_usage (
  user_chat_id text primary key,
  used_on date not null default (current_date at time zone 'utc'),
  count integer not null default 0
);

create index if not exists fsc_generation_logs_created_at_idx
  on public.fsc_generation_logs (created_at desc);

create or replace view public.fsc_generation_stats
with (security_invoker = true) as
select
  count(*)::integer as total_requests,
  coalesce(sum(file_count), 0)::integer as total_fsc_files,
  count(distinct user_chat_id)::integer as unique_users,
  count(*) filter (where mode = 'zip')::integer as zip_requests,
  count(*) filter (where mode = 'single')::integer as single_requests,
  max(created_at) as last_generated_at
from public.fsc_generation_logs;

create or replace view public.fsc_generation_daily_stats
with (security_invoker = true) as
select
  created_at::date as day,
  count(*)::integer as requests,
  coalesce(sum(file_count), 0)::integer as fsc_files,
  count(distinct user_chat_id)::integer as unique_users
from public.fsc_generation_logs
group by created_at::date;
