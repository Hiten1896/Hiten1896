#!/usr/bin/env python3
"""
scripts/generate_stats.py
Fetches GitHub profile stats using GitHub GraphQL API via urllib, restricted to public
repos with fixed 364-day UTC daily boundaries. Subsets JetBrains Mono font via fonttools,
and generates clean standalone SVGs: stats.svg, streak.svg, langs.svg, and year.svg.
"""

import os
import sys
import json
import base64
import io
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

FONT_PATH = os.path.join(os.path.dirname(__file__), "JetBrainsMono-Regular.ttf")
FONT_URL = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf"

def ensure_font():
    """Ensure JetBrains Mono TTF font file is available locally."""
    if not os.path.exists(FONT_PATH):
        print(f"Downloading JetBrains Mono font to {FONT_PATH}...")
        try:
            req = urllib.request.Request(FONT_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(FONT_PATH, "wb") as f:
                f.write(resp.read())
            print("Font downloaded successfully.")
        except Exception as e:
            print(f"Warning: Could not download JetBrains Mono font: {e}")

def subset_font_b64(text_content):
    """Subset JetBrains Mono font for chars in text_content and return base64 string & format."""
    ensure_font()
    if not os.path.exists(FONT_PATH):
        return "", ""

    try:
        from fontTools import subset

        options = subset.Options()
        options.flavor = 'woff2'
        font = subset.load_font(FONT_PATH, options)
        subsetter = subset.Subsetter(options=options)
        # Ensure unique characters including digits & basic symbols
        chars = "".join(set(text_content + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.:,+-*/%#@! ()[]{}<>&|_~'\""))
        subsetter.populate(text=chars)
        subsetter.subset(font)

        buf = io.BytesIO()
        font.save(buf)
        b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        return b64_str, 'woff2'
    except Exception as e:
        print(f"Font subsetting woff2 failed ({e}), trying woff fallback...")
        try:
            from fontTools import subset
            options = subset.Options()
            options.flavor = 'woff'
            font = subset.load_font(FONT_PATH, options)
            subsetter = subset.Subsetter(options=options)
            chars = "".join(set(text_content + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.:,+-*/%#@! ()[]{}<>&|_~'\""))
            subsetter.populate(text=chars)
            subsetter.subset(font)

            buf = io.BytesIO()
            font.save(buf)
            b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
            return b64_str, 'woff'
        except Exception as e2:
            print(f"Fallback font subsetting failed: {e2}")
            with open(FONT_PATH, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode('utf-8')
            return b64_str, 'truetype'

def get_font_style_css(text_content):
    b64_font, fmt = subset_font_b64(text_content)
    if not b64_font:
        return """
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&amp;display=swap');
    body, text { font-family: 'JetBrains Mono', monospace; }
    """
    return f"""
    @font-face {{
      font-family: 'JetBrains Mono';
      src: url('data:font/{fmt};base64,{b64_font}') format('{fmt}');
      font-weight: normal;
      font-style: normal;
    }}
    body, text {{ font-family: 'JetBrains Mono', monospace; }}
    """

def fetch_github_stats():
    """Fetch GitHub profile stats via GraphQL API restricted to 364 days public repos with fixed UTC boundaries."""
    username = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GITHUB_ACTOR") or "Hiten1896"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    now_utc = datetime.now(timezone.utc)
    # Fixed daily UTC boundaries for 364 days
    to_dt = now_utc.replace(hour=23, minute=59, second=59, microsecond=0)
    from_dt = (now_utc - timedelta(days=363)).replace(hour=0, minute=0, second=0, microsecond=0)

    from_iso = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    graphql_query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        name
        login
        createdAt
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoryContributions
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
            primaryLanguage {
              name
              color
            }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    """

    if not token:
        print("WARNING: No GITHUB_TOKEN/GH_TOKEN found in environment.")
        print("WARNING: Falling back to FAKE placeholder stats (not your real GitHub data).")
        return generate_fallback_stats(username, from_dt, to_dt)

    payload = json.dumps({
        "query": graphql_query,
        "variables": {
            "username": username,
            "from": from_iso,
            "to": to_iso
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Python-urllib/3.x"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if "errors" in res_data:
                print("ERROR: GitHub GraphQL API returned errors:")
                for err in res_data["errors"]:
                    print(f"  - {err.get('message', err)}")
                print("WARNING: Falling back to FAKE placeholder stats (not your real GitHub data).")
                return generate_fallback_stats(username, from_dt, to_dt)
            if not res_data.get("data") or not res_data["data"].get("user"):
                print(f"ERROR: GraphQL response missing user data. Full response: {res_data}")
                print("WARNING: Falling back to FAKE placeholder stats (not your real GitHub data).")
                return generate_fallback_stats(username, from_dt, to_dt)
            return parse_graphql_response(res_data["data"]["user"], from_dt, to_dt)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: GitHub API HTTP {e.code} ({e.reason}). Response body: {body}")
        print("WARNING: Falling back to FAKE placeholder stats (not your real GitHub data).")
        return generate_fallback_stats(username, from_dt, to_dt)
    except Exception as e:
        print(f"ERROR: Failed to fetch GraphQL stats: {e!r}")
        print("WARNING: Falling back to FAKE placeholder stats (not your real GitHub data).")
        return generate_fallback_stats(username, from_dt, to_dt)

def parse_graphql_response(user_data, from_dt, to_dt):
    col = user_data["contributionsCollection"]
    cal = col["contributionCalendar"]
    repos = user_data["repositories"]["nodes"]

    total_stars = sum(r["stargazerCount"] for r in repos)
    total_forks = sum(r["forkCount"] for r in repos)
    total_commits = col["totalCommitContributions"]
    total_prs = col["totalPullRequestContributions"]
    total_issues = col["totalIssueContributions"]
    total_repos = user_data["repositories"]["totalCount"]
    total_conts = cal["totalContributions"]

    # Language breakdown
    lang_map = {}
    for r in repos:
        for edge in r.get("languages", {}).get("edges", []):
            lname = edge["node"]["name"]
            lcolor = edge["node"]["color"] or "#858585"
            lsize = edge["size"]
            if lname not in lang_map:
                lang_map[lname] = {"size": 0, "color": lcolor}
            lang_map[lname]["size"] += lsize

    # Flat list of contribution days
    days_list = []
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            days_list.append({
                "date": d["date"],
                "count": d["contributionCount"],
                "color": d["color"],
                "weekday": d["weekday"]
            })

    return {
        "username": user_data["login"],
        "name": user_data.get("name") or user_data["login"],
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_issues": total_issues,
        "total_repos": total_repos,
        "total_conts": total_conts,
        "languages": lang_map,
        "days": days_list,
        "from_dt": from_dt,
        "to_dt": to_dt,
        "is_fallback": False
    }

def generate_fallback_stats(username, from_dt, to_dt):
    """Generate accurate structure if token unavailable locally."""
    days_list = []
    curr = from_dt
    day_idx = 0
    total_c = 0
    while curr <= to_dt:
        date_str = curr.strftime("%Y-%m-%d")
        # Generate realistic contribution pattern
        count = (day_idx * 7 + 3) % 9 if (day_idx % 7 not in (5, 6)) else (day_idx % 3)
        total_c += count
        days_list.append({
            "date": date_str,
            "count": count,
            "color": "#26a641" if count > 5 else ("#0e4429" if count > 0 else "#161b22"),
            "weekday": curr.weekday()
        })
        curr += timedelta(days=1)
        day_idx += 1

    return {
        "username": username,
        "name": f"{username} (DEMO DATA - check Action logs)",
        "total_stars": 12,
        "total_forks": 4,
        "total_commits": 148,
        "total_prs": 18,
        "total_issues": 6,
        "total_repos": 14,
        "total_conts": total_c,
        "languages": {
            "JavaScript": {"size": 450000, "color": "#f1e05a"},
            "Python": {"size": 320000, "color": "#3572A5"},
            "C++": {"size": 180000, "color": "#f34b7d"},
            "HTML": {"size": 95000, "color": "#e34c26"},
            "CSS": {"size": 75000, "color": "#563d7c"}
        },
        "days": days_list,
        "from_dt": from_dt,
        "to_dt": to_dt,
        "is_fallback": True
    }

def calculate_rank(data):
    """
    Compute a rough rank from actual fetched stats instead of a hardcoded value.
    This is a simple heuristic (not GitHub's official algorithm) so it's clearly
    derived from your real numbers rather than a fixed 'A+ / TOP 15%' placeholder.
    """
    score = (
        data["total_stars"] * 4
        + data["total_commits"] * 0.5
        + data["total_prs"] * 3
        + data["total_issues"] * 2
        + data["total_forks"] * 3
    )

    if score >= 400:
        letter, pct = "S", "TOP 1%"
    elif score >= 200:
        letter, pct = "A+", "TOP 5%"
    elif score >= 100:
        letter, pct = "A", "TOP 15%"
    elif score >= 50:
        letter, pct = "B+", "TOP 30%"
    elif score >= 20:
        letter, pct = "B", "TOP 50%"
    else:
        letter, pct = "C", "KEEP GOING"

    return letter, pct

def calculate_streak(days_list):
    """Calculate current streak, longest streak, total active days."""
    total_active = sum(1 for d in days_list if d["count"] > 0)

    # Longest streak
    max_streak = 0
    curr_streak = 0
    max_start = max_end = ""
    curr_start = ""

    for d in days_list:
        if d["count"] > 0:
            if curr_streak == 0:
                curr_start = d["date"]
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
                max_start = curr_start
                max_end = d["date"]
        else:
            curr_streak = 0

    # Current streak (working backwards from today)
    current_streak = 0
    curr_streak_start = curr_streak_end = ""
    for d in reversed(days_list):
        if d["count"] > 0:
            if current_streak == 0:
                curr_streak_end = d["date"]
            current_streak += 1
            curr_streak_start = d["date"]
        elif current_streak > 0:
            break

    return {
        "current_streak": current_streak,
        "current_range": f"{curr_streak_start} - {curr_streak_end}" if current_streak else "N/A",
        "longest_streak": max_streak,
        "longest_range": f"{max_start} - {max_end}" if max_streak else "N/A",
        "total_active": total_active
    }

# SVG Generators

def generate_stats_svg(data):
    w, h = 480, 220
    rank_letter, rank_pct = calculate_rank(data)
    text_content = f"{data['name']} {data['username']} Stars Commits PRs Issues Repositories RANK {rank_letter} {rank_pct} {data['total_stars']} {data['total_commits']} {data['total_prs']} {data['total_issues']} {data['total_repos']}"
    font_css = get_font_style_css(text_content)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>
    {font_css}
    .bg {{ fill: #0d1117; rx: 12px; }}
    .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }}
    .title {{ font-size: 16px; font-weight: 700; fill: #58a6ff; }}
    .label {{ font-size: 13px; font-weight: 400; fill: #8b949e; }}
    .stat-val {{ font-size: 14px; font-weight: 700; fill: #c9d1d9; }}
    .rank-bg {{ fill: #161b22; stroke: #30363d; stroke-width: 1; rx: 8px; }}
    .rank-title {{ font-size: 11px; fill: #8b949e; text-anchor: middle; }}
    .rank-val {{ font-size: 28px; font-weight: 700; fill: #3fb950; text-anchor: middle; }}
  </style>
  <rect class="bg" width="{w}" height="{h}" />
  <rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />

  <!-- Header -->
  <g transform="translate(24, 34)">
    <path fill="#58a6ff" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.28.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
    <text x="26" y="12" class="title">{data['name']}'s GitHub Stats</text>
  </g>

  <!-- Stats Grid -->
  <g transform="translate(24, 65)">
    <!-- Total Stars -->
    <g transform="translate(0, 0)">
      <path fill="#e3b341" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z"/>
      <text x="24" y="13" class="label">Total Stars:</text>
      <text x="170" y="13" class="stat-val">{data['total_stars']}</text>
    </g>
    <!-- Total Commits -->
    <g transform="translate(0, 28)">
      <path fill="#3fb950" d="M11.93 8.5a4.002 4.002 0 01-7.86 0H.75a.75.75 0 010-1.5h3.32a4.002 4.002 0 017.86 0h3.32a.75.75 0 010 1.5h-3.32zM8 9.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"/>
      <text x="24" y="13" class="label">Total Commits:</text>
      <text x="170" y="13" class="stat-val">{data['total_commits']}</text>
    </g>
    <!-- Total PRs -->
    <g transform="translate(0, 56)">
      <path fill="#a371f7" d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm0 9.5a.75.75 0 100 1.5.75.75 0 000-1.5z"/>
      <text x="24" y="13" class="label">Total PRs:</text>
      <text x="170" y="13" class="stat-val">{data['total_prs']}</text>
    </g>
    <!-- Total Issues -->
    <g transform="translate(0, 84)">
      <path fill="#f85149" d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z"/>
      <text x="24" y="13" class="label">Total Issues:</text>
      <text x="170" y="13" class="stat-val">{data['total_issues']}</text>
    </g>
    <!-- Total Repos -->
    <g transform="translate(0, 112)">
      <path fill="#58a6ff" d="M2 2.5A1.5 1.5 0 013.5 1h9A1.5 1.5 0 0114 2.5v11a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 13.5v-11z"/>
      <text x="24" y="13" class="label">Public Repos:</text>
      <text x="170" y="13" class="stat-val">{data['total_repos']}</text>
    </g>
  </g>

  <!-- Rank Box -->
  <g transform="translate(320, 60)">
    <rect class="rank-bg" width="130" height="130" />
    <text x="65" y="32" class="rank-title">RANK</text>
    <text x="65" y="78" class="rank-val">{rank_letter}</text>
    <text x="65" y="108" class="rank-title">{rank_pct}</text>
  </g>
</svg>"""
    return svg

def generate_streak_svg(data):
    w, h = 480, 180
    streak_info = calculate_streak(data["days"])
    text_content = f"Contribution Streak {streak_info['current_streak']} {streak_info['longest_streak']} {streak_info['total_active']} Current Streak Longest Streak Total Active Days"
    font_css = get_font_style_css(text_content)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>
    {font_css}
    .bg {{ fill: #0d1117; rx: 12px; }}
    .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }}
    .card-bg {{ fill: #161b22; stroke: #30363d; stroke-width: 1; rx: 8px; }}
    .title {{ font-size: 16px; font-weight: 700; fill: #f0883e; }}
    .label {{ font-size: 12px; fill: #8b949e; text-anchor: middle; }}
    .val-main {{ font-size: 26px; font-weight: 700; fill: #f0883e; text-anchor: middle; }}
    .val-sec {{ font-size: 22px; font-weight: 700; fill: #c9d1d9; text-anchor: middle; }}
    .range-txt {{ font-size: 10px; fill: #6e7681; text-anchor: middle; }}
  </style>
  <rect class="bg" width="{w}" height="{h}" />
  <rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />

  <!-- Header -->
  <g transform="translate(24, 30)">
    <path fill="#f0883e" d="M8 16c3.314 0 6-2.686 6-6 0-2.47-1.49-4.59-3.61-5.51.07.45.11.91.11 1.38 0 2.45-1.33 4.59-3.33 5.74.52-1.04.83-2.21.83-3.46 0-3.14-1.81-5.86-4.44-7.15C3.78 2.05 4 3.25 4 4.5 4 7.54 2.21 10.16 0 11.45 1.13 14.12 3.84 16 7 16z"/>
    <text x="24" y="14" class="title">Contribution Streak (364 Days)</text>
  </g>

  <!-- 3 Metric Cards -->
  <!-- 1. Current Streak -->
  <g transform="translate(24, 55)">
    <rect class="card-bg" width="130" height="100" />
    <text x="65" y="28" class="label">Current Streak</text>
    <text x="65" y="62" class="val-main">{streak_info['current_streak']} days</text>
    <text x="65" y="85" class="range-txt">{streak_info['current_range']}</text>
  </g>

  <!-- 2. Longest Streak -->
  <g transform="translate(174, 55)">
    <rect class="card-bg" width="130" height="100" />
    <text x="65" y="28" class="label">Longest Streak</text>
    <text x="65" y="62" class="val-sec">{streak_info['longest_streak']} days</text>
    <text x="65" y="85" class="range-txt">{streak_info['longest_range']}</text>
  </g>

  <!-- 3. Total Active Days -->
  <g transform="translate(324, 55)">
    <rect class="card-bg" width="132" height="100" />
    <text x="66" y="28" class="label">Total Active Days</text>
    <text x="66" y="62" class="val-sec">{streak_info['total_active']} days</text>
    <text x="66" y="85" class="range-txt">Out of 364 days</text>
  </g>
</svg>"""
    return svg

def generate_langs_svg(data):
    w, h = 480, 220
    langs = data["languages"]
    total_size = sum(item["size"] for item in langs.values()) or 1

    sorted_langs = sorted(langs.items(), key=lambda x: x[1]["size"], reverse=True)[:6]

    text_content = "Most Used Languages " + " ".join([k for k, _ in sorted_langs])
    font_css = get_font_style_css(text_content)

    # Progress bar segments
    bar_x = 24
    bar_y = 65
    bar_w = 432
    bar_h = 10

    rects = []
    curr_x = bar_x
    for name, info in sorted_langs:
        pct = info["size"] / total_size
        seg_w = pct * bar_w
        if seg_w > 0:
            rects.append(f'<rect x="{curr_x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{info["color"]}" />')
            curr_x += seg_w

    # Language breakdown legend
    legend_items = []
    cols = 2
    for idx, (name, info) in enumerate(sorted_langs):
        pct = (info["size"] / total_size) * 100
        col = idx % cols
        row = idx // cols
        lx = 24 + (col * 220)
        ly = 105 + (row * 30)

        legend_items.append(f"""
    <g transform="translate({lx}, {ly})">
      <circle cx="6" cy="6" r="5" fill="{info['color']}" />
      <text x="18" y="10" font-size="13" font-weight="600" fill="#c9d1d9">{name}</text>
      <text x="140" y="10" font-size="12" fill="#8b949e">{pct:.1f}%</text>
    </g>
    """)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>
    {font_css}
    .bg {{ fill: #0d1117; rx: 12px; }}
    .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }}
    .title {{ font-size: 16px; font-weight: 700; fill: #58a6ff; }}
    .bar-bg {{ fill: #21262d; rx: 5px; }}
  </style>
  <rect class="bg" width="{w}" height="{h}" />
  <rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />

  <!-- Header -->
  <g transform="translate(24, 34)">
    <path fill="#58a6ff" d="M1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0114.25 16H1.75A1.75 1.75 0 010 14.25V1.75C0 .784.784 0 1.75 0zM8.75 3.75a.75.75 0 00-1.5 0v3.5h-3.5a.75.75 0 000 1.5h3.5v3.5a.75.75 0 001.5 0v-3.5h3.5a.75.75 0 000-1.5h-3.5v-3.5z"/>
    <text x="24" y="12" class="title">Most Used Languages</text>
  </g>

  <!-- Progress Bar Container -->
  <g clip-path="url(#bar-clip)">
    <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" class="bar-bg" rx="5" />
    {"".join(rects)}
  </g>
  <clipPath id="bar-clip">
    <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" />
  </clipPath>

  <!-- Legend -->
  {"".join(legend_items)}
</svg>"""
    return svg

def generate_year_svg(data):
    w, h = 820, 160
    days = data["days"]
    total_conts = data["total_conts"]

    text_content = f"Contributions in the last 364 days {total_conts} Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec Mon Wed Fri"
    font_css = get_font_style_css(text_content)

    # Grid parameters
    cell_size = 11
    cell_gap = 3
    grid_x = 40
    grid_y = 45

    # Group days into weeks (columns), aligned to real weekdays like GitHub's
    # calendar: column rows are always Sun(0)..Sat(6), so the first column is
    # padded with blanks up to the first day's weekday, and the last column
    # padded after the final day. Without this padding, days silently shift
    # into the wrong row and month labels attach to the wrong column.
    first_weekday = datetime.strptime(days[0]["date"], "%Y-%m-%d").isoweekday() % 7  # Sun=0..Sat=6

    padded_days = [None] * first_weekday + days
    while len(padded_days) % 7 != 0:
        padded_days.append(None)

    weeks = [padded_days[i:i + 7] for i in range(0, len(padded_days), 7)]

    rect_tags = []
    month_labels = []
    last_month = ""

    for w_idx, week in enumerate(weeks):
        x = grid_x + w_idx * (cell_size + cell_gap)
        for d_idx, day in enumerate(week):
            if day is None:
                continue
            y = grid_y + d_idx * (cell_size + cell_gap)
            c_count = day["count"]

            # GitHub level colors
            if c_count == 0:
                color = "#161b22"
            elif c_count <= 2:
                color = "#0e4429"
            elif c_count <= 5:
                color = "#006d32"
            elif c_count <= 8:
                color = "#26a641"
            else:
                color = "#39d353"

            rect_tags.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}" rx="2">'
                f'<title>{c_count} contributions on {day["date"]}</title></rect>'
            )

            # Month label positioning: label the first week-column in which a
            # new month appears, using the topmost real day in that column.
            d_obj = datetime.strptime(day["date"], "%Y-%m-%d")
            m_name = d_obj.strftime("%b")
            if m_name != last_month:
                month_labels.append(f'<text x="{x}" y="{grid_y - 8}" font-size="10" fill="#8b949e">{m_name}</text>')
                last_month = m_name

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>
    {font_css}
    .bg {{ fill: #0d1117; rx: 12px; }}
    .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }}
    .title {{ font-size: 14px; font-weight: 600; fill: #c9d1d9; }}
    .axis-label {{ font-size: 9px; fill: #6e7681; }}
  </style>
  <rect class="bg" width="{w}" height="{h}" />
  <rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />

  <!-- Header -->
  <text x="24" y="25" class="title">{total_conts} contributions in the last 364 days (UTC)</text>

  <!-- Weekday Labels -->
  <text x="18" y="{grid_y + 1 * (cell_size+cell_gap) + 9}" class="axis-label">Mon</text>
  <text x="18" y="{grid_y + 3 * (cell_size+cell_gap) + 9}" class="axis-label">Wed</text>
  <text x="18" y="{grid_y + 5 * (cell_size+cell_gap) + 9}" class="axis-label">Fri</text>

  <!-- Month Labels -->
  {"".join(month_labels)}

  <!-- Cells -->
  {"".join(rect_tags)}

  <!-- Legend -->
  <g transform="translate({w - 180}, {h - 18})">
    <text x="0" y="9" font-size="10" fill="#6e7681">Less</text>
    <rect x="30" y="0" width="10" height="10" fill="#161b22" rx="2"/>
    <rect x="44" y="0" width="10" height="10" fill="#0e4429" rx="2"/>
    <rect x="58" y="0" width="10" height="10" fill="#006d32" rx="2"/>
    <rect x="72" y="0" width="10" height="10" fill="#26a641" rx="2"/>
    <rect x="86" y="0" width="10" height="10" fill="#39d353" rx="2"/>
    <text x="104" y="9" font-size="10" fill="#6e7681">More</text>
  </g>
</svg>"""
    return svg

def main():
    print("Fetching GitHub stats...")
    data = fetch_github_stats()

    print("Generating SVGs...")
    stats_svg = generate_stats_svg(data)
    streak_svg = generate_streak_svg(data)
    langs_svg = generate_langs_svg(data)
    year_svg = generate_year_svg(data)

    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write(stats_svg)
    print("Saved stats.svg")

    with open("streak.svg", "w", encoding="utf-8") as f:
        f.write(streak_svg)
    print("Saved streak.svg")

    with open("langs.svg", "w", encoding="utf-8") as f:
        f.write(langs_svg)
    print("Saved langs.svg")

    with open("year.svg", "w", encoding="utf-8") as f:
        f.write(year_svg)
    print("Saved year.svg")

    print("All stats SVGs generated successfully!")

if __name__ == "__main__":
    main()