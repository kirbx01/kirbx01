import os
import re
import base64
import datetime
import requests

GITHUB_USER = os.environ.get("GH_USERNAME", "kirbx01")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


OUTPUT_SVG = os.path.join(_repo_root(), "profile-htop.svg")
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ModernDOS8x16.ttf")

EXCLUDED_LANGUAGES = {"Jupyter Notebook"}

RECENT_ACTIVITY_DAYS = 60

COLOR_BG = "#0000a8"
COLOR_BORDER = "#aaaaaa"
COLOR_MAIN = "#aaaaaa"
COLOR_TEXT = "#ffffff"
COLOR_CYAN = "#55ffff"
COLOR_DIM = "#8888b8"
COLOR_RED = "#ff5555"
COLOR_SEL_TXT = "#0000a8"
COLOR_SEL_DIM = "#404040"

LANG_COLOR_FALLBACK = {
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "C++": "#f34b7d",
    "C": "#7a7a7a",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Arduino": "#bd79d1",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
}

GRID_LEVEL_COLORS = ["#000040", "#233bb8", "#4d63db", "#8f9ff0", "#ffffff"]


def format_large_number(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


def _fallback_data(reason: str) -> dict:
    print(f"::warning:: profile-htop: using DEMO data: {reason}")
    return {
        "account_age": "N/A",
        "total_contributions": "0",
        "total_commits": "0",
        "total_prs": "0",
        "total_issues": "0",
        "total_reviews": "0",
        "total_repos": "0",
        "total_stars": "0",
        "contrib": [],
        "languages": [
            {"name": "Go", "pct": 32.0, "color": LANG_COLOR_FALLBACK["Go"]},
            {"name": "Python", "pct": 26.0, "color": LANG_COLOR_FALLBACK["Python"]},
            {"name": "C++", "pct": 21.0, "color": LANG_COLOR_FALLBACK["C++"]},
            {"name": "Arduino", "pct": 13.0, "color": LANG_COLOR_FALLBACK["Arduino"]},
            {"name": "Shell", "pct": 8.0, "color": LANG_COLOR_FALLBACK["Shell"]},
        ],
        "fallback": True,
    }


def get_profile_contribution_total(headers: dict) -> int | None:
    try:
        response = requests.get(
            f"https://github.com/users/{GITHUB_USER}/contributions",
            headers={**headers, "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
            timeout=15,
        )
        response.raise_for_status()
        match = re.search(r"(\d[\d,]*)\s+contributions?\s+in\s+the\s+last\s+year", response.text)
        if match:
            return int(match.group(1).replace(",", ""))
        return None
    except Exception:
        return None


def scrape_contrib_public(headers: dict) -> tuple[int | None, list[dict]]:
    try:
        response = requests.get(
            f"https://github.com/users/{GITHUB_USER}/contributions",
            headers={**headers, "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
            timeout=15,
        )
        response.raise_for_status()
        text = response.text
        total = None
        match = re.search(r"(\d[\d,]*)\s+contributions?\s+in\s+the\s+last\s+year", text)
        if match:
            total = int(match.group(1).replace(",", ""))
        cells = []
        for td in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", text):
            md = re.search(r'data-date="([\d-]+)"', td)
            ml = re.search(r'data-level="(\d)"', td)
            if md and ml:
                cells.append({"date": md.group(1), "level": int(ml.group(1))})
        return total, cells
    except Exception:
        return None, []


def _contrib_columns(days: list[dict]) -> list[list[dict]]:
    cells = sorted(days, key=lambda d: d["date"])
    if not cells:
        return []
    cols: list[list[dict]] = []
    cur: list[dict] = []
    first = datetime.date.fromisoformat(cells[0]["date"])
    pad = (first.weekday() + 1) % 7
    cur = [{"date": "", "level": 0} for _ in range(pad)]
    for day in cells:
        cur.append(day)
        if len(cur) == 7:
            cols.append(cur)
            cur = []
    if cur:
        cols.append(cur)
    return cols


def get_github_data_public() -> dict:
    def rest(path, **params):
        resp = requests.get(
            f"https://api.github.com{path}",
            params=params,
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    u = rest(f"/users/{GITHUB_USER}")
    created_at = datetime.datetime.strptime(u["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    delta = now - created_at
    years = delta.days // 365
    months = (delta.days % 365) // 30
    age_str = f"{years} yrs, {months} mos" if years > 0 else f"{months} mos"

    def search_count(query: str) -> int:
        try:
            j = rest("/search/issues", q=query, per_page=1)
            return int(j.get("total_count") or 0)
        except Exception:
            return 0

    total_prs = search_count(f"author:{GITHUB_USER} type:pr")
    total_issues = search_count(f"author:{GITHUB_USER} type:issue")

    repos = rest(f"/users/{GITHUB_USER}/repos", per_page=100, sort="pushed", type="owner")
    total_stars = sum(r.get("stargazers_count") or 0 for r in repos)

    lang_counts: dict[str, int] = {}
    lang_colors: dict[str, str] = {}
    for r in repos:
        name = r.get("language")
        if not name or name in EXCLUDED_LANGUAGES:
            continue
        lang_counts[name] = lang_counts.get(name, 0) + 1
        lang_colors[name] = LANG_COLOR_FALLBACK.get(name, COLOR_DIM)

    total_langs = sum(lang_counts.values()) or 1
    top_langs = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    languages = [
        {"name": name, "pct": round(count / total_langs * 100, 1), "color": lang_colors[name]}
        for name, count in top_langs
    ]

    year_total, contrib_cells = scrape_contrib_public({})
    year_total = year_total or 0

    return {
        "account_age": age_str,
        "total_contributions": format_large_number(year_total),
        "total_commits": format_large_number(year_total),
        "total_prs": format_large_number(total_prs),
        "total_issues": format_large_number(total_issues),
        "total_reviews": "0",
        "total_repos": format_large_number(len(repos)),
        "total_stars": format_large_number(total_stars),
        "contrib": contrib_cells,
        "languages": languages,
        "fallback": False,
    }


def get_github_data() -> dict:
    if not TOKEN:
        try:
            return get_github_data_public()
        except Exception as e:
            return _fallback_data(f"no token and public fetch failed: {e}")

    headers = {
        "Authorization": f"bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    query = """
    query($user: String!) {
      user(login: $user) {
        createdAt
        contributionsCollection {
          totalCommitContributions
          totalPullRequestReviewContributions
          contributionCalendar {
          totalContributions
          weeks {
            contributionDays { date contributionCount contributionLevel }
          }
        }
        }
        pullRequests { totalCount }
        issues { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
          totalCount
          nodes {
            stargazerCount
            pushedAt
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node { name color }
              }
            }
          }
        }
      }
    }
    """

    try:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"user": GITHUB_USER}},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        res_json = response.json()

        if "errors" in res_json:
            print(f"::warning:: GraphQL errors, using public data: {res_json['errors']}")
            return get_github_data_public()

        user = res_json.get("data", {}).get("user")
        if not user:
            print(f"::warning:: no user object for '{GITHUB_USER}', using public data")
            return get_github_data_public()

        created_at = datetime.datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        delta = now - created_at
        years = delta.days // 365
        months = (delta.days % 365) // 30
        age_str = f"{years} yrs, {months} mos" if years > 0 else f"{months} mos"

        cc = user.get("contributionsCollection") or {}
        total_commits = cc.get("totalCommitContributions") or 0
        total_reviews = cc.get("totalPullRequestReviewContributions") or 0
        total_contribs = (cc.get("contributionCalendar") or {}).get("totalContributions") or 0

        profile_total = get_profile_contribution_total(headers)
        if profile_total is not None:
            total_contribs = profile_total
            if total_commits == 0:
                total_commits = profile_total

        total_prs = user["pullRequests"]["totalCount"]
        total_issues = user["issues"]["totalCount"]

        LEVEL_MAP = {
            "NONE": 0,
            "FIRST_QUARTILE": 1,
            "SECOND_QUARTILE": 2,
            "THIRD_QUARTILE": 3,
            "FOURTH_QUARTILE": 4,
        }
        calendar = (cc.get("contributionCalendar") or {})
        contrib_days = [
            {"date": d["date"], "level": LEVEL_MAP.get(d.get("contributionLevel"), 0)}
            for week in calendar.get("weeks") or []
            for d in week.get("contributionDays") or []
        ]

        repos = user["repositories"]["nodes"]
        total_repos = user["repositories"]["totalCount"]
        total_stars = sum(r["stargazerCount"] for r in repos)

        if RECENT_ACTIVITY_DAYS is not None:
            cutoff = now - datetime.timedelta(days=RECENT_ACTIVITY_DAYS)
            lang_source_repos = [
                r for r in repos
                if datetime.datetime.strptime(r["pushedAt"], "%Y-%m-%dT%H:%M:%SZ") >= cutoff
            ]
            if not lang_source_repos:
                lang_source_repos = repos
        else:
            lang_source_repos = repos

        lang_counts: dict[str, int] = {}
        lang_colors: dict[str, str] = {}
        for r in lang_source_repos:
            edges = r["languages"]["edges"]
            if not edges:
                continue
            top = max(edges, key=lambda e: e["size"])
            name = top["node"]["name"]
            if name in EXCLUDED_LANGUAGES:
                continue
            lang_counts[name] = lang_counts.get(name, 0) + 1
            lang_colors[name] = top["node"]["color"] or LANG_COLOR_FALLBACK.get(name, COLOR_DIM)

        total_langs = sum(lang_counts.values()) or 1
        top_langs = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        languages = [
            {
                "name": name,
                "pct": round(count / total_langs * 100, 1),
                "color": lang_colors[name],
            }
            for name, count in top_langs
        ]
        if not languages:
            languages = _fallback_data("no languages found")["languages"]

        return {
            "account_age": age_str,
            "total_contributions": format_large_number(total_contribs),
            "total_commits": format_large_number(total_commits),
            "total_prs": format_large_number(total_prs),
            "total_issues": format_large_number(total_issues),
            "total_reviews": format_large_number(total_reviews),
            "total_repos": format_large_number(total_repos),
            "total_stars": format_large_number(total_stars),
            "contrib": contrib_days,
            "languages": languages,
            "fallback": False,
        }

    except Exception as e:
        print(f"::warning:: GraphQL fetch failed, using public data: {e}")
        try:
            return get_github_data_public()
        except Exception as e2:
            return _fallback_data(f"all data sources failed: {e2}")


def _font_css() -> str:
    try:
        with open(FONT_PATH, "rb") as f:
            b = base64.b64encode(f.read()).decode("ascii")
        return f"@font-face{{font-family:'ModernDOS';src:url(data:font/ttf;base64,{b}) format('truetype');}}"
    except Exception:
        return ""


def _fade_in(index: int, base_delay: float = 0.1) -> str:
    delay = round(base_delay * index, 2)
    return f'<animate attributeName="opacity" from="0" to="1" begin="{delay}s" dur="0.3s" fill="freeze"/>'


def _lang_bars(data: dict, start_y: int, x0: int, label_w: int, bar_x: int, bar_w: int) -> str:
    rows = []
    for i, lang in enumerate(data["languages"]):
        y = start_y + i * 19
        target = round(bar_w * lang["pct"] / 100, 1)
        delay = round(0.12 * i, 2)
        rows.append(
            f'''    <text x="{x0}" y="{y + 11}" class="seldim">{lang['name'][:12]:<12}</text>
    <rect x="{bar_x}" y="{y}" width="{bar_w}" height="{12}" fill="#d9d9d9"/>
    <rect x="{bar_x}" y="{y}" width="0" height="{12}" fill="{lang['color']}">
        <animate attributeName="width" from="0" to="{target}" begin="{delay}s" dur="1.0s" fill="freeze"/>
    </rect>
    <text x="{bar_x + bar_w + 14}" y="{y + 11}" class="seldim">{lang['pct']:.1f}%</text>'''
        )
    return "".join(rows)


def generate_svg(data: dict) -> str:
    W = 800
    x0 = 36
    x1 = W - x0
    nlang = len(data["languages"])

    stat_pairs = [
        ("Total Commits", "total_commits"),
        ("Pull Requests", "total_prs"),
        ("Repositories", "total_repos"),
        ("Issues", "total_issues"),
        ("Stars", "total_stars"),
        ("Year Contributions", "total_contributions"),
    ]

    sel_item_y = 76
    sel_title_y = sel_item_y + 30
    stat_y = [sel_title_y + 26 + 21 * i for i in range(len(stat_pairs))]
    lang_title_y = stat_y[-1] + 32
    bar_y_start = lang_title_y + 16
    if nlang:
        bar_y = [bar_y_start + 19 * i for i in range(nlang)]
        sel_box_h = bar_y[-1] + 24
    else:
        sel_box_h = lang_title_y + 16

    contrib_title_y = sel_item_y + sel_box_h + 30
    grid_y = contrib_title_y + 22

    cell = 10
    gap = 2
    step = cell + gap
    cols = _contrib_columns(data.get("contrib") or [])[-53:]
    grid_w = len(cols) * step
    grid_h = 7 * step
    grid_x = (W - grid_w) // 2

    foot_y = grid_y + grid_h + 34
    H = foot_y + 84

    stat_rows = []
    for i, (label, key) in enumerate(stat_pairs):
        y = stat_y[i]
        stat_rows.append(
            f'''      <text x="{x0 + 20}" y="{y}" class="seldim">{label}</text>
      <text x="{x1 - 20}" y="{y}" text-anchor="end" class="sel" font-size="17">{data[key]}{_fade_in(i, 0.08)}</text>'''
        )

    lang_block = ""
    if nlang:
        lang_block = (
            f'    <text x="{x0 + 20}" y="{lang_title_y}" class="sel" font-size="15">Primary Languages{_fade_in(6, 0.1)}</text>'
            + "\n"
            + _lang_bars(data, bar_y_start, x0 + 20, 20, 280, 380)
            + "\n"
        )

    contrib_block = ""
    if cols:
        cells = []
        for ci, col in enumerate(cols):
            for ri in range(7):
                level = col[ri]["level"] if ri < len(col) else 0
                x = grid_x + ci * step
                y = grid_y + ri * step
                cells.append(
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{GRID_LEVEL_COLORS[level]}"/>'
                )
        txt_w = 52
        gap = 14
        legend_w = txt_w + gap + 4 * 16 + cell + gap + txt_w
        legend_x = int((W - legend_w) // 2)
        squares_x = legend_x + txt_w + gap
        legend = (
            f'<text x="{legend_x}" y="{grid_y + grid_h + 24}" class="plain" font-size="13">Less</text>'
            + "".join(
                f'<rect x="{squares_x + i * 16}" y="{grid_y + grid_h + 14}" width="{cell}" height="{cell}" fill="{GRID_LEVEL_COLORS[i]}"/>'
                for i in range(5)
            )
            + f'<text x="{squares_x + 4 * 16 + cell + gap}" y="{grid_y + grid_h + 24}" class="plain" font-size="13">More</text>'
        )
        contrib_block = f'''    <text x="{x0 + 20}" y="{contrib_title_y}" class="cyan" font-size="15">Contribution Graph{_fade_in(7, 0.1)}</text>
    <g>
      <animate attributeName="opacity" from="0" to="1" begin="0.7s" dur="0.4s" fill="freeze"/>
      {''.join(cells)}
    </g>
    {legend}
'''

    svg_content = f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
    <style>
        {_font_css()}
        .bg {{ fill: {COLOR_BG}; }}
        .frame {{ stroke: {COLOR_BORDER}; stroke-width: 3; fill: none; }}
        .frame2 {{ stroke: {COLOR_BORDER}; stroke-width: 1; fill: none; }}
        .plain {{ font-family: 'ModernDOS','Courier New',monospace; font-size: 16px; fill: {COLOR_MAIN}; }}
        .cyan {{ font-family: 'ModernDOS','Courier New',monospace; font-size: 16px; fill: {COLOR_CYAN}; }}
        .seldim {{ font-family: 'ModernDOS','Courier New',monospace; font-size: 15px; fill: {COLOR_SEL_DIM}; }}
        .title {{ font-family: 'ModernDOS','Courier New',monospace; font-size: 24px; fill: {COLOR_TEXT}; letter-spacing: 3px; }}
        .sel {{ font-family: 'ModernDOS','Courier New',monospace; font-size: 16px; fill: {COLOR_SEL_TXT}; }}
        .red {{ font-family: 'ModernDOS','Courier New',monospace; fill: {COLOR_RED}; }}
        a {{ text-decoration: none; }}
        .row {{ cursor: pointer; }}
        .row:hover .rd {{ stroke: {COLOR_CYAN}; }}
        .row:hover .plain {{ fill: {COLOR_CYAN}; }}
        .selbox {{ cursor: pointer; }}
        .rs {{ stroke: {COLOR_BORDER}; stroke-width: 4; fill: #ffffff; }}
        .rs2 {{ stroke: {COLOR_SEL_TXT}; stroke-width: 1.5; fill: none; }}
        .rd {{ stroke: {COLOR_BORDER}; stroke-width: 2; fill: none; }}
    </style>

    <rect width="{W}" height="{H}" class="bg"/>
    <rect x="12" y="12" width="{W - 24}" height="{H - 24}" class="frame"/>
    <rect x="17" y="17" width="{W - 34}" height="{H - 34}" class="frame2"/>

    <text x="{x0}" y="42" class="cyan">GNU GRUB version 2.06</text>
    <text x="{x1}" y="46" text-anchor="end" class="title">kirbx01</text>
    <line x1="{x0}" y1="60" x2="{x1}" y2="60" stroke="{COLOR_BORDER}" stroke-width="2"/>

    <a href="https://github.com/kirbx01" target="_blank" rel="noopener">
    <g class="selbox">
      <rect x="{x0}" y="{sel_item_y}" width="{W - 2 * x0}" height="{sel_box_h}" class="rs"/>
      <rect x="{x0 + 4}" y="{sel_item_y + 4}" width="{W - 2 * x0 - 8}" height="{sel_box_h - 8}" class="rs2"/>
      <text x="{x0 + 20}" y="{sel_title_y}" class="sel" font-size="17">kirbx01 GNU Linux (Active Contributor)</text>
      {" ".join(stat_rows)}
      {lang_block}
    </g>
    </a>

    {contrib_block}

    <line x1="{x0}" y1="{foot_y}" x2="{x1}" y2="{foot_y}" stroke="{COLOR_BORDER}" stroke-width="2"/>
    <text x="{x0}" y="{foot_y + 26}" class="plain">Use Up and Down to select, Enter to run</text>
    <text x="{x0}" y="{foot_y + 54}" class="cyan">The highlighted entry will be executed automatically in 5...4...3...2...1...</text>
</svg>
"""
    return svg_content


if __name__ == "__main__":
    github_data = get_github_data()
    final_svg = generate_svg(github_data)

    with open(OUTPUT_SVG, "w", encoding="utf-8") as f:
        f.write(final_svg)

    print(f"Wrote {OUTPUT_SVG} (fallback={github_data.get('fallback')})")
