#!/usr/bin/env python3
"""Generate an animated SVG of a panda eating your GitHub contribution graph.

Usage:
    GITHUB_TOKEN=xxx python panda.py <github_user> <out_dir>
    python panda.py --demo <out_dir>          # fake data, for local testing
"""
import json
import os
import random
import sys
import urllib.request

CELL, GAP = 11, 3
PITCH = CELL + GAP
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 14, 18, 14
STEP_SECONDS = 0.09     # time the panda spends per cell
WALK_FRACTION = 0.9     # rest of the loop the panda sits still before restarting

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

THEMES = {
    "light": {"empty": "#ebedf0",
              "bamboo": ["#c9e9a6", "#8fcf6a", "#4fa83d", "#2e7d32"],
              "outline": "#1f2328"},
    "dark":  {"empty": "#161b22",
              "bamboo": ["#0e4429", "#006d32", "#26a641", "#39d353"],
              "outline": "#d0d7de"},
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date weekday contributionLevel } }
      }
    }
  }
}
"""


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "panda-contrib"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data or not data.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {data}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(d["weekday"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in weeks]


def demo():
    random.seed(7)
    weeks = []
    for _ in range(53):
        weeks.append([(d, random.choice([0, 0, 0, 1, 1, 2, 3, 4])) for d in range(7)])
    return weeks


def panda(outline):
    return f"""
<g>
  <circle cx="-7" cy="-7" r="3.8" fill="#1f2328"/>
  <circle cx="7" cy="-7" r="3.8" fill="#1f2328"/>
  <circle r="9" fill="#ffffff" stroke="{outline}" stroke-width="1.2"/>
  <ellipse cx="-3.7" cy="-0.8" rx="2.5" ry="3.2" transform="rotate(25 -3.7 -0.8)" fill="#1f2328"/>
  <ellipse cx="3.7" cy="-0.8" rx="2.5" ry="3.2" transform="rotate(-25 3.7 -0.8)" fill="#1f2328"/>
  <circle cx="-3.5" cy="-1.4" r="0.9" fill="#fff"/>
  <circle cx="3.5" cy="-1.4" r="0.9" fill="#fff"/>
  <ellipse cx="0" cy="2.6" rx="1.7" ry="1.2" fill="#1f2328"/>
  <path d="M-2 4.6 Q0 6.4 2 4.6" stroke="#1f2328" stroke-width="0.9" fill="none" stroke-linecap="round"/>
  <animateTransform attributeName="transform" type="scale"
    values="1 1;1.08 0.92;1 1" dur="0.36s" repeatCount="indefinite"/>
</g>"""


def build(weeks, theme):
    t = THEMES[theme]
    ncols = len(weeks)
    width = MARGIN_X * 2 + ncols * PITCH - GAP
    height = MARGIN_TOP + MARGIN_BOTTOM + 7 * PITCH - GAP

    def center(c, r):
        return (MARGIN_X + c * PITCH + CELL / 2, MARGIN_TOP + r * PITCH + CELL / 2)

    # walk order: down even columns, up odd columns (every step is exactly one cell)
    order = []
    for c in range(ncols):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        order += [(c, r) for r in rows]
    n = len(order)
    dur = n * STEP_SECONDS / WALK_FRACTION

    level_at = {}
    for c, week in enumerate(weeks):
        for weekday, lvl in week:
            level_at[(c, weekday)] = lvl

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'width="{width}" height="{height}" role="img" '
           f'aria-label="A panda eating the GitHub contribution graph">']

    # empty grid
    for (c, r) in level_at:
        x, y = MARGIN_X + c * PITCH, MARGIN_TOP + r * PITCH
        out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{t["empty"]}"/>')

    # bamboo (contributions) that vanish when the panda arrives
    for i, (c, r) in enumerate(order):
        lvl = level_at.get((c, r), 0)
        if lvl == 0:
            continue
        x, y = MARGIN_X + c * PITCH, MARGIN_TOP + r * PITCH
        ti = WALK_FRACTION * (i + 0.5) / n
        out.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{t["bamboo"][lvl - 1]}">'
            f'<animate attributeName="opacity" values="1;1;0;0" '
            f'keyTimes="0;{ti:.5f};{ti + 0.0008:.5f};1" dur="{dur:.2f}s" repeatCount="indefinite"/></rect>')

    # the panda walks the path
    pts = [center(c, r) for c, r in order]
    path = f"M{pts[0][0]:.1f} {pts[0][1]:.1f} " + " ".join(f"L{x:.1f} {y:.1f}" for x, y in pts[1:])
    out.append(f'<g>{panda(t["outline"])}'
               f'<animateMotion path="{path}" dur="{dur:.2f}s" repeatCount="indefinite" '
               f'calcMode="linear" keyPoints="0;1;1" keyTimes="0;{WALK_FRACTION};1"/></g>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--demo":
        weeks, out_dir = demo(), args[1]
    else:
        user, out_dir = args[0], args[1]
        weeks = fetch(user, os.environ["GITHUB_TOKEN"])
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(out_dir, f"panda-contribution-{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(weeks, theme))
        print("wrote", path)


if __name__ == "__main__":
    main()
