-- Run in Supabase SQL Editor. Users are created by the app admin.
create table if not exists public.watchlists (
  user_id uuid not null references auth.users(id) on delete cascade,
  ticker text not null check (ticker ~ '^[A-Z0-9.^-]{1,15}$'),
  created_at timestamptz not null default now(),
  primary key (user_id, ticker)
);
alter table public.watchlists enable row level security;
drop policy if exists "watchlist read own" on public.watchlists;
drop policy if exists "watchlist insert own" on public.watchlists;
drop policy if exists "watchlist delete own" on public.watchlists;
create policy "watchlist read own" on public.watchlists for select to authenticated using ((select auth.uid()) = user_id);
create policy "watchlist insert own" on public.watchlists for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "watchlist delete own" on public.watchlists for delete to authenticated using ((select auth.uid()) = user_id);
create index if not exists watchlists_user_idx on public.watchlists (user_id);
