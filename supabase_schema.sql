create table if not exists public.fsc_generation_logs (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  vin text not null,
  mode text not null,
  file_count integer not null,
  sent_filename text not null,
  user_chat_id text not null
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
