import requests, datetime, time, sys, json, os

HEADERS = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"): HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

ECOSYSTEM_KEYWORDS = ["agent", "skill", "mcp", "claude", "template", "workflow", "automation", "llm", "assistant", "plugin", "framework", "no-code"]

def days_ago(n): return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()

def search(query, per_page=15):
    r = requests.get("https://api.github.com/search/repositories", headers=HEADERS, params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page}, timeout=30)
    r.raise_for_status()
    return r.json().get("items", [])

def velocity_of(repo):
    created = datetime.datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    age_days = max((datetime.datetime.now(datetime.timezone.utc) - created).days, 1)
    return repo["stargazers_count"] / age_days, age_days

def score_repo(repo):
    vel, age_days = velocity_of(repo)
    stars = repo["stargazers_count"]
    score = 0
    reasons = []
    if vel >= 200: score += 40; reasons.append("explosive growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 50: score += 30; reasons.append("very fast growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 10: score += 20; reasons.append("strong growth (" + str(round(vel)) + " stars/day)")
    elif vel >= 3: score += 10; reasons.append("steady growth (" + str(round(vel,1)) + " stars/day)")
    text = " ".join(filter(None, [repo.get("description") or "", " ".join(repo.get("topics", [])), repo["name"]])).lower()
    hits = [k for k in ECOSYSTEM_KEYWORDS if k in text]
    if len(hits) >= 3: score += 30; reasons.append("rich ecosystem angle (" + ", ".join(hits[:4]) + ")")
    elif len(hits) >= 1: score += 15; reasons.append("ecosystem angle (" + ", ".join(hits) + ")")
    if age_days <= 60: score += 10; reasons.append("very new (early-mover window)")
    if not repo.get("homepage"): score += 10; reasons.append("no official site yet (gap for guides/tools)")
    if stars >= 5000: score += 10
    elif stars >= 1000: score += 5
    return score, vel, reasons

def opportunity_ideas(repo):
    ideas = []
    text = ((repo.get("description") or "") + " " + repo["name"]).lower()
    if any(k in text for k in ["agent", "claude", "mcp", "assistant", "llm"]): ideas.append("Sell config/skill packs or setup guides on Gumroad"); ideas.append("Offer paid setup/integration service on Fiverr/Upwork")
    if "template" in text or "boilerplate" in text: ideas.append("Build premium template variants")
    if not ideas: ideas.append("Create a paid course/guide or complementary tool")
    return ideas

def run():
    today = datetime.date.today().isoformat()
    queries = [(f"created:>{days_ago(30)} stars:>300", "New repos, last 30 days"), (f"created:>{days_ago(90)} stars:>1000 topic:ai", "AI repos, last 90 days"), (f"created:>{days_ago(90)} stars:>500 agent OR mcp OR skill in:name,description", "Agent/MCP ecosystem")]
    seen = set()
    results = []
    for q, label in queries:
        try:
            for repo in search(q):
                if repo["full_name"] in seen: continue
                seen.add(repo["full_name"])
                s, vel, reasons = score_repo(repo)
                results.append((s, vel, repo, reasons, label))
            time.sleep(3)
        except Exception as e:
            print("warn: query failed (" + label + "): " + str(e), file=sys.stderr)
    results.sort(key=lambda x: -x[0])
    lines = ["# GitHub Opportunity Report - " + today, "", "Score = momentum + ecosystem angle + commercial gap. 60+ is worth a close look.", ""]
    for s, vel, repo, reasons, label in results[:12]:
        desc = (repo.get("description") or "No description")[:160]
        lines.append("## " + repo["full_name"] + " - Score: " + str(s) + "/100")
        lines.append("- Stars: " + str(repo["stargazers_count"]) + " | " + str(round(vel,1)) + " stars/day | Found via: " + label)
        lines.append("- What it is: " + desc)
        lines.append("- Why it scored: " + "; ".join(reasons))
        lines.append("- Money angles: " + "; ".join(opportunity_ideas(repo)))
        lines.append("- Link: " + repo["html_url"])
        lines.append("")
    report = "\n".join(lines)
    open("opportunity_report.md", "w").write(report)
    data = {"date": today, "items": [{"name": repo["full_name"], "score": s, "stars": repo["stargazers_count"], "velocity": round(vel,1), "description": (repo.get("description") or "No description")[:200], "reasons": reasons, "ideas": opportunity_ideas(repo), "url": repo["html_url"], "found_via": label} for s, vel, repo, reasons, label in results[:12]]}
    json.dump(data, open("scan_data.json", "w"), indent=2)
    print(report)

run()
