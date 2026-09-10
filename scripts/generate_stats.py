#!/usr/bin/env python3
"""
GitHub Profile Stats Generator — "Mission Control" redesign
Generates dark + light versions of: stats, streak, langs cards.
All numbers are REAL (GitHub GraphQL API). No fake fallback data —
but if the API call fails, an "unavailable" placeholder card is
still written so the workflow doesn't fail and the README doesn't
break.
Theme switching is done in README via <picture> + prefers-color-scheme.
"""

import os
import sys
import math
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("GITHUB_USER", "Hiten1896")
API_URL = "https://api.github.com/graphql"

# ─────────────────────────────────────────────
# THEMES — richer, more saturated "mission control" palette
# ─────────────────────────────────────────────
THEMES = {
    "dark": {
        "BG":      "#05070d",
        "PANEL":   "#0a0e1a",
        "PANEL2":  "#0d1220",
        "BORDER":  "#1c2333",
        "GRID":    "#141a2a",
        "TEXT":    "#eef2ff",
        "MUTED":   "#7684a3",
        "GREEN":   "#2fe6a8",
        "RED":     "#ff5f7e",
        "CYAN":    "#3ee8ff",
        "VIOLET":  "#a78bfa",
        "AMBER":   "#ffb454",
        "PINK":    "#ff7ad9",
        "BLUE":    "#5b8cff",
        "HEAT":    ["#141a2a", "#123b45", "#0d6a75", "#12aebd", "#3ee8ff"],
        "GLOW":    "#3ee8ff",
    },
    "light": {
        "BG":      "#ffffff",
        "PANEL":   "#f9fafc",
        "PANEL2":  "#f1f3f9",
        "BORDER":  "#dbe1ee",
        "GRID":    "#e9ecf5",
        "TEXT":    "#141a2e",
        "MUTED":   "#5b6788",
        "GREEN":   "#0f9d6b",
        "RED":     "#e0355b",
        "CYAN":    "#0894b3",
        "VIOLET":  "#7c5cea",
        "AMBER":   "#c9791a",
        "PINK":    "#d4459a",
        "BLUE":    "#3059d9",
        "HEAT":    ["#eef1f8", "#bfe6ec", "#7dcedd", "#2fabc4", "#0894b3"],
        "GLOW":    "#0894b3",
    },
}

FONT_FAMILY = "'Segoe UI', 'JetBrains Mono', monospace"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Vue": "#41b883", "Shell": "#89e051",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "Go": "#00ADD8",
    "Rust": "#dea584", "Jupyter Notebook": "#DA5B0B", "Dart": "#00B4AB",
    "Kotlin": "#A97BFF", "PHP": "#4F5D95", "Ruby": "#701516", "Other": "#8b949e",
}


def css(theme):
    return f"text {{ font-family: {FONT_FAMILY}; }}"


def esc(text):
    """Escape XML-special characters for safe embedding in SVG text nodes."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def truncate(text, max_chars):
    """Truncate then escape — all text passed through here is safe to embed."""
    text = str(text)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "\u2026"
    return esc(text)


def header(T, w, h, title, accent, subtitle=""):
    """Mission-control style header: hex badge + title, no traffic-light
    chrome — replaces the old 'editor window' look entirely."""
    return f"""
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="{T['PANEL']}" stroke="{T['BORDER']}"/>
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="14" fill="url(#edgeGlow)" opacity="0.5"/>
  <g transform="translate(24, 22)">
    <polygon points="9,0 18,5 18,15 9,20 0,15 0,5" fill="none" stroke="{accent}" stroke-width="1.6"/>
    <circle cx="9" cy="10" r="2.6" fill="{accent}"/>
  </g>
  <text x="46" y="28" font-size="12.5" font-weight="800" letter-spacing="0.3" fill="{T['TEXT']}">{esc(title)}</text>
  <text x="46" y="41" font-size="8.5" letter-spacing="0.5" fill="{T['MUTED']}">{esc(subtitle)}</text>
  <line x1="24" y1="52" x2="{w-24}" y2="52" stroke="{T['BORDER']}"/>"""


def defs_block(T):
    return f"""<defs>
  <radialGradient id="edgeGlow" cx="15%" cy="0%" r="80%">
    <stop offset="0%" stop-color="{T['GLOW']}" stop-opacity="0.10"/>
    <stop offset="100%" stop-color="{T['GLOW']}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{T['CYAN']}" stop-opacity="0.32"/>
    <stop offset="100%" stop-color="{T['CYAN']}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="{T['CYAN']}"/>
    <stop offset="100%" stop-color="{T['VIOLET']}"/>
  </linearGradient>
</defs>"""


# ─────────────────────────────────────────────
# DATA FETCH (real data only)
# ─────────────────────────────────────────────
def fetch_github_stats():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set")

    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=365)

    query = f"""
    query {{
      user(login: "{USERNAME}") {{
        name
        createdAt
        followers {{ totalCount }}
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
          totalCount
          nodes {{
            stargazerCount
            forkCount
            languages(first: 100) {{
              edges {{ size node {{ name }} }}
            }}
          }}
        }}
        contributionsCollection(
          from: "{from_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}",
          to: "{to_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}") {{
          totalCommitContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalIssueContributions
          contributionCalendar {{
            weeks {{
              contributionDays {{ date contributionCount weekday }}
            }}
          }}
        }}
      }}
    }}"""

    try:
        resp = requests.post(
            API_URL, json={"query": query},
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}"}, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if "errors" in result or result.get("data", {}).get("user") is None:
            raise RuntimeError(f"GitHub GraphQL error: {result.get('errors')}")
        return parse_graphql_response(result["data"]["user"])
    except Exception as e:
        raise RuntimeError(f"GitHub API request failed: {e}") from e


def parse_graphql_response(user):
    days = []
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        if not week:
            continue
        for d in week["contributionDays"]:
            if not d:
                continue
            days.append({"date": d["date"], "count": d["contributionCount"],
                         "weekday": d["weekday"]})
    days.sort(key=lambda x: x["date"])

    repos = [repo for repo in user["repositories"]["nodes"] if repo]
    created = datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    lang = defaultdict(int)
    for r in repos:
        for edge in r.get("languages", {}).get("edges", []):
            language = edge.get("node") or {}
            if language.get("name") and edge.get("size"):
                lang[language["name"]] += edge["size"]

    return {
        "name": user.get("name") or USERNAME,
        "username": USERNAME,
        "followers": user["followers"]["totalCount"],
        "total_repos": user["repositories"]["totalCount"],
        "total_stars": sum(r["stargazerCount"] for r in repos),
        "total_forks": sum(r["forkCount"] for r in repos),
        "account_age_years": round((datetime.now(timezone.utc) - created).days / 365.25, 1),
        "total_commits": user["contributionsCollection"]["totalCommitContributions"],
        "total_prs": user["contributionsCollection"]["totalPullRequestContributions"],
        "total_reviews": user["contributionsCollection"]["totalPullRequestReviewContributions"],
        "total_issues": user["contributionsCollection"]["totalIssueContributions"],
        "total_conts": sum(day["count"] for day in days),
        "days": days,
        "langs": lang,
    }


# ─────────────────────────────────────────────
# CALCULATIONS
# ─────────────────────────────────────────────
def calculate_rank(data):
    total = data["total_conts"]
    active = sum(1 for d in data["days"] if d["count"] > 0)
    score = min(100, (total / 20) + (active / 3.65))
    if score >= 85: return "S", "TOP 2%",  score
    if score >= 70: return "A", "TOP 8%",  score
    if score >= 55: return "B", "TOP 25%", score
    if score >= 40: return "C", "TOP 45%", score
    return "D", "TOP 70%", score


def calculate_streak(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)

    current = 0
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        elif current > 0:
            break

    long_range = curr_range = "-"
    longest_end, run = None, 0
    for i, d in enumerate(days):
        run = run + 1 if d["count"] > 0 else 0
        if run == longest:
            longest_end = i
    if longest_end is not None and longest > 0:
        s = datetime.strptime(days[longest_end - longest + 1]["date"], "%Y-%m-%d")
        e = datetime.strptime(days[longest_end]["date"], "%Y-%m-%d")
        long_range = f"{s.strftime('%d %b')} \u2192 {e.strftime('%d %b')}"
    if current > 0 and days:
        e = datetime.strptime(days[-1]["date"], "%Y-%m-%d")
        s = e - timedelta(days=current - 1)
        curr_range = f"{s.strftime('%d %b')} \u2192 {e.strftime('%d %b')}"

    best = max(days, key=lambda x: x["count"]) if days else {"count": 0, "date": None}
    best_date = datetime.strptime(best["date"], "%Y-%m-%d").strftime("%d %b") if best["date"] else None

    active_days = sum(1 for d in days if d["count"] > 0)
    total = sum(d["count"] for d in days)
    avg = round(total / active_days, 1) if active_days else 0

    return {"current_streak": current, "longest_streak": longest,
            "long_range": long_range, "curr_range": curr_range,
            "best_day_count": best["count"], "best_day_date": best_date,
            "total_active": active_days, "avg_per_active_day": avg}


def calculate_activity_insights(days):
    max_gap = curr_gap = 0
    for d in days:
        curr_gap = curr_gap + 1 if d["count"] == 0 else 0
        max_gap = max(max_gap, curr_gap)

    all_total = sum(d["count"] for d in days) or 1
    weekend_pct = round(sum(d["count"] for d in days if d["weekday"] in (0, 6)) / all_total * 100)

    month_totals = defaultdict(int)
    for d in days:
        month_totals[d["date"][:7]] += d["count"]
    busiest_name, busiest_count = "-", 0
    if month_totals:
        mk, busiest_count = max(month_totals.items(), key=lambda x: x[1])
        busiest_name = datetime.strptime(mk, "%Y-%m").strftime("%B")

    wd = defaultdict(int)
    for d in days:
        wd[d["weekday"]] += d["count"]
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    top_weekday = names[max(wd, key=wd.get)] if wd else "-"

    return {"longest_gap": max_gap, "weekend_pct": weekend_pct,
            "busiest_month": busiest_name, "busiest_month_count": busiest_count,
            "top_weekday": top_weekday}


def render_heatmap(T, days, max_w, max_h):
    """Same flat grid, but cells are diamonds/rounded-squares with a subtle
    glow on the hottest days for a more 'radar' feel."""
    if not days:
        return "", 0, 0

    base = datetime.strptime(days[0]["date"], "%Y-%m-%d").date()
    week_cols = defaultdict(list)
    for d in days:
        wk = (datetime.strptime(d["date"], "%Y-%m-%d").date() - base).days // 7
        week_cols[wk].append(d)

    max_weeks = max(week_cols.keys()) + 1 if week_cols else 1
    rows = 7

    gap_ratio = 0.26
    cell_w = max_w / (max_weeks + max_weeks * gap_ratio)
    cell_h = max_h / (rows + rows * gap_ratio)
    cell = max(2.0, min(cell_w, cell_h, 8.0))
    gap = cell * gap_ratio

    def color(c):
        if c == 0: return T["HEAT"][0]
        if c <= 3: return T["HEAT"][1]
        if c <= 6: return T["HEAT"][2]
        if c <= 9: return T["HEAT"][3]
        return T["HEAT"][4]

    rects = []
    for wk in range(max_weeks):
        for pos, d in enumerate(week_cols.get(wk, [])):
            hot = d["count"] > 9
            glow = f' filter="url(#dotGlow)"' if hot else ""
            rects.append(f'<rect x="{wk*(cell+gap):.1f}" y="{pos*(cell+gap):.1f}" '
                         f'width="{cell:.1f}" height="{cell:.1f}" rx="{cell*0.3:.1f}" fill="{color(d["count"])}"{glow}/>')

    total_w = max_weeks * (cell + gap) - gap
    total_h = rows * (cell + gap) - gap
    return "".join(rects), total_w, total_h


# ─────────────────────────────────────────────
# CARD 1: STATS — radial "mission control" layout
# ─────────────────────────────────────────────
def generate_stats_svg(data, T):
    w, h = 560, 300
    rank_letter, rank_pct, score = calculate_rank(data)
    pct = max(0, min(100, round(score)))

    days = data["days"]
    weekly = [sum(days[i]["count"] for i in range(s, min(s+7, len(days))))
              for s in range(0, max(1, len(days)-6), 7)]
    last20 = weekly[-20:] if len(weekly) >= 20 else weekly
    smax = max(last20) or 1
    n = max(1, len(last20))

    # Sparkline as vertical glow-bars instead of an area/line chart —
    # sits behind the metric strip like an EQ readout.
    gx, gy, gw, gh = 300, 66, 232, 150
    bar_gap = 3
    bar_w = (gw - bar_gap * (n - 1)) / n if n > 0 else gw
    bars = []
    for i, v in enumerate(last20):
        bh = max(3, (v / smax) * gh)
        bx = gx + i * (bar_w + bar_gap)
        by = gy + gh - bh
        t = i / max(1, n - 1)
        col = T["CYAN"] if t < 0.5 else T["VIOLET"]
        bars.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="{bar_w/2:.1f}" fill="{col}" opacity="{0.35+0.65*t:.2f}"/>')

    # Rank ring — bigger, gradient stroke, left-of-center focal point.
    rr, cx, cy = 54, 94, 128
    circ = 2 * math.pi * rr
    offset = circ * (1 - pct / 100)

    metrics = [
        ("STARS",     data["total_stars"], T["AMBER"],  "across repos"),
        ("PULL REQS", data["total_prs"],   T["VIOLET"], f"{data['total_reviews']} reviews"),
        ("FOLLOWERS", data["followers"],   T["CYAN"],   f"{data['account_age_years']}y on GitHub"),
        ("REPOS",     data["total_repos"], T["PINK"],   f"{data['total_forks']} forks"),
    ]
    profile_subtitle = esc(f"@{data['username']} {chr(0x00B7)} profile overview")
    strip_y = 254
    col_w = (w - 56) / 4
    cells = []
    for i, (label, val, color, sub) in enumerate(metrics):
        mx = 28 + i * col_w
        cells.append(f"""
  <circle cx="{mx+5:.0f}" cy="{strip_y-5:.0f}" r="4" fill="{color}"/>
  <text x="{mx+16:.0f}" y="{strip_y-1:.0f}" font-size="9.5" font-weight="800" letter-spacing="0.4" fill="{T['MUTED']}">{label}</text>
  <text x="{mx:.0f}" y="{strip_y+22:.0f}" font-size="22" font-weight="700" fill="{T['TEXT']}">{val}</text>
  <text x="{mx:.0f}" y="{strip_y+36:.0f}" font-size="8.5" fill="{T['MUTED']}">{truncate(str(sub), 20)}</text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{defs_block(T)}
<filter id="dotGlow" x="-100%" y="-100%" width="300%" height="300%">
  <feGaussianBlur stdDeviation="1.4" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
{header(T, w, h, truncate(data['name'], 30), T['CYAN'], profile_subtitle)}
<g transform="translate({cx}, {cy})">
  <circle r="{rr}" fill="none" stroke="{T['GRID']}" stroke-width="7"/>
  <circle r="{rr}" fill="none" stroke="url(#ringGrad)" stroke-width="7" stroke-linecap="round"
    stroke-dasharray="{circ:.2f}" stroke-dashoffset="{offset:.2f}" transform="rotate(-90)"/>
  <text y="-4" font-size="30" font-weight="800" fill="{T['TEXT']}" text-anchor="middle">{rank_letter}</text>
  <text y="16" font-size="8" letter-spacing="0.6" fill="{T['MUTED']}" text-anchor="middle">{rank_pct}</text>
</g>
<text x="{cx}" y="{cy+rr+30}" font-size="9" letter-spacing="0.4" fill="{T['MUTED']}" text-anchor="middle">{data['total_conts']} CONTRIBUTIONS / YEAR</text>
<text x="{gx}" y="56" font-size="9.5" font-weight="800" letter-spacing="0.4" fill="{T['MUTED']}">WEEKLY ACTIVITY &#183; LAST 20W</text>
{"".join(bars)}
<line x1="28" y1="{strip_y-30}" x2="{w-28}" y2="{strip_y-30}" stroke="{T['BORDER']}"/>
{"".join(cells)}
</svg>"""


# ─────────────────────────────────────────────
# CARD 2: STREAK + ACTIVITY RHYTHM — radar dial layout
# ─────────────────────────────────────────────
def generate_streak_svg(data, T):
    w, h = 496, 340

    s = calculate_streak(data["days"])
    a = calculate_activity_insights(data["days"])

    heatmap_area_w = w - 56
    heatmap_area_h = 66
    heatmap, heat_w, heat_h = render_heatmap(T, data["days"], heatmap_area_w, heatmap_area_h)
    heat_x_offset = max(0, (heatmap_area_w - heat_w) / 2)

    legend_x = w - 150
    legend = "".join(f'<rect x="{legend_x+i*13}" width="9" height="9" rx="2.5" fill="{c}"/>'
                     for i, c in enumerate(T["HEAT"]))

    def metric(x, y, label, value, color, sub):
        return f"""
  <text x="{x}" y="{y}" font-size="8.5" letter-spacing="0.6" fill="{T['MUTED']}">{label}</text>
  <text x="{x}" y="{y+21}" font-size="19" font-weight="700" fill="{color}">{value}</text>
  <text x="{x}" y="{y+35}" font-size="8" fill="{T['MUTED']}">{truncate(str(sub), 24)}</text>"""

    heatmap_y = 76
    legend_y = heatmap_y + heatmap_area_h + 14
    divider1_y = legend_y + 20
    row1_y = divider1_y + 26
    divider2_y = row1_y + 46
    row2_y = divider2_y + 26
    footer_y = row2_y + 52

    # Flame-style current-streak badge, top-right, replaces plain text.
    flame_cx, flame_cy = w - 56, 30
    flame_active = s["current_streak"] > 0
    flame_color = T["GREEN"] if flame_active else T["MUTED"]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{defs_block(T)}
<filter id="dotGlow" x="-100%" y="-100%" width="300%" height="300%">
  <feGaussianBlur stdDeviation="1.4" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
{header(T, w, h, "Streak & Rhythm", T['GREEN'], f"{s['total_active']} active days this year")}
<g transform="translate({flame_cx}, {flame_cy})">
  <path d="M0,-10 C4,-6 5,-1 2,2 C4,0 5,3 2,6 C4,5 3,9 0,10 C-3,9 -4,5 -2,6 C-5,3 -4,0 -2,2 C-5,-1 -4,-6 0,-10 Z"
    fill="{flame_color}" opacity="{1.0 if flame_active else 0.35}"/>
  <text x="14" y="4" font-size="13" font-weight="800" fill="{T['TEXT']}">{s['current_streak']}d</text>
</g>
<g transform="translate({28+heat_x_offset:.1f}, {heatmap_y})">{heatmap}</g>
<g transform="translate(0, {legend_y})">
  <text x="28" font-size="9" fill="{T['MUTED']}">less</text>
  {legend}
  <text x="{legend_x + 5*13 + 8}" y="8" font-size="9" fill="{T['MUTED']}">more</text>
</g>
<line x1="28" y1="{divider1_y}" x2="{w-28}" y2="{divider1_y}" stroke="{T['BORDER']}"/>
<g>
    {metric(28,  row1_y, "LONGEST STREAK",  s['longest_streak'], T['TEXT'],   s['long_range'])}
    {metric(178, row1_y, "LONGEST GAP",     a['longest_gap'],    T['RED'],    "days without activity")}
  {metric(328, row1_y, "CURRENT STREAK",  s['current_streak'], T['GREEN'],  s['curr_range'])}
</g>
<line x1="28" y1="{divider2_y}" x2="{w-28}" y2="{divider2_y}" stroke="{T['BORDER']}"/>
<g>
  {metric(28,  row2_y, "BUSIEST DAY",      s['best_day_count'], T['VIOLET'], s['best_day_date'] or '-')}
  {metric(178, row2_y, "BUSIEST MONTH",    a['busiest_month'],  T['CYAN'],   f"{a['busiest_month_count']} contributions")}
  {metric(328, row2_y, "WEEKEND ACTIVITY", f"{a['weekend_pct']}%", T['AMBER'],   f"peak: {a['top_weekday']}")}
</g>
<text x="28" y="{footer_y}" font-size="8.5" fill="{T['MUTED']}">avg {s['avg_per_active_day']} contributions / active day &#183; trailing 12 months</text>
</svg>"""


# ─────────────────────────────────────────────
# CARD 3: LANGUAGES — orbit/ring layout
# ─────────────────────────────────────────────
def generate_langs_svg(data, T):
    w = 496
    langs = sorted(data["langs"].items(), key=lambda x: x[1], reverse=True)[:12]
    total = sum(v for _, v in langs) or 1
    rows = max(1, (len(langs) + 2) // 3)
    items_top = 158
    row_h = 40
    items_bottom = items_top + (rows - 1) * row_h
    h = max(240, items_bottom + 40)

    # Donut ring instead of a flat segmented bar.
    ring_cx, ring_cy, ring_r, ring_sw = 70, 100, 46, 15
    circ = 2 * math.pi * ring_r
    segs, start = [], -90.0
    for name, v in langs:
        frac = v / total
        sweep = frac * 360
        color = LANG_COLORS.get(name, "#8b949e")
        dash = circ * frac
        gap = circ - dash
        segs.append(
            f'<circle cx="0" cy="0" r="{ring_r}" fill="none" stroke="{color}" stroke-width="{ring_sw}" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" stroke-dashoffset="{-(start/360*circ):.2f}" transform="rotate(-90)"/>'
        )
        start += sweep

    top_name = langs[0][0] if langs else "-"
    top_pct = round(langs[0][1] / total * 100) if langs else 0

    items = []
    col_w = (w - 56) / 3
    max_name_chars = 14
    for i, (name, v) in enumerate(langs):
        ix = 28 + (i % 3) * col_w
        iy = items_top + (i // 3) * row_h
        pct = round(v / total * 100, 1)
        items.append(f"""
  <circle cx="{ix+5:.0f}" cy="{iy-4:.0f}" r="4" fill="{LANG_COLORS.get(name, '#8b949e')}"/>
  <text x="{ix+16:.0f}" y="{iy:.0f}" font-size="10.5" fill="{T['TEXT']}">{truncate(name, max_name_chars)}</text>
  <text x="{ix+16:.0f}" y="{iy+14:.0f}" font-size="8.5" fill="{T['MUTED']}">{pct}%</text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{defs_block(T)}
{header(T, w, h, "Language Mix", T['VIOLET'], f"across {data['total_repos']} public repos")}
<g transform="translate({ring_cx}, {ring_cy})">
  <circle r="{ring_r}" fill="none" stroke="{T['GRID']}" stroke-width="{ring_sw}"/>
  {"".join(segs)}
  <text y="-3" font-size="15" font-weight="800" fill="{T['TEXT']}" text-anchor="middle">{top_pct}%</text>
  <text y="12" font-size="7.5" letter-spacing="0.3" fill="{T['MUTED']}" text-anchor="middle">{truncate(top_name, 12)}</text>
</g>
<text x="150" y="86" font-size="9.5" font-weight="800" letter-spacing="0.4" fill="{T['MUTED']}">TOP LANGUAGE</text>
<text x="150" y="108" font-size="18" font-weight="700" fill="{T['TEXT']}">{truncate(top_name, 20)}</text>
<text x="150" y="126" font-size="9" fill="{T['MUTED']}">{len(langs)} languages tracked across all owned repos</text>
<line x1="28" y1="{items_top-30}" x2="{w-28}" y2="{items_top-30}" stroke="{T['BORDER']}"/>
{"".join(items)}
</svg>"""


# ─────────────────────────────────────────────
# ERROR STATE (graceful fallback so the workflow never fails outright)
# ─────────────────────────────────────────────
def render_error_svg(T, w, h, title):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{defs_block(T)}
{header(T, w, h, title, T['RED'], "temporarily unavailable")}
<text x="{w/2}" y="{h/2}" font-size="13" fill="{T['RED']}" text-anchor="middle">API unavailable &#8212; stats could not be fetched</text>
<text x="{w/2}" y="{h/2+22}" font-size="10" fill="{T['MUTED']}" text-anchor="middle">will retry on next scheduled run</text>
</svg>"""


# ─────────────────────────────────────────────
# MAIN — generates dark AND light versions
# ─────────────────────────────────────────────
def main():
    cards = [("stats.svg", 560, 300, generate_stats_svg, "Profile Overview"),
             ("streak.svg", 496, 340, generate_streak_svg, "Streak & Rhythm"),
             ("langs.svg", 496, 280, generate_langs_svg, "Language Mix")]

    def write_fallback_cards():
        for theme_name, T in THEMES.items():
            suffix = "" if theme_name == "dark" else "-light"
            for base, w, h, fn, title in cards:
                fname = base.replace(".svg", f"{suffix}.svg")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(render_error_svg(T, w, h, title))
                print(f"wrote {fname} (placeholder)")

    try:
        data = fetch_github_stats()
    except Exception as e:
        print(f"::warning::{e}", file=sys.stderr)
        write_fallback_cards()
        print("Done with fallback cards.")
        return

    try:
        for theme_name, T in THEMES.items():
            suffix = "" if theme_name == "dark" else "-light"
            for base, w, h, fn, title in cards:
                fname = base.replace(".svg", f"{suffix}.svg")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(fn(data, T))
                print(f"wrote {fname}")
    except Exception as e:
        print(f"::warning::Card rendering failed: {e}", file=sys.stderr)
        write_fallback_cards()
        print("Done with fallback cards.")
        return

    print("Done!")


if __name__ == "__main__":
    main()