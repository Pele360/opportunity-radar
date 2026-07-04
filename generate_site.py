import json, html, os
data = json.load(open("scan_data.json"))
cfg = json.load(open("config.json")) if os.path.exists("config.json") else {}
title = cfg.get("site_title", "Opportunity Radar")
tagline = cfg.get("tagline", "Fast-rising GitHub projects, scored for the money-making gaps around them.")
news = cfg.get("newsletter_url", "")
prem = cfg.get("premium_url", "")
spons = cfg.get("sponsor_email", "")
items = data["items"]
maxv = max([x["velocity"] for x in items] or [1])
CSS = "body{font-family:Arial,sans-serif;background:#F5F7F2;color:#101915;max-width:760px;margin:0 auto;padding:40px 20px}.card{background:#fff;border:2px solid #101915;border-radius:6px;padding:20px;margin-bottom:18px}.score{color:#2743E3;font-weight:bold;font-size:20px}.bar{height:10px;background:#D8DED6;border:1px solid #101915;border-radius:2px}.fill{height:100%;background:#2743E3}a.btn{background:#2743E3;color:#fff;text-decoration:none;padding:10px 16px;border-radius:4px;margin-right:8px;font-weight:bold}"
link_news = ("<a class='btn' href='" + html.escape(news) + "'>Get this weekly by email</a>") if news else ""
link_prem = ("<a class='btn' href='" + html.escape(prem) + "'>Full deep-dive report</a>") if prem else ""
link_spons = ("<a class='btn' href='mailto:" + html.escape(spons) + "'>Sponsor this radar</a>") if spons else ""
links = link_news + link_prem + link_spons
def make_card(i, it): pct = max(min(it["velocity"] / maxv * 100, 100), 2); ideas_html = "".join(["<li>" + html.escape(x) + "</li>" for x in it["ideas"]]); reasons = html.escape("; ".join(it["reasons"])); return "<div class='card'><b>" + str(i).zfill(2) + "</b> <a href='" + html.escape(it["url"]) + "'>" + html.escape(it["name"]) + "</a> <span class='score'>" + str(it["score"]) + "/100</span><p>" + html.escape(it["description"]) + "</p><div>Momentum: " + str(it["velocity"]) + " stars/day (" + str(it["stars"]) + " total)</div><div class='bar'><div class='fill' style='width:" + str(round(pct,1)) + "%'></div></div><p style='color:#66746C;font-size:13px'>" + reasons + "</p><b>Money angles</b><ul>" + ideas_html + "</ul></div>"
cards_html = "".join([make_card(i, it) for i, it in enumerate(items, 1)])
header = "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>" + html.escape(title) + "</title><style>" + CSS + "</style></head><body>"
header += "<div style='color:#2743E3;font-weight:bold'>Scan date " + data["date"] + " - auto-updates weekly</div><h1>" + html.escape(title) + "</h1><p>" + html.escape(tagline) + "</p>" + links
footer = "<footer>Score = momentum + ecosystem angle + commercial gap. Data: public GitHub API.</footer></body></html>"
page = header + cards_html + footer
os.makedirs("docs", exist_ok=True)
open("docs/index.html", "w").write(page)
print("Site generated: docs/index.html (" + str(len(items)) + " items)")
