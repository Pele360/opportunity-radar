"""Turn a scored opportunity into today's concrete moves.

A score tells you *what* is rising. This module answers the only question that
follows: what do I actually do about it in the next 90 minutes, and what does
the week after that look like if it works.
"""

# The daily loop, independent of which opportunity is on top. One pass a day.
DAILY_LOOP = [
    {
        "step": "Read the board",
        "minutes": 5,
        "detail": "Open the radar. Look only at New and Accelerating - "
        "steady and cooling entries are yesterday's news.",
    },
    {
        "step": "Pick exactly one",
        "minutes": 5,
        "detail": "Highest score you have not already worked. One per day. "
        "Two is zero.",
    },
    {
        "step": "Check the gap is real",
        "minutes": 20,
        "detail": "Open the repo's issues and discussions. Search the name on "
        "Reddit and X. You want people asking for the thing you'd sell.",
    },
    {
        "step": "Ship the smallest sellable version",
        "minutes": 60,
        "detail": "One page, one config pack, one guide. If it cannot be done "
        "in an hour, it is the wrong first version.",
    },
    {
        "step": "Put it where the demand already is",
        "minutes": 15,
        "detail": "Reply in the issue thread you found, post it where you saw "
        "the question. Distribution on day one, not day ten.",
    },
    {
        "step": "Log the result",
        "minutes": 5,
        "detail": "Shipped what, posted where, any response. Kill anything with "
        "zero signal after three days.",
    },
]

# Which money angle to lead with, in priority order, given what the repo shows.
ANGLE_PLAYS = [
    (
        "docs",
        lambda it: not it.get("homepage") and it.get("stars", 0) >= 1000,
        "Unofficial docs site",
        [
            "Register a clear domain and put up a single quickstart page",
            "Cover the three things the README does not: install gotchas, a real config, one worked example",
            "Link it from the repo's issues where people ask those exact questions",
            "Add an email capture; that list is the asset, not the page",
        ],
    ),
    (
        "support",
        lambda it: it.get("open_issues", 0) >= 40,
        "Paid support and setup",
        [
            "Read the last 30 open issues and group them into three recurring problems",
            "Write the fix for the most common one publicly, for free",
            "Add one line at the end offering paid setup, with a price",
            "Take the first three clients at half price to build proof",
        ],
    ),
    (
        "packs",
        lambda it: any(
            k in (it.get("description", "") + " " + it.get("name", "")).lower()
            for k in ("agent", "claude", "skill", "mcp", "assistant", "llm")
        ),
        "Config / skill pack",
        [
            "Build the setup you would want on day one and use it yourself first",
            "Package it with a README and a 3-minute screen recording",
            "List it on Gumroad at a low double-digit price",
            "Post the free half publicly; sell the complete version",
        ],
    ),
    (
        "hosting",
        lambda it: it.get("stars", 0) >= 200
        and it.get("forks", 0) / max(it.get("stars", 1), 1) >= 0.12,
        "Hardened fork or managed hosting",
        [
            "Diff the popular forks - the common patches are the unmet need",
            "Roll them into one maintained build with a changelog",
            "Offer a hosted version for people who do not want to run it",
            "Charge monthly, not once",
        ],
    ),
    (
        "course",
        lambda it: True,
        "Paid guide or complementary tool",
        [
            "Write the tutorial you needed and could not find",
            "Publish it free to prove the demand exists",
            "Turn the follow-up questions into the paid version",
            "Ship the small tool those questions keep pointing at",
        ],
    ),
]


def pick_play(item):
    """Choose the single angle to lead with for this repo."""
    for key, applies, title, steps in ANGLE_PLAYS:
        if applies(item):
            return {"key": key, "title": title, "steps": steps}
    return None


def why_now(item):
    """One sentence on why this is today's pick rather than any other day's."""
    status = item.get("status", "new")
    if status == "new":
        return "First appearance on the board - nobody has built around it yet."
    if status == "accelerating":
        pct = item.get("star_delta_pct_per_day")
        rate = f" ({pct}%/day)" if pct is not None else ""
        return "Still speeding up" + rate + " - the audience is arriving now."
    if status == "cooling":
        return "Cooling off - only worth it if you already have something half-built."
    return "Holding steady - a slower window, but a safer one."


def focus_for(items):
    """Today's single pick: the best entry whose window is still open."""
    candidates = [i for i in items if i.get("status") in ("new", "accelerating")]
    pool = candidates or items
    if not pool:
        return None
    best = max(pool, key=lambda i: (i.get("score", 0), i.get("velocity", 0)))
    play = pick_play(best)
    return {
        "name": best["name"],
        "url": best["url"],
        "score": best["score"],
        "status": best.get("status", "new"),
        "why_now": why_now(best),
        "play": play,
    }


def build(data):
    """Attach the daily plan to a board."""
    items = data.get("items", [])
    for item in items:
        item["play"] = pick_play(item)
        item["why_now"] = why_now(item)
    data["focus"] = focus_for(items)
    data["daily_loop"] = DAILY_LOOP
    data["loop_minutes"] = sum(s["minutes"] for s in DAILY_LOOP)
    return data
