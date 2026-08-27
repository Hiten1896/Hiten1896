#!/usr/bin/env python3
"""
scripts/generate_stats.py
Fetches GitHub profile stats using GraphQL API, subsets font, and generates:
stats.svg, streak.svg, and langs.svg.

Visual identity: "editor pane" cards -- each card mimics a minimal code
editor window (tab bar + dots), set in a dark slate palette with cyan/violet
accents and full monospace type. The streak card includes a real rendered
GitHub-style contribution heatmap (not a placeholder).
"""

import os
import json
import base64
import io
import urllib.request
from datetime import datetime, timezone, timedelta

FONT_PATH = os.path.join(os.path.dirname(__file__), "JetBrainsMono-Regular.ttf")
FONT_URL = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf"

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
BG = "#0a0e14"
PANEL = "#10161f"
BORDER = "#1e2530"
TEXT = "#e2e8f0"
MUTED = "#6b7789"
CYAN = "#7dd3fc"
VIOLET = "#c084fc"
GREEN = "#4ade80"
AMBER = "#fbbf24"
RED = "#f87171"

HEAT_SCALE = ["#151b24", "#123a2e", "#1a6b4a", "#22a866", "#4ade80"]


def ensure_font():
    if not os.path.exists(FONT_PATH):
        try:
            req = urllib.request.Request(FONT_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(FONT_PATH, "wb") as f:
                f.write(resp.read())
        except Exception as e:
            print(f"Warning: Could not download JetBrains Mono font: {e}")


def subset_font_b64(text_content):
    ensure_font()
    if not os.path.exists(FONT_PATH):
        return "", ""
    try:
        from fontTools import subset
        options = subset.Options()
        options.flavor = 'woff2'
        font = subset.load_font(FONT_PATH, options)
        subsetter = subset.Subsetter(options=options)
        chars = "".join(set(
            text_content + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            ".:,+-*/%#@! ()[]{}<>&|_~'\"-->"
        ))
        subsetter.populate(text=chars)
        subsetter.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        return base64.b64encode(buf.getvalue()).decode('utf-8'), 'woff2'
    except Exception:
        with open(FONT_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8'), 'truetype'


def get_font_style_css(text_content):
    b64_font, fmt = subset_font_b64(text_content)
    if not b64_font:
        return ""
    return f"""
    @font-face {{
      font-family: 'JetBrains Mono';
      src: url('data:font/{fmt};base64,{b64_font}') format('{fmt}');
      font-weight: normal;
      font-style: normal;
    }}
    text {{ font-family: 'JetBrains Mono', monospace; }}
    """


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def fetch_github_stats():
    username = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GITHUB_ACTOR") or "Hiten1896"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    print(f"Fetching stats for user: {username} (Token provided: {bool(token)})")

    now_utc = datetime.now(timezone.utc)
    to_dt = now_utc.replace(hour=23, minute=59, second=59, microsecond=0)
    from_dt = (now_utc - timedelta(days=363)).replace(hour=0, minute=0, second=0, microsecond=0)

    graphql_query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        name
        login
        createdAt
        followers { totalCount }
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                color
                weekday
              }
            }
          }
        }
        repositories(first: 100, isFork: false, privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
          totalCount
          nodes {
            name
            stargazerCount
            forkCount
            primaryLanguage { name color }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }
    """

    if not token:
        print("Error: No GitHub token found in environment variables!")
        return generate_fallback_stats(username, from_dt, to_dt)

    payload = json.dumps({
        "query": graphql_query,
        "variables": {
            "username": username,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "Python-urllib/3.x"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if "errors" in res_data or not res_data.get("data") or not res_data["data"].get("user"):
                print("GraphQL Error Response:", res_data)
                return generate_fallback_stats(username, from_dt, to_dt)
            print("Successfully fetched live GitHub data!")
            return parse_graphql_response(res_data["data"]["user"], from_dt, to_dt)
    except Exception as e:
        print("API Request Exception:", e)
        return generate_fallback_stats(username, from_dt, to_dt)


def parse_graphql_response(user_data, from_dt, to_dt):
    col = user_data["contributionsCollection"]
    cal = col["contributionCalendar"]
    repos = user_data["repositories"]["nodes"]

    total_stars = sum(r["stargazerCount"] for r in repos)
    total_forks = sum(r["forkCount"] for r in repos)
    total_commits = col["totalCommitContributions"]
    total_prs = col["totalPullRequestContributions"]
    total_reviews = col.get("totalPullRequestReviewContributions", 0)
    total_issues = col["totalIssueContributions"]
    total_private = col.get("restrictedContributionsCount", 0)
    total_repos = user_data["repositories"]["totalCount"]
    total_conts = cal["totalContributions"]
    followers = user_data.get("followers", {}).get("totalCount", 0)

    account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(
        user_data["createdAt"].replace("Z", "+00:00"))).days
    account_age_years = round(account_age_days / 365.25, 1)

    lang_map = {}
    for r in repos:
        for edge in r.get("languages", {}).get("edges", []):
            lname = edge["node"]["name"]
            lcolor = edge["node"]["color"] or "#858585"
            lsize = edge["size"]
            if lname not in lang_map:
                lang_map[lname] = {"size": 0, "color": lcolor}
            lang_map[lname]["size"] += lsize

    top_repos = sorted(repos, key=lambda r: r["stargazerCount"], reverse=True)[:3]

    days_list = []
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            days_list.append({"date": d["date"], "count": d["contributionCount"], "color": d["color"], "weekday": d["weekday"]})

    return {
        "username": user_data["login"],
        "name": user_data.get("name") or user_data["login"],
        "followers": followers,
        "account_age_years": account_age_years,
        "total_stars": total_stars, "total_forks": total_forks,
        "total_commits": total_commits, "total_prs": total_prs,
        "total_reviews": total_reviews, "total_issues": total_issues,
        "total_private": total_private,
        "total_repos": total_repos,
        "total_conts": total_conts, "languages": lang_map,
        "top_repos": top_repos,
        "days": days_list, "from_dt": from_dt, "to_dt": to_dt
    }


def generate_fallback_stats(username, from_dt, to_dt):
    print("Using fallback dummy stats.")
    days_list, curr, total_c = [], from_dt, 0
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    while curr <= to_dt:
        d_str = curr.strftime("%Y-%m-%d")
        c_val = 2 if d_str in [today_str, yesterday_str] else (1 if curr.weekday() < 5 else 0)
        days_list.append({"date": d_str, "count": c_val, "color": "#26a641" if c_val > 0 else "#161b22", "weekday": curr.weekday()})
        total_c += c_val
        curr += timedelta(days=1)
    return {
        "username": username, "name": username, "followers": 32, "account_age_years": 3.2,
        "total_stars": 12, "total_forks": 4,
        "total_commits": 148, "total_prs": 18, "total_reviews": 9, "total_issues": 6,
        "total_private": 40, "total_repos": 14,
        "total_conts": total_c,
        "languages": {
            "JavaScript": {"size": 450000, "color": "#f1e05a"},
            "Python": {"size": 220000, "color": "#3572A5"},
            "TypeScript": {"size": 150000, "color": "#3178c6"},
        },
        "top_repos": [
            {"name": "example-repo", "stargazerCount": 12, "forkCount": 3, "primaryLanguage": {"name": "JavaScript", "color": "#f1e05a"}},
        ],
        "days": days_list, "from_dt": from_dt, "to_dt": to_dt
    }


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------
def calculate_rank(data):
    """Weighted, saturating score -> letter rank. More signal than a raw sum."""
    import math
    stars = data["total_stars"]
    commits = data["total_commits"]
    prs = data["total_prs"]
    issues = data["total_issues"]
    reviews = data.get("total_reviews", 0)
    followers = data.get("followers", 0)
    repos = data["total_repos"]

    def sat(x, half_life):
        return 1 - math.exp(-x / half_life) if half_life else 0

    score = (
        sat(stars, 50) * 30 +
        sat(commits, 250) * 25 +
        sat(prs, 50) * 15 +
        sat(reviews, 30) * 10 +
        sat(issues, 25) * 5 +
        sat(followers, 100) * 10 +
        sat(repos, 30) * 5
    )

    if score >= 85: return "S", "TOP 1%", score
    if score >= 70: return "A+", "TOP 5%", score
    if score >= 55: return "A", "TOP 15%", score
    if score >= 38: return "B+", "TOP 30%", score
    if score >= 22: return "B", "TOP 50%", score
    return "C", "GROWING", score


def format_date_str(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return date_str


def calculate_streak(days_list):
    total_active = sum(1 for d in days_list if d["count"] > 0)
    max_streak, curr_streak = 0, 0
    max_start, max_end = "", ""
    curr_start, curr_end = "", ""

    temp_streak = 0
    temp_start = ""

    for d in days_list:
        if d["count"] > 0:
            if temp_streak == 0:
                temp_start = d["date"]
            temp_streak += 1
            curr_streak = temp_streak
            curr_start = temp_start
            curr_end = d["date"]

            if curr_streak >= max_streak:
                max_streak = curr_streak
                max_start = curr_start
                max_end = curr_end
        else:
            temp_streak = 0
            curr_streak = 0
            curr_start = ""
            curr_end = ""

    # If the most recent day has no contributions, current streak is genuinely 0.
    if days_list and days_list[-1]["count"] == 0:
        curr_streak = 0
        curr_start = curr_end = ""

    if not max_start and days_list:
        max_start = days_list[0]["date"]
        max_end = days_list[0]["date"]

    best_day = max(days_list, key=lambda d: d["count"], default={"count": 0, "date": ""})
    avg_per_active_day = round(sum(d["count"] for d in days_list) / total_active, 1) if total_active else 0

    return {
        "current_streak": curr_streak,
        "longest_streak": max_streak,
        "total_active": total_active,
        "curr_range": f"{format_date_str(curr_start)} -> {format_date_str(curr_end)}" if curr_start else "No active streak right now",
        "long_range": f"{format_date_str(max_start)} -> {format_date_str(max_end)}",
        "best_day_count": best_day["count"],
        "best_day_date": format_date_str(best_day["date"]),
        "avg_per_active_day": avg_per_active_day,
    }


# ---------------------------------------------------------------------------
# Shared SVG chrome -- "editor pane" signature element
# ---------------------------------------------------------------------------
def editor_chrome(w, h, tab_label, accent):
    """Top tab bar mimicking a minimal code editor window."""
    return f"""
  <rect x="0" y="0" width="{w}" height="{h}" rx="14" fill="{PANEL}" />
  <rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="13.25" fill="none" stroke="{BORDER}" stroke-width="1.5" />
  <rect x="0" y="0" width="{w}" height="34" rx="14" fill="{BG}" />
  <rect x="0" y="20" width="{w}" height="14" fill="{BG}" />
  <line x1="0" y1="34" x2="{w}" y2="34" stroke="{BORDER}" stroke-width="1" />
  <circle cx="20" cy="17" r="5" fill="{RED}" opacity="0.85" />
  <circle cx="37" cy="17" r="5" fill="{AMBER}" opacity="0.85" />
  <circle cx="54" cy="17" r="5" fill="{GREEN}" opacity="0.85" />
  <text x="{w/2}" y="21.5" font-size="11.5" fill="{MUTED}" text-anchor="middle">{tab_label}</text>
  <rect x="{w - 34}" y="10" width="20" height="14" rx="3" fill="none" stroke="{accent}" stroke-width="1.2" opacity="0.6" />
"""


# ---------------------------------------------------------------------------
# Card 1: Stats overview
# ---------------------------------------------------------------------------
def generate_stats_svg(data):
    w, h = 496, 340
    rank_letter, rank_pct, score = calculate_rank(data)
    font_css = get_font_style_css(data['name'] + rank_letter + rank_pct)

    metrics = [
        ("Stars",         data["total_stars"],  CYAN),
        ("Commits (yr)",  data["total_commits"], GREEN),
        ("Pull Requests", data["total_prs"],     VIOLET),
        ("Reviews",       data.get("total_reviews", 0), AMBER),
        ("Issues",        data["total_issues"],  "#f472b6"),
        ("Repositories",  data["total_repos"],   "#38bdf8"),
    ]

    # Right-hand info column reserved for the rank ring; metrics use the
    # remaining width as a single, generously spaced 3-row x 2-col grid.
    grid_left = 28
    grid_right = w - 168   # leaves room for the rank card on the right
    col_gap = 18
    col_w = (grid_right - grid_left - col_gap) / 2
    row_h = 62
    grid_top = 96

    cells = []
    for i, (label, val, color) in enumerate(metrics):
        col = i % 2
        row = i // 2
        x = grid_left + col * (col_w + col_gap)
        y = grid_top + row * row_h

        cells.append(f"""
    <rect x="{x:.1f}" y="{y:.1f}" width="{col_w:.1f}" height="{row_h - 14:.1f}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1" />
    <rect x="{x:.1f}" y="{y:.1f}" width="3" height="{row_h - 14:.1f}" rx="1.5" fill="{color}" />
    <text x="{x + 16:.1f}" y="{y + 20:.1f}" font-size="10" letter-spacing="0.5" fill="{MUTED}">{label.upper()}</text>
    <text x="{x + 16:.1f}" y="{y + 39:.1f}" font-size="19" font-weight="700" fill="{TEXT}">{val}</text>""")

    grid_bottom = grid_top + 3 * row_h - 14

    score_pct = max(0, min(100, round(score)))
    ring_r = 40
    circumference = 2 * 3.14159265 * ring_r
    offset = circumference * (1 - score_pct / 100)
    ring_cx = w - 90
    ring_cy = grid_top + 58

    footer_y = h - 26

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>{font_css}</style>
  {editor_chrome(w, h, f"~/{data['username']}/stats.json", CYAN)}

  <text x="28" y="56" font-size="17" font-weight="700" fill="{TEXT}">{data['name']}</text>
  <text x="28" y="76" font-size="11.5" fill="{MUTED}">@{data['username']} &#183; {data.get('account_age_years', 0)}y on GitHub</text>

  {"".join(cells)}

  <g transform="translate({ring_cx}, {ring_cy})">
    <text x="0" y="-56" font-size="10" letter-spacing="0.5" fill="{MUTED}" text-anchor="middle">RANK</text>
    <circle cx="0" cy="0" r="{ring_r}" fill="none" stroke="{BORDER}" stroke-width="8" />
    <circle cx="0" cy="0" r="{ring_r}" fill="none" stroke="{CYAN}" stroke-width="8"
      stroke-linecap="round" stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{offset:.2f}"
      transform="rotate(-90)" />
    <text x="0" y="8" font-size="24" font-weight="700" fill="{TEXT}" text-anchor="middle">{rank_letter}</text>
    <text x="0" y="66" font-size="10.5" fill="{MUTED}" text-anchor="middle">{rank_pct}</text>
  </g>

  <line x1="28" y1="{grid_bottom + 24:.1f}" x2="{w - 28}" y2="{grid_bottom + 24:.1f}" stroke="{BORDER}" stroke-width="1" />

  <g transform="translate(28, {footer_y})">
    <text x="0" y="0" font-size="10" fill="{MUTED}">FOLLOWERS</text>
    <text x="0" y="18" font-size="15" font-weight="700" fill="{TEXT}">{data.get('followers', 0)}</text>
  </g>
  <g transform="translate(180, {footer_y})">
    <text x="0" y="0" font-size="10" fill="{MUTED}">PRIVATE CONTRIBUTIONS</text>
    <text x="0" y="18" font-size="15" font-weight="700" fill="{TEXT}">{data.get('total_private', 0)}</text>
  </g>
  <g transform="translate(360, {footer_y})">
    <text x="0" y="0" font-size="10" fill="{MUTED}">TOTAL CONTRIBUTIONS</text>
    <text x="0" y="18" font-size="15" font-weight="700" fill="{TEXT}">{data.get('total_conts', 0)}</text>
  </g>
</svg>"""


# ---------------------------------------------------------------------------
# Card 2: Streak + real contribution heatmap
# ---------------------------------------------------------------------------
def heat_color(count):
    if count <= 0: return HEAT_SCALE[0]
    if count <= 2: return HEAT_SCALE[1]
    if count <= 5: return HEAT_SCALE[2]
    if count <= 9: return HEAT_SCALE[3]
    return HEAT_SCALE[4]


def render_heatmap(days_list, x0, y0, cell=8.2, gap=2.6):
    """Render an actual GitHub-style weekly contribution grid from real data."""
    weeks = []
    week = [None] * 7
    if days_list:
        first_weekday = days_list[0]["weekday"]
        for wd in range(first_weekday):
            week[wd] = None
    for d in days_list:
        wd = d["weekday"]
        week[wd] = d
        if wd == 6:
            weeks.append(week)
            week = [None] * 7
    if any(v is not None for v in week):
        weeks.append(week)

    svg_parts = []
    for wi, wk in enumerate(weeks):
        for di, day in enumerate(wk):
            if day is None:
                continue
            cx = x0 + wi * (cell + gap)
            cy = y0 + di * (cell + gap)
            color = heat_color(day["count"])
            svg_parts.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell}" height="{cell}" rx="2" fill="{color}" />')
    width_used = len(weeks) * (cell + gap)
    return "".join(svg_parts), width_used


def generate_streak_svg(data):
    w, h = 496, 248
    s = calculate_streak(data["days"])
    font_css = get_font_style_css("streak" + s['curr_range'] + s['long_range'])

    heatmap_svg, heat_w = render_heatmap(data["days"], x0=0, y0=0, cell=7.2, gap=2.3)
    max_w = w - 56
    scale = min(1.0, max_w / heat_w) if heat_w else 1.0

    legend_x = w - 150
    legend_cells = "".join(
        f'<rect x="{legend_x + i*13}" y="0" width="9" height="9" rx="2" fill="{c}" />'
        for i, c in enumerate(HEAT_SCALE)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>{font_css}</style>
  {editor_chrome(w, h, f"~/{data['username']}/streak.log", GREEN)}
  <text x="28" y="54" font-size="11.5" fill="{MUTED}">contributions.map(day =&gt; day.count)</text>
  <g transform="translate(28, 62) scale({scale:.3f})">
    {heatmap_svg}
  </g>
  <g transform="translate(0, 128)">
    <text x="28" y="0" font-size="9.5" fill="{MUTED}">less</text>
    {legend_cells}
    <text x="{legend_x + 5*13 + 8}" y="8" font-size="9.5" fill="{MUTED}">more</text>
  </g>
  <g transform="translate(28, 164)">
    <text x="0" y="0" font-size="10" fill="{MUTED}">CURRENT STREAK</text>
    <text x="0" y="23" font-size="20" font-weight="700" fill="{GREEN}">{s['current_streak']}<tspan font-size="11" fill="{MUTED}"> days</tspan></text>
    <text x="0" y="39" font-size="8.5" fill="{MUTED}">{s['curr_range']}</text>
  </g>
  <g transform="translate(180, 164)">
    <text x="0" y="0" font-size="10" fill="{MUTED}">LONGEST STREAK</text>
    <text x="0" y="23" font-size="20" font-weight="700" fill="{TEXT}">{s['longest_streak']}<tspan font-size="11" fill="{MUTED}"> days</tspan></text>
    <text x="0" y="39" font-size="8.5" fill="{MUTED}">{s['long_range']}</text>
  </g>
  <g transform="translate(360, 164)">
    <text x="0" y="0" font-size="10" fill="{MUTED}">BEST DAY</text>
    <text x="0" y="23" font-size="20" font-weight="700" fill="{VIOLET}">{s['best_day_count']}</text>
    <text x="0" y="39" font-size="8.5" fill="{MUTED}">{s['best_day_date'] or '-'}</text>
  </g>
  <text x="28" y="{h - 14}" font-size="9" fill="{MUTED}">{s['total_active']} active days - avg {s['avg_per_active_day']}/day when active</text>
</svg>"""


# ---------------------------------------------------------------------------
# Card 3: Languages + top repos
# ---------------------------------------------------------------------------
def generate_langs_svg(data):
    w, h = 496, 280
    langs = sorted(data["languages"].items(), key=lambda x: x[1]["size"], reverse=True)[:6]
    total = sum(i["size"] for _, i in langs) or 1
    font_css = get_font_style_css("langs" + "".join(n for n, _ in langs))

    bar_x, bar_y, bar_w = 28, 56, w - 56
    rects, curr_x = [], bar_x
    legend = []
    for idx, (name, info) in enumerate(langs):
        pct = info["size"] / total
        seg_w = pct * bar_w
        rects.append(f'<rect x="{curr_x:.1f}" y="{bar_y}" width="{max(seg_w, 1):.1f}" height="10" fill="{info["color"]}" />')
        curr_x += seg_w
        col = idx % 2
        row = idx // 2
        lx = 28 + col * 235
        ly = 92 + row * 22
        legend.append(
            f'<rect x="{lx}" y="{ly - 9}" width="8" height="8" rx="2" fill="{info["color"]}" />'
            f'<text x="{lx + 14}" y="{ly}" font-size="11.5" fill="{TEXT}">{name}</text>'
            f'<text x="{lx + 215}" y="{ly}" font-size="10.5" fill="{MUTED}" text-anchor="end">{pct*100:.1f}%</text>'
        )

    top_repos = data.get("top_repos", [])[:3]
    repo_rows = []
    ry = 222
    for r in top_repos:
        lang = (r.get("primaryLanguage") or {}) or {}
        lname = lang.get("name", "-")
        lcolor = lang.get("color") or MUTED
        repo_rows.append(f"""
    <circle cx="34" cy="{ry - 4}" r="3.5" fill="{lcolor}" />
    <text x="46" y="{ry}" font-size="11.5" fill="{TEXT}">{r['name']}</text>
    <text x="{w - 28}" y="{ry}" font-size="11" fill="{AMBER}" text-anchor="end">&#9733; {r['stargazerCount']}</text>
    <text x="{w - 78}" y="{ry}" font-size="11" fill="{MUTED}" text-anchor="end">fork {r['forkCount']}</text>""")
        ry += 20

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>{font_css}</style>
  {editor_chrome(w, h, f"~/{data['username']}/languages.yml", VIOLET)}
  <text x="28" y="50" font-size="12.5" fill="{MUTED}">top languages by bytes written</text>
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="{BORDER}" />
  <clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5" /></clipPath>
  <g clip-path="url(#barclip)">{"".join(rects)}</g>
  {"".join(legend)}
  <line x1="28" y1="182" x2="{w - 28}" y2="182" stroke="{BORDER}" stroke-width="1" />
  <text x="28" y="200" font-size="10" fill="{MUTED}">TOP REPOSITORIES</text>
  {"".join(repo_rows)}
</svg>"""


def main():
    data = fetch_github_stats()
    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write(generate_stats_svg(data))
    with open("streak.svg", "w", encoding="utf-8") as f:
        f.write(generate_streak_svg(data))
    with open("langs.svg", "w", encoding="utf-8") as f:
        f.write(generate_langs_svg(data))
    print("Stats SVGs generated successfully!")


if __name__ == "__main__":
    main()