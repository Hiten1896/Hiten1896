#!/usr/bin/env python3
"""
GitHub Profile Stats Generator
Generates dark + light versions of: stats, streak, langs cards.
All numbers are REAL (GitHub GraphQL API). No fake fallback data.
Theme switching is done in README via <picture> + prefers-color-scheme.
"""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("GITHUB_USER", "Hiten1896")
API_URL = "https://api.github.com/graphql"

# ─────────────────────────────────────────────
# THEMES
# ─────────────────────────────────────────────
THEMES = {
    "dark": {
        "BG":     "#0d1117",
        "PANEL":  "#161b22",
        "BORDER": "#30363d",
        "TEXT": "#e6edf3",
        "MUTED":  "#8b949e",
        "GREEN":  "#3fb950",
        "RED":    "#f85149",
        "CYAN":   "#39d0d8",
        "VIOLET": "#a371f7",
        "AMBER":  "#e3b341",
        "PINK":   "#f472b6",
        "HEAT":   ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "LIGHTS": ["#ff5f57", "#febc2e", "#28c840"],
    },
    "light": {
        "BG":     "#ffffff",
        "PANEL":  "#f6f8fa",
        "BORDER": "#d0d7de",
        "TEXT":   "#1f2328",
        "MUTED":  "#656d76",
        "GREEN":  "#1a7f37",
        "RED":    "#cf222e",
        "CYAN":   "#0969da",
        "VIOLET": "#8250df",
        "AMBER":  "#9a6700",
        "PINK":   "#bf3989",
        "HEAT":   ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "LIGHTS": ["#ff5f57", "#febc2e", "#28c840"],
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


def editor_chrome(T, w, h, title, accent):
    t = title or "~/.github/profile"
    return f"""
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{T['PANEL']}" stroke="{T['BORDER']}"/>
  <line x1="0.5" y1="30" x2="{w-0.5}" y2="30" stroke="{T['BORDER']}"/>
  <circle cx="18" cy="15.5" r="5" fill="{T['LIGHTS'][0]}"/>
  <circle cx="34" cy="15.5" r="5" fill="{T['LIGHTS'][1]}"/>
  <circle cx="50" cy="15.5" r="5" fill="{T['LIGHTS'][2]}"/>
  <text x="64" y="19.5" font-size="10.5" fill="{T['MUTED']}">{t}</text>
  <circle cx="{w-16}" cy="15.5" r="3.5" fill="{accent}"/>"""


# ─────────────────────────────────────────────
# DATA FETCH (real data only)
# ─────────────────────────────────────────────
def fetch_github_stats():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set")

    to_dt = datetime.utcnow()
    from_dt = to_dt - timedelta(days=365)

    query = f"""
    query {{
      user(login: "{USERNAME}") {{
        name
        createdAt
        followers {{ totalCount }}
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
          totalCount
          nodes {{ stargazerCount forkCount primaryLanguage {{ name }}
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
        for d in week["contributionDays"]:
            days.append({"date": d["date"], "count": d["contributionCount"],
                         "weekday": d["weekday"]})
    days.sort(key=lambda x: x["date"])

    repos = user["repositories"]["nodes"]
    created = datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ")

    # Real language bytes estimate: count repos per primary language
    lang = defaultdict(int)
    for r in repos:
        if r.get("primaryLanguage") and r["primaryLanguage"].get("name"):
            lang[r["primaryLanguage"]["name"]] += 1

    return {
        "name": user.get("name") or USERNAME,
        "username": USERNAME,
        "followers": user["followers"]["totalCount"],
        "total_repos": user["repositories"]["totalCount"],
        "total_stars": sum(r["stargazerCount"] for r in repos),
        "total_forks": sum(r["forkCount"] for r in repos),
        "account_age_years": round((datetime.utcnow() - created).days / 365.25, 1),
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


def render_heatmap(T, days, cell=7.2, gap=2.3):
    rects = []
    base = datetime.strptime(days[0]["date"], "%Y-%m-%d").date()
    week_cols = defaultdict(list)
    for d in days:
        wk = (datetime.strptime(d["date"], "%Y-%m-%d").date() - base).days // 7
        week_cols[wk].append(d)

    def color(c):
        if c == 0: return T["HEAT"][0]
        if c <= 3: return T["HEAT"][1]
        if c <= 6: return T["HEAT"][2]
        if c <= 9: return T["HEAT"][3]
        return T["HEAT"][4]

    max_weeks = max(week_cols.keys()) + 1 if week_cols else 1
    for wk in range(max_weeks):
        for pos, d in enumerate(week_cols.get(wk, [])):
            rects.append(f'<rect x="{wk*(cell+gap):.1f}" y="{pos*(cell+gap):.1f}" '
                         f'width="{cell}" height="{cell}" rx="2" fill="{color(d["count"])}"/>')
    return "".join(rects), max_weeks * (cell + gap)


# ─────────────────────────────────────────────
# CARD 1: STATS (profile-level only)
# ─────────────────────────────────────────────
def generate_stats_svg(data, T):
    w, h = 560, 340
    rank_letter, rank_pct, score = calculate_rank(data)

    days = data["days"]
    weekly = [sum(days[i]["count"] for i in range(s, min(s+7, len(days))))
              for s in range(0, max(1, len(days)-6), 7)]
    last12 = weekly[-12:] if len(weekly) >= 12 else weekly
    smax = max(last12) or 1
    sx, sy, sw, sh = 28, 158, 210, 42
    bw = sw / max(1, len(last12))
    bars = "".join(
        f'<rect x="{sx+i*bw+1:.1f}" y="{sy+sh-(v/smax)*sh:.1f}" width="{bw-2:.1f}" '
        f'height="{(v/smax)*sh:.1f}" rx="1.5" fill="{T["CYAN"]}"/>'
        for i, v in enumerate(last12))

    pct = max(0, min(100, round(score)))
    rr, cx, cy = 44, w-78, 95
    circ = 2 * 3.14159265 * rr
    offset = circ * (1 - pct/100)

    active_days = sum(1 for d in days if d["count"] > 0)
    metrics = [
        ("TOTAL STARS",   data["total_stars"],   T["AMBER"],  "across repos"),
        ("COMM",       data["total_commits"], T["GREEN"],  "last 12 months"),
        ("PULL REQUESTS", data["total_prs"],     T["VIOLET"], f"{data['total_reviews']} reviews given"),
        ("FOLLOWERS",     data["followers"],     T["CYAN"],   f"{data['account_age_years']}y on GitHub"),
        ("PUBLIC REPOS",  data["total_repos"],   T["CYAN"],   f"{data['total_forks']} total forks"),
        ("ACTIVE DAYS",   active_days,           T["PINK"],   f"of {len(days)} tracked"),
    ]

    cells = []
    col_w = (w - 56) / 3
    for i, (label, val, color, sub) in enumerate(metrics):
        mx = 28 + (i % 3) * col_w
        my = 246 + (i // 3) * 42
        cells.append(f"""
  <rect x="{mx:.0f}" y="{my-8:.0f}" width="3" height="36" rx="1.5" fill="{color}"/>
  <text x="{mx+12:.0f}" y="{my+4:.0f}" font-size="8.5" letter-spacing="0.6" fill="{T['MUTED']}">{label}</text>
  <text x="{mx+12:.0f}" y="{my+25:.0f}" font-size="16" font-weight="700" fill="{T['TEXT']}">{val}<tspan font-size="8.5" fill="{T['MUTED']}" dx="6">{sub}</tspan></text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{editor_chrome(T, w, h, f"~/{data['username']}/report.md", T['CYAN'])}
<text x="28" y="72" font-size="22" font-weight="700" fill="{T['TEXT']}">{data['name']}</text>
<text x="28" y="92" font-size="11.5" fill="{T['CYAN']}">@{data['username']}</text>
<text x="28" y="124" font-size="27" font-weight="700" fill="{T['TEXT']}">{data['total_conts']}</text>
<text x="28" y="140" font-size="9" letter-spacing="0.6" fill="{T['MUTED']}">CONTRIBUTIONS &#183; LAST 12 MONTHS</text>
<g transform="translate({cx}, {cy})">
  <circle r="{rr}" fill="none" stroke="{T['BORDER']}" stroke-width="7"/>
  <circle r="{rr}" fill="none" stroke="{T['VIOLET']}" stroke-width="7" stroke-linecap="round"
    stroke-dasharray="{circ:.2f}" stroke-dashoffset="{offset:.2f}" transform="rotate(-90)"/>
  <text y="5" font-size="20" font-weight="700" fill="{T['TEXT']}" text-anchor="middle">{rank_letter}</text>
  <text y="19" font-size="7" letter-spacing="0.5" fill="{T['MUTED']}" text-anchor="middle">{rank_pct}</text>
</g>
<text x="28" y="152" font-size="8.5" letter-spacing="0.6" fill="{T['MUTED']}">WEEKLY TREND &#183; LAST 12 WEEKS</text>
{bars}
<line x1="28" y1="216" x2="{w-28}" y2="216" stroke="{T['BORDER']}"/>
{"".join(cells)}
</svg>"""


# ─────────────────────────────────────────────
# CARD 2: STREAK + ACTIVITY RHYTHM
# ─────────────────────────────────────────────
def generate_streak_svg(data, T):
    w, h = 496, 300
    s = calculate_streak(data["days"])
    a = calculate_activity_insights(data["days"])

    heatmap, heat_w = render_heatmap(T, data["days"])
    scale = min(1.0, (w - 56) / heat_w) if heat_w else 1.0

    legend_x = w - 150
    legend = "".join(f'<rect x="{legend_x+i*13}" width="9" height="9" rx="2" fill="{c}"/>'
                     for i, c in enumerate(T["HEAT"]))

    def metric(x, label, value, color, sub):
        return f"""
  <text x="{x}" font-size="8.5" letter-spacing="0.6" fill="{T['MUTED']}">{label}</text>
  <text x="{x}" y="22" font-size="19" font-weight="700" fill="{color}">{value}</text>
  <text x="{x}" y="37" font-size="8" fill="{T['MUTED']}">{sub}</text>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{editor_chrome(T, w, h, f"~/{data['username']}/streak.log", T['GREEN'])}
<g transform="translate(28, 50) scale({scale:.3f})">{heatmap}</g>
<g transform="translate(0, 118)">
  <text x="28" font-size="9" fill="{T['MUTED']}">less</text>
  {legend}
  <text x="{legend_x + 5*13 + 8}" y="8" font-size="9" fill="{T['MUTED']}">more</text>
</g>
<line x1="28" y1="136" x2="{w-28}" y2="136" stroke="{T['BORDER']}"/>
<g transform="translate(28, 168)">
    {metric(0,   "LONGEST STREAK",  s['longest_streak'], T['TEXT'],   s['long_range'])}
    {metric(150, "LONGEST GAP",     a['longest_gap'],    T['RED'],    "days without activity")}
  {metric(300, "CURRENT STREAK",  s['current_streak'], T['GREEN'],  s['curr_range'])}
</g>
<line x1="28" y1="212" x2="{w-28}" y2="212" stroke="{T['BORDER']}"/>
<g transform="translate(28, 244)">
  {metric(0,   "BUSIEST DAY",      s['best_day_count'], T['VIOLET'], s['best_day_date'] or '-')}
  {metric(150, "BUSIEST MONTH",    a['busiest_month'],  T['CYAN'],   f"{a['busiest_month_count']} contributions")}
  {metric(300, "WEEKEND ACTIVITY", a['weekend_pct'],    T['AMBER'],  f"peak: {a['top_weekday']}")}
</g>
<text x="28" y="{h-12}" font-size="8.5" fill="{T['MUTED']}">{s['total_active']} active days &#183; avg {s['avg_per_active_day']}/day &#183; last 12 months</text>
</svg>"""


# ─────────────────────────────────────────────
# CARD 3: LANGUAGES (real repo data)
# ─────────────────────────────────────────────
def generate_langs_svg(data, T):
    w, h = 496, 280
    langs = sorted(data["langs"].items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in langs)
    top = langs[:5]
    other = sum(v for _, v in langs[5:])
    if other > 0:
        top.append(("Other", other))

    bar_y, bar_x, bar_w, bar_h = 66, 28, w - 56, 14
    segs, xoff = [], bar_x
    for name, v in top:
        seg_w = (v / total) * bar_w
        color = LANG_COLORS.get(name, "#8b949e")
        segs.append(f'<rect x="{xoff:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>')
        xoff += seg_w

    items = []
    col_w = (w - 56) / 3
    for i, (name, v) in enumerate(top):
        ix = 28 + (i % 3) * col_w
        iy = 130 + (i // 3) * 44
        pct = round(v / total * 100, 1)
        items.append(f"""
  <circle cx="{ix+5:.0f}" cy="{iy-4:.0f}" r="4" fill="{LANG_COLORS.get(name, '#8b949e')}"/>
  <text x="{ix+16:.0f}" y="{iy:.0f}" font-size="10.5" fill="{T['TEXT']}">{name}</text>
  <text x="{ix+16:.0f}" y="{iy+14:.0f}" font-size="8.5" fill="{T['MUTED']}">{pct}%</text>""")

    commit_share = round(data["total_commits"] / max(1, data["total_conts"]) * 100)
    pr_share = round(data["total_prs"] / max(1, data["total_conts"]) * 100)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{editor_chrome(T, w, h, f"~/{data['username']}/languages.json", T['VIOLET'])}
<text x="28" y="52" font-size="12" font-weight="700" fill="{T['TEXT']}">Languages across {data['total_repos']} public repos</text>
{"".join(segs)}
<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="3" fill="none" stroke="{T['BORDER']}"/>
{"".join(items)}
<line x1="28" y1="222" x2="{w-28}" y2="222" stroke="{T['BORDER']}"/>
<text x="28" y="248" font-size="9" fill="{T['MUTED']}">Contribution mix</text>
<text x="150" y="248" font-size="9.5" fill="{T['GREEN']}">&#9679; {commit_share}% commits</text>
<text x="290" y="248" font-size="9.5" fill="{T['VIOLET']}">&#9679; {pr_share}% pull requests</text>
<text x="28" y="{h-12}" font-size="8.5" fill="{T['MUTED']}">Based on primary language of owned, non-forked repositories</text>
</svg>"""


# ─────────────────────────────────────────────
# ERROR STATE
# ─────────────────────────────────────────────
def render_error_svg(filename, T, w, h, title):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<style>{css(T)}</style>
{editor_chrome(T, w, h, title, T['RED'])}
<text x="{w/2}" y="{h/2}" font-size="13" fill="{T['RED']}" text-anchor="middle">API unavailable &#8212; stats could not be fetched</text>
<text x="{w/2}" y="{h/2+22}" font-size="10" fill="{T['MUTED']}" text-anchor="middle">will retry on next scheduled run</text>
</svg>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(svg)


# ─────────────────────────────────────────────
# MAIN — generates dark AND light versions
# ─────────────────────────────────────────────
def main():
    data = fetch_github_stats()
    cards = [("stats.svg", 560, 300, generate_stats_svg, "~/report.md"),
             ("streak.svg", 496, 300, generate_streak_svg, "~/streak.log"),
             ("langs.svg", 496, 280, generate_langs_svg, "~/languages.json")]

    for theme_name, T in THEMES.items():
        suffix = "" if theme_name == "dark" else "-light"
        for base, w, h, fn, title in cards:
            fname = base.replace(".svg", f"{suffix}.svg")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(fn(data, T))
            print(f"wrote {fname}")

    print("Done!")


if __name__ == "__main__":
    main()
