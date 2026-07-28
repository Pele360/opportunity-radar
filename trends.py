"""Snapshot store and week-over-week trend maths for the opportunity radar.

Every scan is archived to ``history/<date>.json`` so the radar can answer the
question a single snapshot never could: *is this thing still accelerating?*
"""

import datetime
import glob
import json
import os

HISTORY_DIR = "history"

# Growth thresholds are expressed *per day* so the same rules hold whether the
# radar runs daily or weekly - a gap of N days is normalised before comparison.
ACCELERATING_PCT_PER_DAY = 1.7
COOLING_PCT_PER_DAY = 0.4

# How many points of history a sparkline shows.
SPARK_POINTS = 12


def save_snapshot(data, history_dir=HISTORY_DIR):
    """Archive one scan. Re-running a scan on the same day overwrites that day."""
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, data["date"] + ".json")
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    return path


def load_snapshots(history_dir=HISTORY_DIR):
    """Return every archived scan, oldest first."""
    snapshots = []
    for path in sorted(glob.glob(os.path.join(history_dir, "*.json"))):
        try:
            with open(path) as fh:
                snap = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        if snap.get("date") and isinstance(snap.get("items"), list):
            snapshots.append(snap)
    snapshots.sort(key=lambda s: s["date"])
    return snapshots


def build_timeline(snapshots):
    """Map repo full_name -> chronological list of observations."""
    timeline = {}
    for snap in snapshots:
        for item in snap["items"]:
            timeline.setdefault(item["name"], []).append(
                {
                    "date": snap["date"],
                    "stars": item.get("stars", 0),
                    "score": item.get("score", 0),
                    "velocity": item.get("velocity", 0),
                }
            )
    return timeline


def _pct_change(current, previous):
    if not previous:
        return None
    return (current - previous) / previous * 100.0


def days_between(a, b):
    """Whole days between two ISO dates, never less than 1."""
    d1 = datetime.date.fromisoformat(a)
    d2 = datetime.date.fromisoformat(b)
    return max(abs((d2 - d1).days), 1)


def classify(item, points):
    """Label a repo's trajectory from its own observation history.

    ``points`` is the repo's timeline *including* the current observation.
    Growth is normalised to a per-day rate, so a daily and a weekly cadence
    classify the same repo the same way.
    """
    if len(points) < 2:
        return "new"
    latest, prior = points[-1], points[-2]
    pct = _pct_change(latest["stars"], prior["stars"])
    if pct is None:
        return "steady"
    per_day = pct / days_between(prior["date"], latest["date"])
    if per_day >= ACCELERATING_PCT_PER_DAY:
        return "accelerating"
    if per_day < COOLING_PCT_PER_DAY:
        return "cooling"
    return "steady"


def annotate(items, snapshots):
    """Attach trend fields to the current scan's items.

    ``snapshots`` must already include the current scan (so ``save_snapshot``
    runs first). Items are mutated in place and also returned.
    """
    timeline = build_timeline(snapshots)
    prior_dates = [s["date"] for s in snapshots]
    previous_date = prior_dates[-2] if len(prior_dates) >= 2 else None

    for item in items:
        points = timeline.get(item["name"], [])
        # Guard against a caller that annotates before archiving.
        if not points or points[-1]["date"] != snapshots[-1]["date"]:
            points = points + [
                {
                    "date": snapshots[-1]["date"],
                    "stars": item.get("stars", 0),
                    "score": item.get("score", 0),
                    "velocity": item.get("velocity", 0),
                }
            ]

        item["first_seen"] = points[0]["date"]
        item["appearances"] = len(points)
        item["history"] = points[-SPARK_POINTS:]
        item["status"] = classify(item, points)

        if len(points) >= 2:
            prior = points[-2]
            gap = days_between(prior["date"], points[-1]["date"])
            item["star_delta"] = points[-1]["stars"] - prior["stars"]
            item["score_delta"] = points[-1]["score"] - prior["score"]
            pct = _pct_change(points[-1]["stars"], prior["stars"])
            item["star_delta_pct"] = round(pct, 1) if pct is not None else None
            item["star_delta_pct_per_day"] = (
                round(pct / gap, 2) if pct is not None else None
            )
            item["compared_to"] = prior["date"]
            item["days_since_compared"] = gap
        else:
            item["star_delta"] = None
            item["score_delta"] = None
            item["star_delta_pct"] = None
            item["star_delta_pct_per_day"] = None
            item["compared_to"] = previous_date
            item["days_since_compared"] = None

    return items


def departed(snapshots, limit=8):
    """Repos on the previous board that dropped off the current one.

    Falling off the board is itself a signal — the window may be closing.
    """
    if len(snapshots) < 2:
        return []
    current = {i["name"] for i in snapshots[-1]["items"]}
    out = []
    for item in snapshots[-2]["items"]:
        if item["name"] not in current:
            out.append(
                {
                    "name": item["name"],
                    "url": item.get("url", ""),
                    "score": item.get("score", 0),
                    "stars": item.get("stars", 0),
                }
            )
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def board_summary(snapshots):
    """Headline numbers for the dashboard's stat tiles."""
    if not snapshots:
        return {}
    current = snapshots[-1]["items"]
    previous = snapshots[-2]["items"] if len(snapshots) >= 2 else []
    prev_by_name = {i["name"]: i for i in previous}

    high = [i for i in current if i.get("score", 0) >= 70]
    prev_high = [i for i in previous if i.get("score", 0) >= 70]
    fresh = [i for i in current if i["name"] not in prev_by_name]

    stars_gained = 0
    for item in current:
        prior = prev_by_name.get(item["name"])
        if prior:
            stars_gained += max(item.get("stars", 0) - prior.get("stars", 0), 0)

    velocities = sorted(i.get("velocity", 0) for i in current)
    if velocities:
        mid = len(velocities) // 2
        median_velocity = (
            velocities[mid]
            if len(velocities) % 2
            else (velocities[mid - 1] + velocities[mid]) / 2
        )
    else:
        median_velocity = 0

    # Board-level sparklines, one point per archived scan.
    spark = {"tracked": [], "high": [], "median_velocity": []}
    for snap in snapshots[-SPARK_POINTS:]:
        rows = snap["items"]
        spark["tracked"].append({"date": snap["date"], "value": len(rows)})
        spark["high"].append(
            {
                "date": snap["date"],
                "value": len([i for i in rows if i.get("score", 0) >= 70]),
            }
        )
        vels = sorted(i.get("velocity", 0) for i in rows)
        if vels:
            m = len(vels) // 2
            med = vels[m] if len(vels) % 2 else (vels[m - 1] + vels[m]) / 2
        else:
            med = 0
        spark["median_velocity"].append({"date": snap["date"], "value": round(med, 1)})

    return {
        "scans_archived": len(snapshots),
        "tracked": len(current),
        "high_conviction": len(high),
        "high_conviction_delta": len(high) - len(prev_high) if previous else None,
        "new_entries": len(fresh),
        "stars_gained": stars_gained,
        "median_velocity": round(median_velocity, 1),
        "previous_date": snapshots[-2]["date"] if len(snapshots) >= 2 else None,
        "days_since_previous": (
            days_between(snapshots[-2]["date"], snapshots[-1]["date"])
            if len(snapshots) >= 2
            else None
        ),
        "sparklines": spark,
    }


def tracked_days(item, current_date):
    """How long a repo has been on the radar, for 'tracked N days' copy."""
    if not item.get("first_seen"):
        return 0
    return days_between(item["first_seen"], current_date)
