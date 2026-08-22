#!/usr/bin/env python3
"""
scripts/generate_stats.py
Fetches GitHub profile stats using GraphQL API, subsets font, and generates:
stats.svg, streak.svg, and langs.svg.
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
        chars = "".join(set(text_content + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.:,+-*/%#@! ()[]{}<>&|_~'\""))
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
    body, text {{ font-family: 'JetBrains Mono', monospace; }}
    """

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
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
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
        "variables": {"username": username, "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}
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
    total_issues = col["totalIssueContributions"]
    total_repos = user_data["repositories"]["totalCount"]
    total_conts = cal["totalContributions"]

    lang_map = {}
    for r in repos:
        for edge in r.get("languages", {}).get("edges", []):
            lname = edge["node"]["name"]
            lcolor = edge["node"]["color"] or "#858585"
            lsize = edge["size"]
            if lname not in lang_map:
                lang_map[lname] = {"size": 0, "color": lcolor}
            lang_map[lname]["size"] += lsize

    days_list = []
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            days_list.append({"date": d["date"], "count": d["contributionCount"], "color": d["color"], "weekday": d["weekday"]})

    return {
        "username": user_data["login"],
        "name": user_data.get("name") or user_data["login"],
        "total_stars": total_stars, "total_forks": total_forks,
        "total_commits": total_commits, "total_prs": total_prs,
        "total_issues": total_issues, "total_repos": total_repos,
        "total_conts": total_conts, "languages": lang_map,
        "days": days_list, "from_dt": from_dt, "to_dt": to_dt
    }

def generate_fallback_stats(username, from_dt, to_dt):
    print("Using fallback dummy stats.")
    days_list, curr, total_c = [], from_dt, 0
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    while curr <= to_dt:
        d_str = curr.strftime("%Y-%m-%d")
        # Give a couple of recent active days so dates show up even on fallback
        c_val = 2 if d_str in [today_str, yesterday_str] else (1 if curr.weekday() < 5 else 0)
        days_list.append({"date": d_str, "count": c_val, "color": "#26a641" if c_val > 0 else "#161b22", "weekday": curr.weekday()})
        total_c += c_val
        curr += timedelta(days=1)
    return {
        "username": username, "name": username, "total_stars": 12, "total_forks": 4,
        "total_commits": 148, "total_prs": 18, "total_issues": 6, "total_repos": 14,
        "total_conts": total_c, "languages": {"JavaScript": {"size": 450000, "color": "#f1e05a"}},
        "days": days_list, "from_dt": from_dt, "to_dt": to_dt
    }

def calculate_rank(data):
    score = data["total_stars"] * 4 + data["total_commits"] * 0.5 + data["total_prs"] * 3
    if score >= 200: return "A+", "TOP 5%"
    if score >= 100: return "A", "TOP 15%"
    return "B+", "TOP 30%"

def format_date_str(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
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
            
    # Fallback bounds if streaks are empty
    if not curr_start and days_list:
        curr_start = days_list[-1]["date"]
        curr_end = days_list[-1]["date"]
    if not max_start and days_list:
        max_start = days_list[0]["date"]
        max_end = days_list[0]["date"]

    return {
        "current_streak": curr_streak, 
        "longest_streak": max_streak, 
        "total_active": total_active,
        "curr_range": f"{format_date_str(curr_start)} To {format_date_str(curr_end)}",
        "long_range": f"{format_date_str(max_start)} To {format_date_str(max_end)}"
    }

def generate_stats_svg(data):
    w, h = 480, 220
    rank_letter, rank_pct = calculate_rank(data)
    font_css = get_font_style_css(data['name'])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>{font_css} .bg {{ fill: #0d1117; rx: 12px; }} .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }} .title {{ font-size: 16px; font-weight: 700; fill: #58a6ff; }} .label {{ font-size: 13px; fill: #8b949e; }} .stat-val {{ font-size: 14px; font-weight: 700; fill: #c9d1d9; }}</style>
  <rect class="bg" width="{w}" height="{h}" /><rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />
  <g transform="translate(24, 34)"><text x="0" y="12" class="title">{data['name']}'s GitHub Stats</text></g>
  <g transform="translate(24, 65)">
    <text x="24" y="13" class="label">Total Stars:</text><text x="170" y="13" class="stat-val">{data['total_stars']}</text>
    <text x="24" y="41" class="label">Total Commits:</text><text x="170" y="41" class="stat-val">{data['total_commits']}</text>
    <text x="24" y="69" class="label">Total PRs:</text><text x="170" y="69" class="stat-val">{data['total_prs']}</text>
    <text x="24" y="97" class="label">Total Issues:</text><text x="170" y="97" class="stat-val">{data['total_issues']}</text>
    <text x="24" y="125" class="label">Public Repos:</text><text x="170" y="125" class="stat-val">{data['total_repos']}</text>
  </g>
  <g transform="translate(320, 60)">
    <rect fill="#161b22" stroke="#30363d" width="130" height="130" rx="8" />
    <text x="65" y="32" font-size="11" fill="#8b949e" text-anchor="middle">RANK</text>
    <text x="65" y="78" font-size="28" font-weight="700" fill="#3fb950" text-anchor="middle">{rank_letter}</text>
    <text x="65" y="108" font-size="11" fill="#8b949e" text-anchor="middle">{rank_pct}</text>
  </g>
</svg>"""

def generate_streak_svg(data):
    w, h = 480, 180
    s = calculate_streak(data["days"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>.bg {{ fill: #0d1117; rx: 12px; }} .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }} .card {{ fill: #161b22; stroke: #30363d; rx: 8px; }}</style>
  <rect class="bg" width="{w}" height="{h}" /><rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />
  <g transform="translate(24, 30)"><text x="0" y="14" font-size="16" font-weight="700" fill="#f0883e">Contribution Streak</text></g>
  <g transform="translate(24, 55)"><rect class="card" width="130" height="100"/><text x="65" y="26" font-size="12" fill="#8b949e" text-anchor="middle">Current Streak</text><text x="65" y="58" font-size="22" font-weight="700" fill="#f0883e" text-anchor="middle">{s['current_streak']}d</text><text x="65" y="82" font-size="8.5" fill="#8b949e" text-anchor="middle">{s['curr_range']}</text></g>
  <g transform="translate(174, 55)"><rect class="card" width="130" height="100"/><text x="65" y="26" font-size="12" fill="#8b949e" text-anchor="middle">Longest Streak</text><text x="65" y="58" font-size="22" font-weight="700" fill="#c9d1d9" text-anchor="middle">{s['longest_streak']}d</text><text x="65" y="82" font-size="8.5" fill="#8b949e" text-anchor="middle">{s['long_range']}</text></g>
  <g transform="translate(324, 55)"><rect class="card" width="132" height="100"/><text x="66" y="30" font-size="12" fill="#8b949e" text-anchor="middle">Active Days</text><text x="66" y="65" font-size="24" font-weight="700" fill="#c9d1d9" text-anchor="middle">{s['total_active']}</text></g>
</svg>"""

def generate_langs_svg(data):
    w, h = 480, 220
    langs = sorted(data["languages"].items(), key=lambda x: x[1]["size"], reverse=True)[:5]
    total = sum(i["size"] for _, i in langs) or 1
    rects, curr_x, legend = [], 24, []
    for idx, (name, info) in enumerate(langs):
        seg_w = (info["size"] / total) * 432
        rects.append(f'<rect x="{curr_x}" y="65" width="{seg_w}" height="10" fill="{info["color"]}" />')
        curr_x += seg_w
        legend.append(f'<circle cx="{24 + (idx%2)*220}" cy="{105 + (idx//2)*30}" r="5" fill="{info["color"]}" /><text x="{42 + (idx%2)*220}" y="{109 + (idx//2)*30}" font-size="13" fill="#c9d1d9">{name}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <style>.bg {{ fill: #0d1117; rx: 12px; }} .border {{ fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; }}</style>
  <rect class="bg" width="{w}" height="{h}" /><rect class="border" width="{w-2}" height="{h-2}" x="1" y="1" />
  <g transform="translate(24, 34)"><text x="0" y="12" font-size="16" font-weight="700" fill="#58a6ff">Most Used Languages</text></g>
  <rect x="24" y="65" width="432" height="10" fill="#21262d" rx="5"/>{"".join(rects)}{"".join(legend)}
</svg>"""

def main():
    data = fetch_github_stats()
    with open("stats.svg", "w", encoding="utf-8") as f: f.write(generate_stats_svg(data))
    with open("streak.svg", "w", encoding="utf-8") as f: f.write(generate_streak_svg(data))
    with open("langs.svg", "w", encoding="utf-8") as f: f.write(generate_langs_svg(data))
    print("Stats SVGs generated successfully!")

if __name__ == "__main__":
    main()