#!/usr/bin/env python3
"""
Generate an animated Pac-Man SVG from a GitHub contribution calendar.

- Fetches the contribution calendar via GitHub's GraphQL API.
- Builds a 52(week) x 7(day) grid.
- Colors each active cell by activity tier using three DISTINCT hues
  (not shades of one color) chosen for contrast on OLED/AMOLED/LCD/
  laptop/mobile displays:
    LOW    -> Amber / Gold   (#FFC300)
    MID    -> Cyan / Teal    (#00E5FF)
    HIGH   -> Magenta / Pink (#FF2FB0)
  Empty days are a neutral dark slate so the graph reads well on both
  light and dark GitHub themes.
- Computes a path through active cells and animates Pac-Man (plus a
  chasing ghost) travelling the grid and "eating" each dot in turn.
- Outputs a single self-contained animated SVG (pacman.svg) and a
  light-theme variant (pacman-light.svg).
"""

import json
import os
import sys
import urllib.request

USERNAME = os.environ.get("GITHUB_USER_NAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT_DIR = os.environ.get("OUT_DIR", ".")

CELL = 12
GAP = 3
STEP = CELL + GAP
MARGIN = 20

# --- GitHub-native contribution palette ---
COLOR_EMPTY_DARK = "#161b22"
COLOR_EMPTY_LIGHT = "#ebedf0"
COLOR_LOW = "#9be9a8"    # GitHub green 1
COLOR_MID = "#40c463"    # GitHub green 2
COLOR_HIGH = "#216e39"   # GitHub green 4

PACMAN_COLOR = "#2ea043"
GHOST_COLOR = "#1f883d"  # darker green to match GitHub contribution theme


def fetch_calendar():
    if not USERNAME:
        print("ERROR: GITHUB_USER_NAME not set", file=sys.stderr)
        sys.exit(1)
    if not TOKEN:
        print("ERROR: GITHUB_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "pacman-contribution-graph",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    grid = []
    for i, w in enumerate(weeks):
        col = [d["contributionCount"] for d in w["contributionDays"]]
        if len(col) < 7:
            missing = 7 - len(col)
            if i == 0:
                col = [0] * missing + col
            elif i == len(weeks) - 1:
                col = col + [0] * missing
            else:
                col = [0] * missing + col
        elif len(col) > 7:
            col = col[:7]
        grid.append(col)
    return grid


def tier(count, low_max, mid_max):
    if count <= 0:
        return None
    if count <= low_max:
        return "low"
    if count <= mid_max:
        return "mid"
    return "high"


def compute_thresholds(grid):
    counts = sorted(c for col in grid for c in col if c > 0)
    if not counts:
        return 1, 3
    n = len(counts)
    low_max = counts[max(0, n // 3 - 1)] if n >= 3 else counts[0]
    mid_max = counts[max(0, (2 * n) // 3 - 1)] if n >= 3 else counts[-1]
    if mid_max <= low_max:
        mid_max = low_max + 1
    return low_max, mid_max


def build_path(grid):
    """Simple boustrophedon (snake) path through every active cell, in
    column (week) order, alternating direction each column so Pac-Man's
    motion stays continuous without long jumps."""
    path = []
    for x, col in enumerate(grid):
        if not col:
            continue
        ys = range(7) if x % 2 == 0 else range(6, -1, -1)
        for y in ys:
            if y < len(col) and col[y] > 0:
                path.append((x, y))
    return path


def color_for(count, low_max, mid_max, empty_color):
    t = tier(count, low_max, mid_max)
    if t is None:
        return empty_color
    return {"low": COLOR_LOW, "mid": COLOR_MID, "high": COLOR_HIGH}[t]


def render_svg(grid, path, dark=True):
    weeks = len(grid)
    width = MARGIN * 2 + weeks * STEP
    height = MARGIN * 2 + 7 * STEP + 30

    empty_color = COLOR_EMPTY_DARK if dark else COLOR_EMPTY_LIGHT
    bg = "#05070d" if dark else "#ffffff"
    text_color = "#c9d1d9" if dark else "#24292f"

    low_max, mid_max = compute_thresholds(grid)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    svg.append(f'<rect width="100%" height="100%" fill="{bg}"/>')
    svg.append(
        f'<text x="{MARGIN}" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="12" fill="{text_color}">Pac-Man Contribution Graph</text>'
    )

    grid_y0 = MARGIN + 20

    # legend
    legend_x = width - MARGIN - 260
    legend_y = 18
    legend_items = [("Low", COLOR_LOW), ("Mid", COLOR_MID), ("High", COLOR_HIGH)]
    lx = legend_x
    for label, col in legend_items:
        svg.append(f'<rect x="{lx}" y="{legend_y-9}" width="10" height="10" rx="2" fill="{col}"/>')
        svg.append(
            f'<text x="{lx+14}" y="{legend_y}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="10" fill="{text_color}">{label}</text>'
        )
        lx += 70

    # cells
    dot_ids = []
    for x, col in enumerate(grid):
        for y, count in enumerate(col):
            cx = MARGIN + x * STEP
            cy = grid_y0 + y * STEP
            fill = color_for(count, low_max, mid_max, empty_color)
            svg.append(
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="3" fill="{empty_color}"/>'
            )
            if count > 0:
                dot_id = f"dot_{x}_{y}"
                dot_ids.append(dot_id)
                r = 3.2
                svg.append(
                    f'<circle id="{dot_id}" cx="{cx + CELL/2}" cy="{cy + CELL/2}" r="{r}" '
                    f'fill="{fill}">'
                    f'</circle>'
                )

    # partition walls to create a table-like maze with visual sections
    partition_color = "#3d4559" if dark else "#bcc5d1"
    for group_start in range(0, weeks, 4):
        group_end = min(weeks, group_start + 4)
        x0 = MARGIN + group_start * STEP - 4
        x1 = MARGIN + group_end * STEP - 4
        for x in range(group_start, group_end):
            line_x = MARGIN + x * STEP + CELL / 2
            svg.append(
                f'<line x1="{line_x}" y1="{grid_y0 - 6}" x2="{line_x}" y2="{grid_y0 + 7 * STEP + 6}" '
                f'stroke="{partition_color}" stroke-width="2" opacity="0.75"/>'
            )
        svg.append(
            f'<rect x="{x0}" y="{grid_y0 - 8}" width="{max(1, x1 - x0)}" height="{7 * STEP + 16}" '
            f'fill="none" stroke="{partition_color}" stroke-width="2" rx="8" opacity="0.75"/>'
        )

    # animation timing
    n = len(path)
    if n == 0:
        svg.append("</svg>")
        return "\n".join(svg)

    total_duration = max(20, min(60, n * 0.35))
    step_dur = total_duration / n

    def cell_center(x, y):
        return (MARGIN + x * STEP + CELL / 2, grid_y0 + y * STEP + CELL / 2)

    points = [cell_center(x, y) for x, y in path]
    path_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)

    # dot fade-out keyTimes aligned to when pacman reaches that cell
    key_map = {f"dot_{x}_{y}": i for i, (x, y) in enumerate(path)}
    for dot_id, idx in key_map.items():
        t_eat = idx / n
        svg.append(
            f'<animate xlink:href="#{dot_id}" attributeName="opacity" '
            f'values="1;1;0;0" keyTimes="0;{max(t_eat-0.001,0):.4f};{t_eat:.4f};1" '
            f'dur="{total_duration:.2f}s" begin="0s" repeatCount="indefinite" fill="freeze"/>'
        )

    # Pac-Man sprite (one escape runner moving through partitions)
    svg.append(
        f'<g id="pacman">'
        f'<circle r="6.5" fill="{PACMAN_COLOR}"/>'
        f'<path d="M0,0 L7,-3 A7,7 0 1,1 7,3 Z" fill="{bg}">'
        f'<animateTransform attributeName="transform" type="rotate" '
        f'values="0;40;0;-40;0" dur="0.4s" repeatCount="indefinite"/>'
        f'</path>'
        f'<animateMotion dur="{total_duration:.2f}s" repeatCount="indefinite" '
        f'rotate="auto" path="M{path_str.replace(" ", " L")}"/>'
        f'</g>'
    )

    # multiple hunters weaving through the partitions
    ghost_colors = ["#1f883d", "#2ea043", "#3fb950", "#66d98b", "#a6f3b5"]
    for idx, color in enumerate(ghost_colors):
        start_offset = max(1, n // (len(ghost_colors) + 2) * (idx + 1))
        ghost_points = points[start_offset:] + points[:start_offset]
        ghost_path_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in ghost_points)
        ghost_delay = (idx * total_duration) / len(ghost_colors)
        svg.append(
            f'<g id="ghost_{idx}">'
            f'<path d="M-6,2 A6,6 0 1,1 6,2 L6,7 L3,5 L0,7 L-3,5 L-6,7 Z" fill="{color}"/>'
            f'<circle cx="-2.3" cy="-1" r="1.6" fill="white"/>'
            f'<circle cx="2.3" cy="-1" r="1.6" fill="white"/>'
            f'<circle cx="-2.3" cy="-1" r="0.8" fill="#111"/>'
            f'<circle cx="2.3" cy="-1" r="0.8" fill="#111"/>'
            f'<animateMotion dur="{total_duration:.2f}s" begin="-{ghost_delay:.2f}s" repeatCount="indefinite" '
            f'path="M{ghost_path_str.replace(" ", " L")}"/>'
            f'</g>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def main():
    grid = fetch_calendar()
    path = build_path(grid)

    dark_svg = render_svg(grid, path, dark=True)
    light_svg = render_svg(grid, path, dark=False)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "pacman.svg"), "w") as f:
        f.write(dark_svg)
    with open(os.path.join(OUT_DIR, "pacman-light.svg"), "w") as f:
        f.write(light_svg)

    print(f"Generated pacman.svg and pacman-light.svg in {OUT_DIR} "
          f"({len(path)} active cells)")


if __name__ == "__main__":
    main()