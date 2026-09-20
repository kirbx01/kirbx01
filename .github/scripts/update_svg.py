import os
import base64
import datetime
import requests

GITHUB_USER = os.environ.get("GH_USERNAME", "kirbx01")
TOKEN = os.environ.get("GH_TOKEN")
def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


OUTPUT_SVG = os.path.join(_repo_root(), "profile-htop.svg")
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ModernDOS8x16.ttf")

EXCLUDED_LANGUAGES = {"Jupyter Notebook"}

RECENT_ACTIVITY_DAYS = 180

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
        "total_stars": "0",
        "languages": [
            {"name": "Go", "pct": 32.0, "color": LANG_COLOR_FALLBACK["Go"]},
            {"name": "Python", "pct": 26.0, "color": LANG_COLOR_FALLBACK["Python"]},
            {"name": "C++", "pct": 21.0, "color": LANG_COLOR_FALLBACK["C++"]},
            {"name": "Arduino", "pct": 13.0, "color": LANG_COLOR_FALLBACK["Arduino"]},
            {"name": "Shell", "pct": 8.0, "color": LANG_COLOR_FALLBACK["Shell"]},
        ],
        "fallback": True,
    }


def get_github_data() -> dict:
    if not TOKEN:
        return _fallback_data("GH_TOKEN environment variable is not set")

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
          contributionCalendar { totalContributions }
        }
        pullRequests { totalCount }
        issues { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
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
            return _fallback_data(f"GraphQL errors: {res_json['errors']}")

        user = res_json.get("data", {}).get("user")
        if not user:
            return _fallback_data(f"no user object returned for '{GITHUB_USER}' (bad username or token scope)")

        created_at = datetime.datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.utcnow()
        delta = now - created_at
        years = delta.days // 365
        months = (delta.days % 365) // 30
        age_str = f"{years} yrs, {months} mos" if years > 0 else f"{months} mos"

        cc = user["contributionsCollection"]
        total_commits = cc["totalCommitContributions"]
        total_reviews = cc["totalPullRequestReviewContributions"]
        total_contribs = cc["contributionCalendar"]["totalContributions"]

        total_prs = user["pullRequests"]["totalCount"]
        total_issues = user["issues"]["totalCount"]

        repos = user["repositories"]["nodes"]
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

        lang_bytes: dict[str, int] = {}
        lang_colors: dict[str, str] = {}
        for r in lang_source_repos:
            for edge in r["languages"]["edges"]:
                name = edge["node"]["name"]
                if name in EXCLUDED_LANGUAGES:
                    continue
                lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
                lang_colors[name] = edge["node"]["color"] or LANG_COLOR_FALLBACK.get(name, COLOR_DIM)

        total_bytes = sum(lang_bytes.values()) or 1
        top_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:5]
        languages = [
            {
                "name": name,
                "pct": round(size / total_bytes * 100, 1),
                "color": lang_colors[name],
            }
            for name, size in top_langs
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
            "total_stars": format_large_number(total_stars),
            "languages": languages,
            "fallback": False,
        }

    except Exception as e:
        return _fallback_data(f"exception during fetch: {e}")


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
        ("Code Reviews", "total_reviews"),
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

    drop_titles = [
        ("Stats &amp; Pull Requests (Advanced)", "https://github.com/kirbx01?tab=pull-requests"),
        ("Memory Diagnostic (Tests and Linting)", "https://github.com/kirbx01?tab=repositories"),
        ("System Shutdown (Standby Mode)", "https://panshi.onrender.com"),
    ]
    next_y = sel_item_y + sel_box_h + 12
    item_h = 40
    item_gap = 8
    drop_rows = []
    for i, (t, href) in enumerate(drop_titles):
        y = next_y + i * (item_h + item_gap)
        drop_rows.append(
            f'''    <a href="{href}" target="_blank" rel="noopener">
    <g class="row">
      <rect x="{x0}" y="{y}" width="{W - 2 * x0}" height="{item_h}" class="rd"/>
      <text x="{x0 + 20}" y="{y + 26}" class="plain">{t}</text>
    </g>
    </a>'''
        )

    foot_y = next_y + len(drop_titles) * (item_h + item_gap) - item_gap + 8
    H = foot_y + 84

    demo_tag = ""
    if data.get("fallback"):
        demo_tag = f'<text x="{x1}" y="58" text-anchor="end" class="red" font-size="13">demo data</text>'

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
    {demo_tag}

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

    {"".join(drop_rows)}

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