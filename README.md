# Opportunity Radar

Scans GitHub every morning for fast-rising projects, scores the commercial gap
around each one, and tells you which single one to work on today.

**Dashboard:** `docs/index.html` (published via GitHub Pages from `docs/`)
**Digest:** `opportunity_report.md`

---

## The goal, and how the daily routine gets there

The goal is revenue from products built beside somebody else's momentum. The
radar exists because the two hard parts of that are *timing* and *picking one*,
and both are decidable from data.

The system runs itself at 06:00 UTC. Your part is a **110-minute loop**, once a
day, in this order:

| Step | Time | What it means |
|---|---|---|
| Read the board | 5 min | Open the dashboard. Filter to **New** and **Accelerating** only. |
| Pick exactly one | 5 min | Highest score you haven't already worked. One per day — two is zero. |
| Check the gap is real | 20 min | The repo's issues and discussions, plus a name search on Reddit/X. You want people *asking* for the thing you'd sell. |
| Ship the smallest sellable version | 60 min | One page, one config pack, one guide. If it can't be done in an hour, it's the wrong first version. |
| Put it where the demand is | 15 min | Reply in the thread you found it in. Distribution on day one, not day ten. |
| Log the result | 5 min | Shipped what, posted where, any response. Kill anything with zero signal after three days. |

The dashboard leads with **Today's pick** — the highest-scoring entry whose
window is still open — and a four-step play chosen from what that specific repo
shows: no docs site, an issue backlog, a fork pile-up, or none of those. That is
the "what do I do about it" answer the score alone never gave.

### Why daily and not weekly

Momentum windows on this board close in days. A weekly cadence means you meet a
repo, on average, three and a half days after the moment it was worth meeting.
Growth thresholds are normalised **per day** (`trends.ACCELERATING_PCT_PER_DAY`),
so the classification means the same thing at any cadence — changing the cron
does not silently change what "accelerating" means.

---

## How scoring works

Score is capped at 100 and every point is attributable — the dashboard shows the
breakdown per repo.

| Component | Max | Signal |
|---|---|---|
| Momentum | 40 | stars/day since creation |
| Ecosystem fit | 30 | keyword overlap with markets we can sell into |
| Freshness | 10 | under 60 days old — the early-mover window |
| Commercial gap | 24 | no homepage, ≥40 open issues, high fork ratio, no license |
| Reach | 10 | total stars — audience size |
| Maintenance risk | −10 | no push in 30 days — a closing window, not an opening one |

Archived repos, disabled repos and forks are dropped before scoring.

---

## Trends

Every scan is archived to `history/<date>.json`. Nothing derived is stored —
deltas, status and sparklines are recomputed from the raw observations, so
changing a threshold re-labels the entire back catalogue.

- **New** — first appearance on the board
- **Accelerating** — ≥1.7% star growth per day since the previous scan
- **Steady** — between the two floors
- **Cooling** — under 0.4% per day; only worth it if you already have something half-built

`docs/index.html` also lists what *dropped off* the board since the last scan.
A closing window is a signal too.

---

## Layout

| File | Role |
|---|---|
| `scanner.py` | Query GitHub, score, write the board, report and archive |
| `trends.py` | Snapshot store; deltas, status and board summary |
| `playbook.py` | Score → today's pick, its four-step play, and the daily loop |
| `generate_site.py` | Render `docs/index.html` |
| `backfill_history.py` | One-off: recover `history/` from past `scan_data.json` commits |
| `config.json` | Title, tagline, newsletter/premium/sponsor links |
| `tests/` | Scoring, trend, playbook and escaping tests |

## Running it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .   # tests, no network
GITHUB_TOKEN=<token> python scanner.py       # scan (works unauthenticated, lower rate limit)
python generate_site.py                      # rebuild the dashboard
```

`GITHUB_TOKEN` is optional but raises the search rate limit considerably. In CI
the workflow's built-in token is used.

The scan **refuses to overwrite the board if every query fails**, and the
workflow refuses to publish an empty board — a bad API day leaves yesterday's
radar standing rather than blanking it.

## Adding a query

Add a `(query, label)` pair to `scanner.queries()`. Labels surface on the
dashboard as "found via", so make them descriptive.
