-- ETDS v2 database + realtime setup
create extension if not exists pgcrypto;

create table if not exists public.meters (
  id uuid primary key default gen_random_uuid(),
  meter_id text unique not null,
  location text not null default 'Unassigned',
  latitude double precision,
  longitude double precision,
  status text not null default 'normal' check (status in ('normal','warning','critical')),
  last_seen_at timestamptz,
  voltage double precision,
  current double precision,
  power_kw double precision,
  energy_kwh double precision,
  tamper boolean not null default false,
  signal_strength integer,
  relay_state text,
  device_status text not null default 'offline',
  updated_at timestamptz not null default now()
);

create table if not exists public.readings (
  id uuid primary key default gen_random_uuid(),
  meter_id text not null references public.meters(meter_id) on delete cascade,
  measured_at timestamptz not null default now(),
  voltage double precision,
  current double precision,
  power_kw double precision,
  energy_kwh double precision,
  source_power_kw double precision,
  load_power_kw double precision,
  feeder_power_kw double precision,
  tamper boolean not null default false,
  latitude double precision,
  longitude double precision,
  signal_strength integer,
  relay_state text,
  device_status text,
  status text not null default 'normal',
  severity text,
  is_theft boolean not null default false,
  anomaly_score double precision not null default 0,
  imbalance_pct double precision,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists readings_meter_time_idx on public.readings(meter_id, measured_at desc);
create index if not exists readings_theft_idx on public.readings(is_theft, measured_at desc);

create table if not exists public.incidents (
  id uuid primary key default gen_random_uuid(),
  meter_id text not null references public.meters(meter_id) on delete cascade,
  status text not null default 'active' check (status in ('active','resolved')),
  severity text not null check (severity in ('warning','critical')),
  is_theft boolean not null default false,
  detected_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by text,
  resolution_note text,
  anomaly_score double precision not null default 0,
  imbalance_pct double precision,
  reasons jsonb not null default '[]'::jsonb,
  snapshot jsonb not null default '{}'::jsonb
);
create index if not exists incidents_time_idx on public.incidents(detected_at desc);
create index if not exists incidents_active_idx on public.incidents(status, meter_id);
create unique index if not exists one_active_incident_per_meter on public.incidents(meter_id) where status = 'active';

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  role text not null default 'operator' check (role in ('operator','admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', split_part(coalesce(new.email,''),'@',1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create or replace function public.touch_meter_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists touch_meters_updated_at on public.meters;
create trigger touch_meters_updated_at before update on public.meters for each row execute function public.touch_meter_updated_at();

alter table public.meters enable row level security;
alter table public.readings enable row level security;
alter table public.incidents enable row level security;
alter table public.profiles enable row level security;

drop policy if exists "authenticated read meters" on public.meters;
create policy "authenticated read meters" on public.meters for select to authenticated using (true);
drop policy if exists "authenticated manage meters" on public.meters;
create policy "authenticated manage meters" on public.meters for all to authenticated using (true) with check (true);

drop policy if exists "authenticated read readings" on public.readings;
create policy "authenticated read readings" on public.readings for select to authenticated using (true);

drop policy if exists "authenticated read incidents" on public.incidents;
create policy "authenticated read incidents" on public.incidents for select to authenticated using (true);
drop policy if exists "authenticated resolve incidents" on public.incidents;
create policy "authenticated resolve incidents" on public.incidents for update to authenticated using (true) with check (true);

drop policy if exists "own profile read" on public.profiles;
create policy "own profile read" on public.profiles for select to authenticated using (id = auth.uid());

-- Realtime: the dashboard listens to these tables through Supabase Realtime.
do $$
begin
  begin execute 'alter publication supabase_realtime add table public.meters'; exception when duplicate_object then null; end;
  begin execute 'alter publication supabase_realtime add table public.readings'; exception when duplicate_object then null; end;
  begin execute 'alter publication supabase_realtime add table public.incidents'; exception when duplicate_object then null; end;
end $$;

-- Example first meter. Change coordinates/location or delete this seed row.
insert into public.meters (meter_id, location, latitude, longitude)
values ('MTR-001', 'Main Block', 22.3072, 73.1812)
on conflict (meter_id) do nothing;
