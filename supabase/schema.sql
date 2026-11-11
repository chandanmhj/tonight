-- Tonight: database schema for Supabase (Postgres).
-- Run this in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
-- It is safe to run again, and it upgrades an older copy of this schema in place.

-- ---------- tables ----------
create table if not exists providers (
    provider_id      int primary key,            -- TMDB provider id (e.g. 8 = Netflix)
    name             text not null,
    logo_path        text,
    display_priority int not null default 999    -- lower = more prominent in India
);

create table if not exists movies (
    tmdb_id         int primary key,
    title           text not null,
    year            int,
    runtime         int,                          -- minutes, null when unknown
    rating          numeric(3,1),
    vote_count      int not null default 0,
    genres          text[] not null default '{}',
    mood_tags       text[] not null default '{}',
    overview        text,
    poster_path     text,
    last_checked_at timestamptz                   -- the 24-hour freshness clock
);

create table if not exists movie_providers (
    tmdb_id     int not null references movies(tmdb_id)       on delete cascade,
    provider_id int not null references providers(provider_id) on delete cascade,
    primary key (tmdb_id, provider_id)
);

-- bulk fetcher bookkeeping (lets it resume after a crash)
create table if not exists fetch_jobs (
    job         text primary key,                 -- e.g. 'discover:2019'
    next_page   int  not null default 1,
    total_pages int,
    status      text not null default 'pending'   -- pending | done
);

create table if not exists fetch_queue (
    tmdb_id    int primary key,
    status     text not null default 'pending',   -- pending | done | failed
    attempts   int  not null default 0,
    last_error text
);

create index if not exists idx_mp_provider     on movie_providers (provider_id);
create index if not exists idx_movies_runtime  on movies (runtime);
create index if not exists idx_movies_genres   on movies using gin (genres);
create index if not exists idx_movies_moods    on movies using gin (mood_tags);
create index if not exists idx_queue_status    on fetch_queue (status);

-- ---------- security ----------
-- Only the backend (secret key) touches the data. With row level security on and no
-- policies, the public "publishable / anon" key can read and write nothing.
alter table providers        enable row level security;
alter table movies           enable row level security;
alter table movie_providers  enable row level security;
alter table fetch_jobs       enable row level security;
alter table fetch_queue      enable row level security;

-- ---------- functions the backend calls ----------

-- Remove the first version of these two functions (different parameters) if it exists.
drop function if exists similar_movies(int, int[], int, int);
drop function if exists match_movies(int[], int, text, int[], int);

-- Movies from our library that fit the filters, in random order (this is what makes picks
-- different each time). Genres match if the movie has ANY of the chosen genres.
create or replace function match_movies(
    p_providers int[], p_min_runtime int, p_max_runtime int,
    p_mood text default null, p_genres text[] default '{}',
    p_exclude int[] default '{}', p_limit int default 10)
returns setof movies language sql as $$
    select m.*
    from movies m
    where m.runtime between greatest(p_min_runtime, 1) and p_max_runtime
      and m.vote_count >= 20
      and coalesce(m.rating, 0) >= 5.5
      and m.tmdb_id <> all(p_exclude)
      and (p_mood is null or p_mood = any(m.mood_tags))
      and (cardinality(p_genres) = 0 or m.genres && p_genres)
      and exists (select 1 from movie_providers mp
                  where mp.tmdb_id = m.tmdb_id and mp.provider_id = any(p_providers))
    order by random()
    limit p_limit
$$;

-- "More like these": movies that share genres with any of the given movies, on the user's
-- apps and within the runtime range. Most shared genres first, random among equals.
create or replace function similar_movies(
    p_ids int[], p_providers int[], p_min_runtime int, p_max_runtime int, p_limit int default 12)
returns setof movies language sql as $$
    with src as (
        select array_agg(distinct g) as genres
        from movies f, unnest(f.genres) g
        where f.tmdb_id = any(p_ids)
    )
    select m.*
    from movies m, src
    where m.tmdb_id <> all(p_ids)
      and m.runtime between greatest(p_min_runtime, 1) and p_max_runtime
      and m.vote_count >= 20
      and coalesce(m.rating, 0) >= 5.5
      and m.genres && src.genres
      and exists (select 1 from movie_providers mp
                  where mp.tmdb_id = m.tmdb_id and mp.provider_id = any(p_providers))
    order by cardinality(array(select unnest(m.genres) intersect select unnest(src.genres))) desc,
             random()
    limit p_limit
$$;

-- Put every movie not checked in the last 24 hours back in the fetch queue.
create or replace function requeue_stale(p_cutoff timestamptz)
returns int language plpgsql as $$
declare n int;
begin
    insert into fetch_queue (tmdb_id, status)
    select tmdb_id, 'pending' from movies
    where last_checked_at is null or last_checked_at < p_cutoff
    on conflict (tmdb_id) do update set status = 'pending', attempts = 0, last_error = null;
    get diagnostics n = row_count;
    return n;
end $$;

-- Supabase exposes functions to the public key by default. Lock them to the backend.
revoke execute on function match_movies(int[], int, int, text, text[], int[], int) from public, anon, authenticated;
revoke execute on function similar_movies(int[], int[], int, int, int)             from public, anon, authenticated;
revoke execute on function requeue_stale(timestamptz)                              from public, anon, authenticated;
grant  execute on function match_movies(int[], int, int, text, text[], int[], int) to service_role;
grant  execute on function similar_movies(int[], int[], int, int, int)             to service_role;
grant  execute on function requeue_stale(timestamptz)                              to service_role;
