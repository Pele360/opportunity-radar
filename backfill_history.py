"""Rebuild ``history/`` from past ``scan_data.json`` commits.

The scanner used to overwrite ``scan_data.json`` on every run, so the only
record of earlier scans is git history. This recovers them into the snapshot
store, then re-annotates the current board with the trends they unlock.

Safe to re-run: existing snapshots are left alone unless ``--force`` is passed.
"""

import argparse
import json
import os
import subprocess
import sys

import scanner
import trends

TRACKED_FILE = "scan_data.json"


def commits_touching(path):
    """Commit SHAs that changed ``path``, oldest first."""
    out = subprocess.run(
        ["git", "log", "--format=%H", "--", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return list(reversed(out))


def blob_at(commit, path):
    result = subprocess.run(
        ["git", "show", commit + ":" + path], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def backfill(force=False, history_dir=trends.HISTORY_DIR):
    recovered, skipped = [], []
    for commit in commits_touching(TRACKED_FILE):
        snap = blob_at(commit, TRACKED_FILE)
        if not snap or not snap.get("date") or not isinstance(snap.get("items"), list):
            continue
        target = os.path.join(history_dir, snap["date"] + ".json")
        if os.path.exists(target) and not force:
            skipped.append(snap["date"])
            continue
        # Store only the raw observation; trend fields are derived, never archived.
        trends.save_snapshot({"date": snap["date"], "items": snap["items"]}, history_dir)
        recovered.append(snap["date"])
    return recovered, skipped


def reannotate():
    """Refresh scan_data.json from the newest snapshot, now with history behind it."""
    snapshots = trends.load_snapshots()
    if not snapshots:
        print("no snapshots to work from", file=sys.stderr)
        return 1
    latest = snapshots[-1]
    data = scanner.build(latest["items"], latest["date"])
    with open(TRACKED_FILE, "w") as fh:
        json.dump(data, fh, indent=2)
    with open("opportunity_report.md", "w") as fh:
        fh.write(scanner.render_report(data))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="overwrite snapshots that already exist"
    )
    args = parser.parse_args()

    recovered, skipped = backfill(force=args.force)
    print("recovered " + str(len(recovered)) + " snapshot(s): " + ", ".join(recovered))
    if skipped:
        print("left alone (already present): " + ", ".join(skipped))
    return reannotate()


if __name__ == "__main__":
    sys.exit(main())
