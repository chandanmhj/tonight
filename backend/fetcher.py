"""
Resumable bulk fetcher: fills your Supabase database with Indian OTT movies.

Phase 1 (discover): walks TMDB's list of movies streaming in India one release year at a
time and queues every movie ID. Splitting by year gets past TMDB's 10,000-result limit.
Phase 2 (process): fetches details, rating and platforms for each queued movie, pausing
between requests and between batches.

Progress is saved in Supabase after every page and every movie, so you can stop it, kill
it, or lose your internet, and the next run carries on where it left off.

Run from the backend folder:
    python fetcher.py run --from-year 2015          # one full pass, then exit
    python fetcher.py run --forever                 # new releases + 24h refresh, repeating
    python fetcher.py status                        # progress and recent failures
Ctrl+C is safe: it finishes the current movie, saves, and exits.
"""
import argparse
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from app import config, service, store, tmdb

MAX_DISCOVER_PAGES = 500        # TMDB refuses pages beyond 500
STOP = False


def _request_stop(signum, frame):
    global STOP
    STOP = True
    print("\n[stop] finishing the current item, then exiting...", flush=True)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def nap(seconds):
    """Sleep in 1-second slices so Ctrl+C is honoured quickly."""
    end = time.time() + seconds
    while not STOP and time.time() < end:
        time.sleep(min(1, end - time.time()))


# ---------- phase 1 ----------
def discover_year(year, gap):
    job = f"discover:{year}"
    state = store.job_get(job) or {"next_page": 1, "status": "pending"}
    if state["status"] == "done":
        return
    page = state["next_page"]
    while not STOP:
        data = tmdb.discover(year, page)
        total = min(data.get("total_pages") or 0, MAX_DISCOVER_PAGES)
        store.queue_add([m["id"] for m in data.get("results", [])])
        done = page >= total
        store.job_save(job, next_page=page + 1, total_pages=total,
                       status="done" if done else "pending")
        if done:
            log(f"discover {year}: finished ({total} pages)")
            return
        page += 1
        nap(gap)


def discover(years, gap):
    for year in years:
        if STOP:
            return
        try:
            discover_year(year, gap)
        except Exception as e:           # one bad year must not kill the run
            log(f"discover {year} paused: {tmdb.clean_error(e)} (will resume next pass)")


# ---------- phase 2 ----------
def process_queue(gap, batch_size, batch_pause, max_attempts):
    ok = failed = 0
    while not STOP:
        rows = store.queue_next(batch_size, max_attempts)
        if not rows:
            break
        for r in rows:
            if STOP:
                break
            tid, attempts = r["tmdb_id"], r["attempts"]
            try:
                existing = store.get_movie(tid)
                if existing is not None and not service.is_stale(existing):
                    store.queue_set(tid, status="done")        # already fresh, no API call
                    continue
                service.refresh_movie(tid)
                store.queue_set(tid, status="done", last_error=None)
                ok += 1
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    _mark(tid, status="done", last_error="not found")
                else:
                    _mark(tid, status="failed", attempts=attempts + 1, last_error=tmdb.clean_error(e))
                    failed += 1
            except Exception as e:       # network drop, bad data, etc.: record and move on
                _mark(tid, status="failed", attempts=attempts + 1, last_error=tmdb.clean_error(e))
                failed += 1
            nap(gap)
        log(f"batch done | fetched {ok}, failed {failed} so far")
        if not STOP:
            nap(batch_pause)


def _mark(tid, **fields):
    try:
        store.queue_set(tid, **fields)
    except Exception as e:
        log(f"could not save status for {tid}: {tmdb.clean_error(e)}")


# ---------- orchestration ----------
def one_pass(args, first_pass):
    this_year = datetime.now().year
    years = list(range(this_year + 1, args.from_year - 1, -1))      # newest first
    if not first_pass:               # new releases keep arriving: re-scan the latest two years
        store.jobs_reset([f"discover:{this_year}", f"discover:{this_year + 1}"])
    discover(years, args.gap)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=config.STALE_HOURS)).isoformat()
    n = store.requeue_stale(cutoff)
    if n:
        log(f"{n} movies are older than {config.STALE_HOURS}h and queued for refresh")
    process_queue(args.gap, args.batch_size, args.batch_pause, args.max_attempts)


def run(args):
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    missing = [n for n, v in (("TMDB_API_KEY", config.TMDB_API_KEY),
                              ("SUPABASE_URL", config.SUPABASE_URL),
                              ("SUPABASE_SERVICE_KEY", config.SUPABASE_SERVICE_KEY)) if not v]
    if missing:
        sys.exit("Missing in .env: " + ", ".join(missing))
    store.upsert_providers(tmdb.all_providers())       # keep the platform list current
    first, crashes = True, 0
    while not STOP:
        try:
            one_pass(args, first)
            crashes, first = 0, False
        except Exception as e:           # last line of defence: log, back off, retry
            crashes += 1
            wait = min(900, 30 * 2 ** (crashes - 1)) + random.random()
            log(f"pass crashed ({tmdb.clean_error(e)}); retrying in {wait:.0f}s")
            nap(wait)
            continue
        if not args.forever:
            break
        log(f"cycle complete, sleeping {args.cycle_hours}h")
        nap(args.cycle_hours * 3600)
    log("stopped cleanly")


def status():
    q = store.queue_counts()
    print(f"movies stored: {store.count_movies()}")
    print(f"queue: {q['pending']} pending, {q['done']} done, {q['failed']} failed")
    for r in store.queue_failures():
        print(f"  failed {r['tmdb_id']} (x{r['attempts']}): {r['last_error']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--from-year", type=int, default=2010, help="oldest release year to scan")
    r.add_argument("--gap", type=float, default=0.3, help="seconds between requests")
    r.add_argument("--batch-size", type=int, default=100, help="movies per batch")
    r.add_argument("--batch-pause", type=float, default=30, help="seconds between batches")
    r.add_argument("--max-attempts", type=int, default=3, help="tries per failed movie")
    r.add_argument("--forever", action="store_true", help="repeat every --cycle-hours")
    r.add_argument("--cycle-hours", type=float, default=24)
    sub.add_parser("status")
    args = p.parse_args()
    run(args) if args.cmd == "run" else status()
