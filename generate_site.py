#!/usr/bin/env python3
"""Generates docs/index.html (the public radar page) from scan_data.json.
Monetization links are read from config.json — edit that file, never this one.
"""
import json
import html

with open("scan_data.json") as f:
      data = json.load(f)
  try:
        with open("config.json") as f:
                  cfg = json.load(f)
  except FileNotFoundError:
        cfg = {}

site_title = cfg.get("site_title", "Opportunity Radar")
tagline = cfg.get("tagline", "Fast-rising GitHub projects, scored for the money-making gaps around them. Rescans itself weekly.")
newsletter_url = cfg.get("newsletter_url", "")
premium_url = cfg.get("premium_url", "")
sponsor_email = cfg.get("sponsor_email", "")

MAX_VEL = max((i["velocity"] for i in data["items"]), default=1) or 1

def bar(v):
      pct = max(min(v / MAX_VEL * 100, 100), 2)
      return f'''<div class="track" role="img" aria-label="{v} stars per day">
        <div class="track-fill" style="width:{pct:.1f}%"></div>
      </div>'''

cards = []
for i, item in enumerate(data["items"], 1):
      ideas = "".join(f"<li>{html.escape(x)}</li>" for x in item["ideas"])
      reasons = html.escape("; ".join(item["reasons"]))
      cards.append(f'''
      <article class="card">
        <div class="card-head">
          <span class="rank">{i:02d}</span>
          <h2><a href="{html.escape(item["url"])}" target="_blank" rel="noopener">{html.escape(item["name"])}</a></h2>
          <span class="score">{item["score"]}<small>/100</small></span>
        </div>
        <p class="desc">{html.escape(item["description"])}</p>
        <div class="readout">
          <div class="readout-label">Momentum <b>{item["velocity"]:,} stars/day</b> · {item["stars"]:,} total</div>
          {bar(item["velocity"])}
        </div>
        <p class="why">{reasons}</p>
        <div class="ideas"><span>Money angles</span><ul>{ideas}</ul></div>
      </article>''')

cta_bits = []
if newsletter_url:
      cta_bits.append(f'<a class="btn" href="{html.escape(newsletter_url)}">Get this weekly by email</a>')
  if premium_url:
        cta_bits.append(f'<a class="btn btn-quiet" href="{html.escape(premium_url)}">Full deep-dive report</a>')
    if sponsor_email:
          cta_bits.append(f'<a class="btn btn-quiet" href="mailto:{html.escape(sponsor_email)}">Sponsor this radar</a>')
      cta = f'<div class="cta">{"".join(cta_bits)}</div>' if cta_bits else ""

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(site_title)} — {data["date"]}</title>
<meta name="description" content="{html.escape(tagline)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  --paper:#F5F7F2; --ink:#101915; --muted:#66746C;
    --accent:#2743E3; --line:#D8DED6; --card:#FFFFFF;
    }}
    * {{ box-sizing:border-box; margin:0; }}
    body {{
      background:var(--paper); color:var(--ink);
        font:16px/1.55 "Archivo", system-ui, sans-serif;
          background-image:
              linear-gradient(var(--line) 1px, transparent 1px),
                  linear-gradient(90deg, var(--line) 1px, transparent 1px);
                    background-size:32px 32px;
                    }}
                    .wrap {{ max-width:760px; margin:0 auto; padding:40px 20px 80px; }}
                    header {{ margin-bottom:36px; }}
                    .stamp {{
                      font:600 12px/1 "IBM Plex Mono", monospace; letter-spacing:.12em;
                        text-transform:uppercase; color:var(--accent); margin-bottom:14px;
                        }}
                        h1 {{ font-weight:800; font-size:clamp(30px,6vw,44px); letter-spacing:-.02em; }}
                        .tagline {{ color:var(--muted); margin-top:10px; max-width:52ch; }}
                        .cta {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; }}
                        .btn {{
                          background:var(--accent); color:#fff; text-decoration:none;
                            padding:10px 16px; font-weight:700; font-size:14px; border-radius:4px;
                            }}
                            .btn-quiet {{ background:transparent; color:var(--accent); border:1.5px solid var(--accent); }}
                            .card {{
                              background:var(--card); border:1.5px solid var(--ink);
                                border-radius:6px; padding:20px; margin-bottom:18px;
                                  box-shadow:4px 4px 0 var(--ink);
                                  }}
                                  .card-head {{ display:flex; align-items:baseline; gap:12px; }}
                                  .rank {{ font:600 13px "IBM Plex Mono", monospace; color:var(--muted); }}
                                  .card h2 {{ font-size:18px; font-weight:700; flex:1; min-width:0; overflow-wrap:anywhere; }}
                                  .card h2 a {{ color:var(--ink); text-decoration:none; border-bottom:2px solid var(--accent); }}
                                  .score {{ font:600 20px "IBM Plex Mono", monospace; color:var(--accent); }}
                                  .score small {{ font-size:12px; color:var(--muted); }}
                                  .desc {{ margin-top:10px; color:#2A352F; font-size:15px; }}
                                  .readout {{ margin-top:14px; }}
                                  .readout-label {{ font:400 12px "IBM Plex Mono", monospace; color:var(--muted); margin-bottom:6px; }}
                                  .readout-label b {{ color:var(--ink); font-weight:600; }}
                                  .track {{
                                    height:10px; border:1.5px solid var(--ink); border-radius:2px;
                                      background:repeating-linear-gradient(90deg, transparent 0 9px, var(--line) 9px 10px);
                                      }}
                                      .track-fill {{ height:100%; background:var(--accent); }}
                                      .why {{ margin-top:12px; font-size:13px; color:var(--muted); }}
                                      .ideas {{ margin-top:12px; border-top:1.5px dashed var(--line); padding-top:10px; }}
                                      .ideas span {{
                                        font:600 11px "IBM Plex Mono", monospace; letter-spacing:.1em;
                                          text-transform:uppercase; color:var(--accent);
                                          }}
                                          .ideas ul {{ margin:6px 0 0 18px; font-size:14px; }}
                                          footer {{ margin-top:40px; font:400 12px "IBM Plex Mono", monospace; color:var(--muted); }}
                                          @media (prefers-reduced-motion:no-preference) {{
                                            .track-fill {{ animation:grow .8s ease-out; }}
                                              @keyframes grow {{ from {{ width:0 }} }}
                                              }}
                                              </style>
                                              </head>
                                              <body>
                                              <div class="wrap">
                                                <header>
                                                    <div class="stamp">Scan date {data["date"]} · auto-updates weekly</div>
                                                        <h1>{html.escape(site_title)}</h1>
                                                            <p class="tagline">{html.escape(tagline)}</p>
                                                                {cta}
                                                                  </header>
                                                                    {"".join(cards)}
                                                                      <footer>Score = momentum + ecosystem angle + commercial gap. Data: public GitHub API.</footer>
                                                                      </div>
                                                                      </body>
                                                                      </html>'''

with open("docs/index.html", "w") as f:
      f.write(page)
  print(f"Site generated: docs/index.html ({len(data['items'])} items)")
