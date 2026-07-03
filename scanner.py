#!/usr/bin/env python3
"""
GitHub Opportunity Scanner
Finds fast-rising repos and scores them for monetizable gaps.
Run anytime: python3 scanner.py
No API key needed (uses public GitHub API, rate-limited but sufficient).
"""

import requests
import datetime
import time
import sys
import json
import os

API = "https://api.github.com/search/repositories"
HEADERS = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"):
      HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

ECOSYSTEM_KEYWORDS = [
      "agent", "skill", "mcp", "claude", "template", "workflow",
      "automation", "llm", "assistant", "plugin", "framework", "no-code"
]

def days_ago(n):
      return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()

def search(query, sort="stars", per_page=15):
      r = requests.get(API, headers=HEADERS, params={
                "q": query, "sort": sort, "order": "desc", "per_page": per_page
      }, timeout=30)
      r.raise_for_status()
      return r.json().get("items", [])

def score_repo(repo):
      created = datetime.datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
      age_days = max((datetime.datetime.now(datetime.timezone.utc) - created).days, 1)
      stars = repo["stargazers_count"]
      velocity = stars / age_days

    score = 0
    reasons = []

    if velocity >= 200: score += 40; reasons.append(f"explosive growth ({velocity:.0f} stars/day)")
elif velocity >= 50: score += 30; reasons.append(f"very fast growth ({velocity:.0f} stars/day)")
elif velocity >= 10: score += 20; reasons.append(f"strong growth ({velocity:.0f} stars/day)")
elif velocity >= 3: score += 10; reasons.append(f"steady growth ({velocity:.1f} stars/day)")

    text = " ".join(filter(None, [repo.get("description") or "", " ".join(repo.get("topics", [])), repo["name"]])).lower()
    hits = [k for k in ECOSYSTEM_KEYWORDS if k in text]
    if len(hits) >= 3: score += 30; reasons.append(f"rich ecosystem angle ({', '.join(hits[:4])})")
elif len(hits) >= 1: score += 15; reasons.append(f"ecosystem angle ({', '.join(hits)})")

    if age_days <= 60: score += 10; reasons.append("very new (early-mover window)")
          if not repo.get("homepage"): score += 10; reasons.append("no official site yet (gap for guides/tools)")

    if stars >= 5000: score += 10
elif stars >= 1000: score += 5

    return score, velocity, reasons

def opportunity_ideas(repo, reasons):
      ideas = []
      text = ((repo.get("description") or "") + " " + repo["name"]).lower()
      if any(k in text for k in ["agent", "claude", "mcp", "assistant", "llm"]):
                ideas.append("Sell config/skill packs or setup guides on Gumroad")
                ideas.append("Offer paid setup/integration service on Fiverr/Upwork")
            if "template" in text or "boilerplate" in text:
                      ideas.append("Build premium template variants")
                  if not ideas:
                            ideas.append("Create a paid course/guide or complementary tool")
                        return ideas

def run():
      today = datetime.date.today().isoformat()
    queries = [
              (f"created:>{days_ago(30)} stars:>300", "New repos, last 30 days"),
              (f"created:>{days_ago(90)} stars:>1000 topic:ai", "AI repos, last 90 days"),
              (f"created:>{days_ago(90)} stars:>500 agent OR mcp OR skill in:name,description", "Agent/MCP ecosystem"),
    ]

    seen, results = set(), []
    for q, label in queries:
              try:
                            for repo in search(q):
                                              if repo["full_name"] in seen:
                                                                    continue
                                                                seen.add(repo["full_name"])
                                              s, vel, reasons = score_repo(repo)
                                              results.append((s, vel, repo, reasons, label))
                                          time.sleep(3)
except Exception as e:
            print(f"[warn] query failed ({label}): {e}", file=sys.stderr)

    results.sort(key=lambda x: -x[0])

    lines = [f"# GitHub Opportunity Report — {today}\n"]
    lines.append("Score = momentum + ecosystem angle + commercial gap. 60+ is worth a close look.\n")
    for s, vel, repo, reasons, label in results[:12]:
              lines.append(f"## {repo['full_name']}  —  Score: {s}/100")
              lines.append(f"- Stars: {repo['stargazers_count']:,}  |  {vel:.1f} stars/day  |  Found via: {label}")
              desc = (repo.get('description') or 'No description')[:160]
              lines.append(f"- What it is: {desc}")
              lines.append(f"- Why it scored: {'; '.join(reasons)}")
              lines.append(f"- Money angles: {'; '.join(opportunity_ideas(repo, reasons))}")
              lines.append(f"- Link: {repo['html_url']}\n")

    report = "\n".join(lines)
    with open("opportunity_report.md", "w") as f:
              f.write(report)

    data = {"date": today, "items": []}
    for s, vel, repo, reasons, label in results[:12]:
              data["items"].append({
                            "name": repo["full_name"],
                            "score": s,
                            "stars": repo["stargazers_count"],
                            "velocity": round(vel, 1),
                            "description": (repo.get("description") or "No description")[:200],
                            "reasons": reasons,
                            "ideas": opportunity_ideas(repo, reasons),
                            "url": repo["html_url"],
                            "found_via": label,
              })
          with open("scan_data.json", "w") as f:
                    json.dump(data, f, indent=2)
                print(report)

if __name__ == "__main__":
      run()
