import json, html, os

data = json.load(open("scan_data.json"))
cfg = json.load(open("config.json")) if os.path.exists("config.json") else {}


links = ""
if news:
    links += "<a class='btn' href='" + html.escape(news) + "'>Get this weekly by email</a>"
if prem:
    links += "<a class='btn' href='" + html.escape(prem) + "'>Full deep-dive report</a>"
if spons:
    links += "<a class='btn' href='mailto:" + html.escape(spons) + "'>Sponsor this radar</a>"
parts.append(links)
for i, it in enumerate(items, 1):
    pct = max(min(it["velocity"] / maxv * 100, 100), 2)
    ideas_html = "".join("<li>" + html.escape(x) + "</li>" for x in it["ideas"])
    reasons = html.escape("; ".join(it["reasons"]))
    card = "<div class='card'>"
    card += "<b>" + str(i).zfill(2) + "</b> "
    card += "<a href='" + html.escape(it["url"]) + "'>" + html.escape(it["name"]) + "</a> "
    card += "<span class='score'>" + str(it["score"]) + "/100</span>"
    card += "<p>" + html.escape(it["description"]) + "</p>"
    card += "<div>Momentum: " + str(it["velocity"]) + " stars/day (" + str(it["stars"]) + " total)</div>"
    card += "<div class='bar'><div class='fill' style='width:" + str(round(pct,1)) + "%'></div></div>"
    card += "<p style='color:#66746C;font-size:13px'>" + reasons + "</p>"
    card += "<b>Money angles</b><ul>" + ideas_html + "</ul>"
    card += "</div>"
    parts.append(card)

parts.append("<footer>Score = momentum + ecosystem angle + commercial gap. Data: public GitHub API.</footer>")
parts.append("</body></html>")

os.makedirs("docs", exist_ok=True)
open("docs/index.html", "w").write("".join(parts))
print("Site generated: docs/index.html (" + str(len(items)) + " items)")
title = cfg.get("site_title", "Opportunity Radar")
tagline = cfg.get("tagline", "Fast-rising GitHub projects, scored for the money-making gaps around them.")
news = cfg.get("newsletter_url", "")
prem = cfg.get("premium_url", "")
spons = cfg.get("sponsor_email", "")
items = data["items"]
maxv = max([x["velocity"] for x in items] or [1])

CSS = "body{font-family:Arial,sans-serif;background:#F5F7F2;color:#101915;max-width:760px;margin:0 auto;padding:40px 20px}"
CSS += ".card{background:#fff;border:2px solid #101915;border-radius:6px;padding:20px;margin-bottom:18px}"
CSS += ".score{color:#2743E3;font-weight:bold;font-size:20px}"
CSS += ".bar{height:10px;background:#D8DED6;border:1px solid #101915;border-radius:2px}"
CSS += ".fill{height:100%;background:#2743E3}"
CSS += "a.btn{background:#2743E3;color:#fff;text-decoration:none;padding:10px 16px;border-radius:4px;margin-right:8px;font-weight:bold}"

parts = []
parts.append("<!doctype html><html><head><meta charset='utf-8'>")
parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
parts.append("<title>" + html.escape(title) + "</title>")
parts.append("<style>" + CSS + "</style></head><body>")
parts.append("<div style='color:#2743E3;font-weight:bold'>Scan date " + data["date"] + " - auto-updates weekly</div>")
parts.append("<h1>" + html.escape(title) + "</h1>")
parts.append("<p>" + html.escape(tagline) + "</p>")
