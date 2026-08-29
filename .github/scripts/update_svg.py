import os
import datetime
import requests

GITHUB_USER = os.environ.get("GH_USERNAME", "kirbx01")
TOKEN = os.environ.get("GH_TOKEN")
OUTPUT_SVG = "profile-htop.svg"

EXCLUDED_LANGUAGES = {"Jupyter Notebook"}

RECENT_ACTIVITY_DAYS = 180

COLOR_BG = "#0d1117"
COLOR_TEXT_MAIN = "#c9d1d9"
COLOR_GREEN = "#3fb950"
COLOR_CYAN = "#58a6ff"
COLOR_ORANGE = "#d29922"
COLOR_FUCHSIA = "#ff79c6"
COLOR_DIM = "#8b949e"
COLOR_TRACK = "#21262d"
COLOR_TRACK_STROKE = "#30363d"
COLOR_RED = "#f85149"

LANG_COLOR_FALLBACK = {
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "C++": "#f34b7d",
    "C": "#555555",
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
    print(f"::warning:: profile-htop: using DEMO data — {reason}")
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
        return _fallback_data(f"exception during fetch — {e}")


def _lang_bars(data: dict, start_y: int) -> str:
    bar_x = 140
    bar_w = 260
    bar_h = 12
    rows = []
    for i, lang in enumerate(data["languages"]):
        y = start_y + i * 22
        target_w = round(bar_w * lang["pct"] / 100, 1)
        delay = 0.15 * i
        rows.append(f"""
    <text x="20" y="{y + bar_h - 2}" class="text-main">{lang['name'][:10]:<10}</text>
    <rect x="{bar_x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{COLOR_TRACK}" stroke="{COLOR_TRACK_STROKE}" rx="2"/>
    <rect x="{bar_x}" y="{y}" width="0" height="{bar_h}" fill="{lang['color']}" rx="2">
        <animate attributeName="width" from="0" to="{target_w}" begin="{delay}s" dur="1.1s" fill="freeze" calcMode="spline" keySplines="0.16 1 0.3 1" keyTimes="0;1" values="0;{target_w}"/>
    </rect>
    <text x="{bar_x + bar_w + 12}" y="{y + bar_h - 2}" class="text-main dim">{lang['pct']:.1f}%</text>""")
    return "".join(rows)


def _fade_in(index: int, base_delay: float = 0.08) -> str:
    delay = base_delay * index
    return f'<animate attributeName="opacity" from="0" to="1" begin="{delay}s" dur="0.35s" fill="freeze"/>'


def _safe_text_len_attrs(plain_text: str, max_width_px: float, per_char: float = 8.6) -> str:
    natural = len(plain_text) * per_char
    if natural > max_width_px:
        return f' textLength="{max_width_px:.0f}" lengthAdjust="spacingAndGlyphs"'
    return ""


def generate_svg(data: dict) -> str:
    demo_tag = ""
    if data.get("fallback"):
        demo_tag = f'<text x="780" y="20" text-anchor="end" class="text-main" fill="{COLOR_RED}" font-size="11px">[DEMO DATA — GH_TOKEN missing/invalid]</text>'

    lang_section_title_y = 235
    lang_bars_start_y = 250
    n_langs = len(data["languages"])
    lang_section_bottom = lang_bars_start_y + n_langs * 22

    box_y = lang_section_bottom + 15
    box_h = 115
    footer_y = box_y + box_h + 25

    total_h = footer_y + 20

    ping_text = f"$ ping {GITHUB_USER}"
    ping_len_px = len(ping_text) * 8.6

    box_inner_available_px = 760 - (35 - 20) - 15

    user_line_plain = f"USER: {GITHUB_USER}  |  OS: Linux / Arch / BSD  |  SHELL: Zsh"
    stack_line_plain = "STACK: Go, Gin, Python, C++, Espressif, Arduino"
    status_line_plain = f"Status: ONLINE  |  GitHub: github.com/{GITHUB_USER}"

    svg_content = f"""<svg width="800" height="{total_h}" viewBox="0 0 800 {total_h}" xmlns="http://www.w3.org/2000/svg">
    <style>
        .bg {{ fill: {COLOR_BG}; }}
        .text-main {{ font-family: 'Courier New', Courier, monospace; font-size: 13px; fill: {COLOR_TEXT_MAIN}; white-space: pre; }}
        .green {{ fill: {COLOR_GREEN}; font-weight: bold; }}
        .red {{ fill: {COLOR_RED}; font-weight: bold;}}
        .cyan {{ fill: {COLOR_CYAN}; }}
        .orange {{ fill: {COLOR_ORANGE}; }}
        .fuchsia {{ fill: {COLOR_FUCHSIA}; font-weight: bold; }}
        .dim {{ fill: {COLOR_DIM}; }}
        a {{ text-decoration: none; }}
        a:hover text {{ fill: {COLOR_CYAN}; }}
        .highlight-box {{ stroke: {COLOR_TRACK_STROKE}; stroke-width: 1; fill: none; rx: 4px; }}
    </style>

    <rect width="800" height="{total_h}" class="bg" rx="10"/>
    {demo_tag}

    <text x="20" y="30" class="text-main">1  [<tspan class="green">||||||||||||||||||||||||||||||</tspan>] 100.0%
        <animate attributeName="opacity" values="1;0.55;1" dur="2.4s" repeatCount="indefinite"/>
    </text>
    <text x="450" y="30" class="text-main">Account Age: <tspan class="fuchsia">{data['account_age']}</tspan></text>

    <text x="20" y="50" class="text-main">2  [<tspan class="orange">||||||||||||||||||||||||</tspan>              ]  72.4%
        <animate attributeName="opacity" values="1;0.5;1" dur="1.8s" repeatCount="indefinite"/>
    </text>
    <text x="450" y="50" class="text-main">Total Stars: <tspan class="cyan">{data['total_stars']}</tspan></text>

    <text x="20" y="70" class="text-main">Mem[<tspan class="green">||||||||||</tspan>] 64.2G/96.0G</text>
    <text x="450" y="70" class="text-main">Status: <tspan class="red">COOKED<animate attributeName="opacity" values="1;1;0.15;1" keyTimes="0;0.6;0.8;1" dur="1.6s" repeatCount="indefinite"/></tspan></text>

    <text x="20" y="90" class="text-main">Swp[<tspan class="orange">||</tspan>                                  ]  1.2G/16.0G</text>
    <text x="450" y="90" class="text-main">Contributions(yr): <tspan class="cyan">{data['total_contributions']}</tspan></text>

    <text x="20" y="125" class="text-main dim">  ID ACTIVITY     TYPE     COUNT     REPO_SRC S   CPU% MEM%   TIME+     Command</text>

    <text x="20" y="145" opacity="0" class="text-main">{_fade_in(0)}<tspan class="fuchsia"> 1001</tspan> Total Commits   (Activity) <tspan class="cyan">{data['total_commits']}</tspan>    github.com S  18.2  0.6   31:42.10  contribution_graph</text>
    <text x="20" y="165" opacity="0" class="text-main">{_fade_in(1)}<tspan class="fuchsia"> 1002</tspan> Pull Requests   (Review)   <tspan class="cyan">{data['total_prs']}</tspan>      github.com S   9.1  0.2   15:18.40  open_pr_tracker</text>
    <text x="20" y="185" opacity="0" class="text-main">{_fade_in(2)}<tspan class="fuchsia"> 1003</tspan> Open Issues     (Bug/Feat) <tspan class="cyan">{data['total_issues']}</tspan>     github.com S   4.5  0.1    7:09.10  issue_monitor</text>
    <text x="20" y="205" opacity="0" class="text-main">{_fade_in(3)}<tspan class="fuchsia"> 1004</tspan> Code Reviews    (Review)   <tspan class="cyan">{data['total_reviews']}</tspan>      github.com S   6.3  0.1    5:02.77  pr_review_bot</text>

    <text x="20" y="{lang_section_title_y}" class="text-main dim">TOP LANGUAGES (by bytes across owned repos):</text>
    {_lang_bars(data, lang_bars_start_y)}

    <rect x="20" y="{box_y}" width="760" height="{box_h}" class="highlight-box" />
    <text x="35" y="{box_y + 25}" class="text-main"{_safe_text_len_attrs(user_line_plain, box_inner_available_px)}>USER: <tspan class="green">{GITHUB_USER}</tspan>  |  OS: <tspan class="cyan"> Nix / Arch / FreeBSD/ DOS</tspan>  |  SHELL: <tspan class="orange">Zsh</tspan></text>
    <text x="35" y="{box_y + 45}" class="text-main"{_safe_text_len_attrs(stack_line_plain, box_inner_available_px)}>STACK: <tspan class="fuchsia">Go, Gin, Python, C++, Espressif, Arduino</tspan></text>

    <clipPath id="ping-clip">
        <rect x="35" y="{box_y + 55}" height="16" width="0">
            <animate attributeName="width" from="0" to="{ping_len_px}" begin="0.6s" dur="1.4s" fill="freeze" calcMode="linear"/>
        </rect>
    </clipPath>
    <text x="35" y="{box_y + 65}" class="text-main" clip-path="url(#ping-clip)">{ping_text}</text>
    <rect x="{35 + ping_len_px}" y="{box_y + 53}" width="7" height="15" fill="{COLOR_GREEN}">
        <animate attributeName="x" from="35" to="{35 + ping_len_px}" begin="0.6s" dur="1.4s" fill="freeze" calcMode="linear"/>
        <animate attributeName="opacity" values="1;0;1" dur="0.9s" begin="2s" repeatCount="indefinite"/>
    </rect>

    <a href="https://github.com/{GITHUB_USER}" target="_blank">
        <text x="35" y="{box_y + 90}" opacity="0" class="text-main"{_safe_text_len_attrs(status_line_plain, box_inner_available_px)}>
            <animate attributeName="opacity" from="0" to="1" begin="2.1s" dur="0.4s" fill="freeze"/>
            Status: <tspan class="green">ONLINE</tspan>  |  GitHub: <tspan class="cyan">github.com/{GITHUB_USER}</tspan>
        </text>
    </a>

    <text x="20" y="{footer_y}" class="text-main dim" font-size="11px">F3:search  F4:filter  F5:tree  F6:sort-by  F9:kill  F10:quit</text>
</svg>
"""
    return svg_content


if __name__ == "__main__":
    github_data = get_github_data()
    final_svg = generate_svg(github_data)

    with open(OUTPUT_SVG, "w", encoding="utf-8") as f:
        f.write(final_svg)

    print(f"Wrote {OUTPUT_SVG} (fallback={github_data.get('fallback')})")
