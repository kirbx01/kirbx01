import os
import datetime
import requests

GITHUB_USER = "kirbx01"
TOKEN = os.environ.get("GH_TOKEN") 
OUTPUT_SVG = "profile-htop.svg"

COLOR_BG = "#0d1117"
COLOR_TEXT_MAIN = "#c9d1d9"
COLOR_GREEN = "#3fb950"
COLOR_CYAN = "#58a6ff"
COLOR_ORANGE = "#d29922"
COLOR_FUCHSIA = "#ff79c6"
COLOR_DIM = "#8b949e"

def format_large_number(num):
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def get_github_data():
    default_data = {
        "account_age": "2 years, 3 months",
        "total_contributions": "1.2K",
        "total_prs": "45",
        "total_issues": "12",
        "organizations": []
    }

    if not TOKEN:
        return default_data

    headers = {"Authorization": f"Bearer {TOKEN}"}
    query = """
    query($user: String!) {
      user(login: $user) {
        createdAt
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
        pullRequests(first: 1) { totalCount }
        issues(first: 1) { totalCount }
        organizations(first: 3) {
          nodes {
            login
            url
          }
        }
      }
    }
    """
    
    try:
        response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': {'user': GITHUB_USER}}, headers=headers)
        response.raise_for_status()
        res_json = response.json()
        
        if 'errors' in res_json:
            return default_data
            
        data = res_json.get('data', {}).get('user', {})
        if not data:
             return default_data

        created_at = datetime.datetime.strptime(data['createdAt'], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.utcnow()
        delta = now - created_at
        years = delta.days // 365
        months = (delta.days % 365) // 30
        age_str = f"{years} yrs, {months} mos" if years > 0 else f"{months} mos"

        return {
            "account_age": age_str,
            "total_contributions": format_large_number(data['contributionsCollection']['contributionCalendar']['totalContributions']),
            "total_prs": format_large_number(data['pullRequests']['totalCount']),
            "total_issues": format_large_number(data['issues']['totalCount']),
            "organizations": data['organizations']['nodes']
        }
        
    except Exception:
        return default_data

def generate_svg(data):
    svg_content = f"""<svg width="800" height="440" viewBox="0 0 800 440" xmlns="http://www.w3.org/2000/svg">
    <style>
        .bg {{ fill: {COLOR_BG}; rx: 10px; }}
        .text-main {{ font-family: 'Courier New', Courier, monospace; font-size: 13px; fill: {COLOR_TEXT_MAIN}; }}
        .green {{ fill: {COLOR_GREEN}; font-weight: bold; }}
        .cyan {{ fill: {COLOR_CYAN}; }}
        .orange {{ fill: {COLOR_ORANGE}; }}
        .fuchsia {{ fill: {COLOR_FUCHSIA}; font-weight: bold; }}
        .dim {{ fill: {COLOR_DIM}; }}
        a {{ text-decoration: none; }}
        a:hover text {{ text-decoration: underline; fill: {COLOR_CYAN}; }}
        .highlight-box {{ stroke: #30363d; stroke-width: 1; fill: none; rx: 4px; }}
    </style>

    <rect width="800" height="440" class="bg" />

    <text x="20" y="30" class="text-main">1  [<tspan class="green">||||||||||||||||||||||||||||||</tspan>] 100.0%</text>
    <text x="450" y="30" class="text-main">Account Age: <tspan class="fuchsia">{data['account_age']}</tspan></text>

    <text x="20" y="50" class="text-main">2  [<tspan class="orange">||||||||||||||||||||||||</tspan>              ]  72.4%</text>
    <text x="450" y="50" class="text-main">Load average: <tspan class="cyan">1.33 1.15 1.08</tspan></text>

    <text x="20" y="70" class="text-main">Mem[<tspan class="green">||||||||||||||||||||||||||||||||||||||||</tspan>] 64.2G/96.0G</text>
    <text x="450" y="70" class="text-main">Status: <tspan class="green">ONLINE</tspan></text>

    <text x="20" y="90" class="text-main">Swp[<tspan class="orange">||</tspan>                                  ]  1.2G/16.0G</text>

    <text x="20" y="125" class="text-main dim">  ID ACTIVITY     TYPE     COUNT     REPO_SRC S   CPU% MEM%   TIME+     Command</text>
    
    <text x="20" y="145" class="text-main"><tspan class="fuchsia"> 1001</tspan> Total Commits   (Activity) <tspan class="cyan">{data['total_contributions']}</tspan>    github.com S  18.2  0.6   31:42.10  contribution_graph</text>
    <text x="20" y="165" class="text-main"><tspan class="fuchsia"> 1002</tspan> Pull Requests   (Review)   <tspan class="cyan">{data['total_prs']}</tspan>      github.com S   9.1  0.2   15:18.40  open_pr_tracker</text>
    <text x="20" y="185" class="text-main"><tspan class="fuchsia"> 1003</tspan> Open Issues     (Bug/Feat) <tspan class="cyan">{data['total_issues']}</tspan>     github.com S   4.5  0.1    7:09.10  issue_monitor</text>
    <text x="20" y="205" class="text-main"><tspan class="dim"> 2020</tspan> systemd-udevd   (Kernel)   <tspan class="dim">3</tspan>         localhost  S   0.0  0.0    0:01.01  udevd</text>

    <rect x="20" y="235" width="760" height="115" class="highlight-box" />
    <text x="35" y="260" class="text-main">USER: <tspan class="green">{GITHUB_USER}</tspan>  |  OS: <tspan class="cyan">Linux / Nix / Ubuntu</tspan>  |  SHELL: <tspan class="orange">Zsh</tspan></text>
    <text x="35" y="280" class="text-main">STACK: <tspan class="fuchsia">Go, Gin, Python, C++, Espressif IoT</tspan></text>
    <text x="35" y="300" class="text-main">$ ping {GITHUB_USER}</text>
    
    <a href="https://github.com/{GITHUB_USER}" target="_blank">
        <text x="35" y="325" class="text-main">Status: <tspan class="green">ONLINE</tspan>  |  GitHub: <tspan class="cyan">github.com/{GITHUB_USER}</tspan></text>
    </a>

    <text x="20" y="375" class="text-main dim">ORGS:</text>
    """
    
    current_x = 75
    if data['organizations']:
        for org in data['organizations']:
            org_link = f"""<a href="{org['url']}" target="_blank">
                <text x="{current_x}" y="375" class="text-main fuchsia">{org['login']}</text>
            </a>"""
            svg_content += org_link
            current_x += len(org['login']) * 10 + 25
    else:
        svg_content += f"""<text x="{current_x}" y="375" class="text-main dim">None public</text>"""

    svg_content += """
    <text x="20" y="418" class="text-main dim" font-size="11px">F3:search  F4:filter  F5:tree  F6:sort-by  F9:kill  F10:quit</text>
</svg>
"""
    return svg_content

if __name__ == "__main__":
    github_data = get_github_data()
    final_svg = generate_svg(github_data)
    
    with open(OUTPUT_SVG, "w", encoding="utf-8") as f:
        f.write(final_svg)
