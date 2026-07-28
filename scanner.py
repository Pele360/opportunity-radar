"""Scan GitHub for fast-rising projects and score the commercial gaps around them.

Writes three artefacts:
  - ``scan_data.json``        current board, trend-annotated (feeds the dashboard)
  - ``opportunity_report.md`` human-readable digest
  - ``history/<date>.json``   permanent archive of this scan
"""

import datetime
import json
import os
import sys
import time

import requests

import playbook
import trends

HEADERS = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

ECOSYSTEM_KEYWORDS = [
    "agent", "skill", "mcp", "claude", "template", "workflow",
    "automation", "llm", "assistant", "plugin", "framework", "no-code",
]

# Board size. The report stays shorter than the dashboard on purpose.
MAX_ITEMS = 24
REPORT_ITEMS = 12

# A repo this quiet has lost its maintainers' attention - the window is closing.
STALE_PUSH_DAYS = 30


def days_ago(n):
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def search(query, per_page=20):
    r = requests.get(
        "https://api.github.com/search/repositories",
        headers=HEADERS,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def _parse_ts(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_eligible(repo):
    """Skip repos that can't be an opportunity: dead, mirrored, or someone's fork."""
    return not (repo.get("archived") or repo.get("disabled") or repo.get("fork"))


def repo_age_days(repo, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return max((now - _parse_ts(repo["created_at"])).days, 1)


def pushed_days_ago(repo, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    pushed = repo.get("pushed_at") or repo.get("updated_at")
    if not pushed:
        return None
    return max((now - _parse_ts(pushed)).days, 0)


def velocity_of(repo, now=None):
    age = repo_age_days(repo, now)
    return repo["stargazers_count"] / age, age


def score_repo(repo, now=None):
    """Score 0-100 and return the breakdown that produced it.

    Returns ``(score, velocity, components)`` where each component is
    ``{"label", "points", "detail"}`` so the dashboard can show its work
    instead of asking readers to trust one opaque number.
    """
    vel, age_days = velocity_of(repo, now)
    stars = repo["stargazers_count"]
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    components = []

    def add(label, points, detail):
        if points:
            components.append({"label": label, "points": points, "detail": detail})

    # 1. Momentum - how fast attention is arriving.
    if vel >= 200:
        add("Momentum", 40, "explosive growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 50:
        add("Momentum", 30, "very fast growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 10:
        add("Momentum", 20, "strong growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 3:
        add("Momentum", 10, "steady growth (" + str(round(vel, 1)) + " stars/day)")

    # 2. Ecosystem fit - does it sit in a market we can actually sell into.
    text = " ".join(
        filter(
            None,
            [
                repo.get("description") or "",
                " ".join(repo.get("topics", [])),
                repo["name"],
            ],
        )
    ).lower()
    hits = [k for k in ECOSYSTEM_KEYWORDS if k in text]
    if len(hits) >= 3:
        add("Ecosystem fit", 30, "rich ecosystem angle (" + ", ".join(hits[:4]) + ")")
    elif hits:
        add("Ecosystem fit", 15, "ecosystem angle (" + ", ".join(hits) + ")")

    # 3. Freshness - an early-mover window that has not closed yet.
    if age_days <= 60:
        add("Freshness", 10, "very new (early-mover window)")

    # 4. Commercial gap - the unmet need someone could get paid to fill.
    if not repo.get("homepage"):
        add("Commercial gap", 8, "no official site yet (gap for guides/tools)")
    if open_issues >= 40:
        add("Commercial gap", 6, str(open_issues) + " open issues (support demand)")
    if stars >= 200 and forks / max(stars, 1) >= 0.12:
        pct = round(forks / max(stars, 1) * 100)
        add("Commercial gap", 6, "high fork ratio (" + str(pct) + "% - people build on it)")
    if not repo.get("license"):
        add("Commercial gap", 4, "no license declared (integration friction to solve)")

    # 5. Reach - a large audience to sell to.
    if stars >= 5000:
        add("Reach", 10, f"{stars:,} stars")
    elif stars >= 1000:
        add("Reach", 5, f"{stars:,} stars")

    # 6. Maintenance risk - a stalling repo is a closing window, not an opening one.
    stale = pushed_days_ago(repo, now)
    if stale is not None and stale > STALE_PUSH_DAYS:
        add("Maintenance risk", -10, "no push in " + str(stale) + " days (stalling)")

    score = max(0, min(sum(c["points"] for c in components), 100))
    return score, vel, components


def opportunity_ideas(repo):
    """Concrete ways to get paid around this repo, keyed off its actual shape."""
    ideas = []
    text = (
        (repo.get("description") or "")
        + " "
        + repo["name"]
        + " "
        + " ".join(repo.get("topics") or [])
    ).lower()
    stars = repo["stargazers_count"]
    forks = repo.get("forks_count", 0)

    if "mcp" in text:
        ideas.append("Publish a hosted MCP endpoint or a curated server directory")
    if any(k in text for k in ["agent", "claude", "assistant", "llm", "skill"]):
        ideas.append("Sell config/skill packs or setup guides on Gumroad")
        ideas.append("Offer paid setup/integration service on Fiverr/Upwork")
    if any(k in text for k in ["template", "boilerplate", "starter"]):
        ideas.append("Build premium template variants")
    if not repo.get("homepage") and stars >= 1000:
        ideas.append("Run the unofficial docs site while the project has none")
    if repo.get("open_issues_count", 0) >= 40:
        ideas.append("Paid support tier or office hours for teams adopting it")
    if stars >= 200 and forks / max(stars, 1) >= 0.12:
        ideas.append("Sell a hardened fork or managed hosting")
    if not ideas:
        ideas.append("Create a paid course/guide or complementary tool")

    # Preserve order, drop repeats.
    return list(dict.fromkeys(ideas))


def queries():
    return [
        (f"created:>{days_ago(30)} stars:>300", "New repos, last 30 days"),
        (f"created:>{days_ago(90)} stars:>1000 topic:ai", "AI repos, last 90 days"),
        (
            f"created:>{days_ago(90)} stars:>500 agent OR mcp OR skill in:name,description",
            "Agent/MCP ecosystem",
        ),
        (
            f"created:>{days_ago(180)} stars:>800 topic:developer-tools",
            "Developer tooling, last 180 days",
        ),
    ]


def collect(now=None):
    """Run every query and return scored, de-duplicated results, best first."""
    seen = set()
    results = []
    failures = 0
    for q, label in queries():
        try:
            for repo in search(q):
                if repo["full_name"] in seen or not is_eligible(repo):
                    continue
                seen.add(repo["full_name"])
                score, vel, components = score_repo(repo, now)
                results.append((score, vel, repo, components, label))
            time.sleep(3)
        except Exception as e:  # one bad query must not lose the whole scan
            failures += 1
            print("warn: query failed (" + label + "): " + str(e), file=sys.stderr)
    results.sort(key=lambda x: -x[0])
    return results, failures


def to_item(score, vel, repo, components, label, now=None):
    return {
        "name": repo["full_name"],
        "score": score,
        "score_components": components,
        "reasons": [c["detail"] for c in components],
        "stars": repo["stargazers_count"],
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "velocity": round(vel, 1),
        "age_days": repo_age_days(repo, now),
        "pushed_days_ago": pushed_days_ago(repo, now),
        "language": repo.get("language"),
        "topics": (repo.get("topics") or [])[:6],
        "homepage": repo.get("homepage") or "",
        "description": (repo.get("description") or "No description")[:200],
        "ideas": opportunity_ideas(repo),
        "url": repo["html_url"],
        "found_via": label,
    }


def render_report(data):
    summary = data.get("summary", {})
    lines = [
        "# GitHub Opportunity Report - " + data["date"],
        "",
        "Score = momentum + ecosystem angle + commercial gap - maintenance risk. "
        "60+ is worth a close look.",
        "",
    ]
    if summary.get("previous_date"):
        lines += [
            "Since {}: {} new entries, {:,} stars gained across the board.".format(
                summary["previous_date"],
                summary.get("new_entries", 0),
                summary.get("stars_gained", 0),
            ),
            "",
        ]

    focus = data.get("focus")
    if focus:
        lines += ["## Today's pick: " + focus["name"], "", focus["why_now"], ""]
        if focus.get("play"):
            lines.append("Play - " + focus["play"]["title"] + ":")
            for i, step in enumerate(focus["play"]["steps"], 1):
                lines.append(str(i) + ". " + step)
            lines.append("")

    if data.get("daily_loop"):
        lines += [
            "## The daily loop ({} minutes)".format(data.get("loop_minutes", 0)),
            "",
        ]
        for step in data["daily_loop"]:
            lines.append(
                "- **{}** ({} min) - {}".format(
                    step["step"], step["minutes"], step["detail"]
                )
            )
        lines.append("")

    lines += ["## The board", ""]

    for item in data["items"][:REPORT_ITEMS]:
        lines.append("## " + item["name"] + " - Score: " + str(item["score"]) + "/100")
        movement = item.get("status", "new")
        delta = item.get("star_delta")
        if delta is not None:
            movement += " ({:+,} stars vs {})".format(delta, item.get("compared_to"))
        lines.append(
            "- Stars: {:,} | {} stars/day | {}".format(
                item["stars"], item["velocity"], movement
            )
        )
        lines.append("- Found via: " + item["found_via"])
        lines.append("- What it is: " + item["description"][:160])
        lines.append("- Why it scored: " + "; ".join(item["reasons"]))
        lines.append("- Money angles: " + "; ".join(item["ideas"]))
        if item.get("play"):
            lines.append(
                "- Next move: " + item["play"]["title"] + " - " + item["play"]["steps"][0]
            )
        lines.append("- Link: " + item["url"])
        lines.append("")

    gone = data.get("departed", [])
    if gone:
        lines += ["## Dropped off the board", ""]
        for g in gone:
            lines.append("- " + g["name"] + " (was " + str(g["score"]) + "/100)")
        lines.append("")

    return "\n".join(lines)


def build(items, today):
    """Archive, annotate and assemble the board. Shared by the scan and backfill."""
    data = {"date": today, "items": items}
    trends.save_snapshot(data)
    snapshots = trends.load_snapshots()
    trends.annotate(items, snapshots)
    data["departed"] = trends.departed(snapshots)
    data["summary"] = trends.board_summary(snapshots)
    # Trends must land before the playbook - today's pick depends on status.
    playbook.build(data)
    return data


def run():
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now(datetime.timezone.utc)
    results, failures = collect(now)

    if not results:
        print(
            "error: every query failed - refusing to overwrite the existing board",
            file=sys.stderr,
        )
        return 1

    items = [to_item(s, v, r, c, l, now) for s, v, r, c, l in results[:MAX_ITEMS]]
    data = build(items, today)
    data["query_failures"] = failures

    with open("scan_data.json", "w") as fh:
        json.dump(data, fh, indent=2)

    report = render_report(data)
    with open("opportunity_report.md", "w") as fh:
        fh.write(report)

    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(run())
