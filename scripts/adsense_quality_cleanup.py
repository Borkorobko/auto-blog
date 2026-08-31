from __future__ import annotations

from pathlib import Path
import csv
import html
import re

SITE = "https://footballtraininglab.com"
POSTS = Path("posts")
CONTENT_PLAN = Path("content_plan.csv")

# GitHub Pages cannot emit real server-side 301 redirects. These source pages are
# therefore converted into noindex + canonical + immediate redirect stubs, while
# being removed from the article library and sitemap.
REDIRECTS = {
    "complete-football-speed-training-guide": "speed-training-for-football",
    "speed-training-drills-for-football": "speed-training-for-football",
    "speed-training-exercises-for-footballers": "speed-training-for-football",
    "best-speed-exercises-for-football-players": "speed-training-for-football",
    "how-to-get-faster-in-football": "speed-training-for-football",
    "how-to-improve-speed-in-football": "speed-training-for-football",
    "how-to-improve-sprint-speed-for-football": "speed-training-for-football",
    "football-sprint-training-explained": "speed-training-for-football",
    "core-workout-for-football-players": "core-workout-football",
    "football-conditioning-workout-plan": "football-conditioning-workout",
    "plyometrics-football": "plyometric-workout-for-football",
    "explosive-training-football": "plyometric-workout-for-football",
    "building-endurance-for-football-players": "football-endurance-training",
    "how-to-increase-stamina-for-football": "football-endurance-training",
    "football-stamina-training": "football-endurance-training",
    "football-agility-drills-for-better-footwork": "agility-drills-football",
    "football-warm-up-routine": "football-warm-up-before-a-match",
    "football-warm-up-routines-to-prevent-fatigue": "football-warm-up-before-a-match",
    "football-recovery-workout": "football-recovery-routine-after-a-match",
    "how-to-get-stronger-for-football": "strength-training-for-football",
    "best-boots-for-speed": "best-football-boots-for-speed",
    "foootball-news": "index",
}

CATEGORY_ORDER = [
    "Speed & Training",
    "Fitness",
    "Strength & Power",
    "Recovery & Nutrition",
    "Equipment",
]


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").title()


def target_url(target: str) -> str:
    if target == "index":
        return f"{SITE}/posts/index.html"
    return f"{SITE}/posts/{target}.html"


def target_href(target: str) -> str:
    if target == "index":
        return "index.html"
    return f"{target}.html"


def make_redirect_stub(source: str, target: str) -> str:
    url = target_url(target)
    label = "Football Training Lab article library" if target == "index" else title_from_slug(target)
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Guide Moved | Football Training Lab</title>
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{html.escape(url, quote=True)}">
  <meta http-equiv="refresh" content="0; url={html.escape(url, quote=True)}">
  <script>window.location.replace({url!r});</script>
</head>
<body>
  <main>
    <h1>This guide has been consolidated</h1>
    <p>To keep Football Training Lab focused and avoid overlapping articles, this page has been merged into a stronger guide.</p>
    <p><a href="{html.escape(target_href(target), quote=True)}">Continue to {html.escape(label)}</a></p>
  </main>
</body>
</html>
'''


def extract_text(pattern: str, page: str, fallback: str) -> str:
    match = re.search(pattern, page, flags=re.I | re.S)
    if not match:
        return fallback
    value = re.sub(r"<[^>]+>", " ", match.group(1))
    return html.unescape(re.sub(r"\s+", " ", value)).strip() or fallback


def active_posts() -> list[Path]:
    retired = set(REDIRECTS)
    return sorted(
        [p for p in POSTS.glob("*.html") if p.name != "index.html" and p.stem not in retired],
        key=lambda p: p.name,
    )


def replace_internal_links() -> int:
    updated = 0
    for post in active_posts():
        page = post.read_text(encoding="utf-8")
        changed = page
        for source, target in REDIRECTS.items():
            source_name = f"{source}.html"
            changed = changed.replace(source_name, target_href(target))
        if changed != page:
            post.write_text(changed, encoding="utf-8")
            updated += 1
    return updated


def fix_strength_article() -> bool:
    path = POSTS / "strength-training-for-football.html"
    if not path.exists():
        return False
    page = path.read_text(encoding="utf-8")
    changed = page
    changed = changed.replace(
        "Football Strength Training For | Football Training Lab",
        "Strength Training for Football Players | Football Training Lab",
    )
    changed = changed.replace(
        "Practical guide to Football Strength Training For for football players, including drills, progression, training structure and common mistakes.",
        "Practical strength training guide for football players, including exercises, progression, weekly structure and common mistakes.",
    )
    changed = changed.replace('"headline":"Football Strength Training For"', '"headline":"Strength Training for Football Players"')
    changed = changed.replace('"name":"Football Strength Training For"', '"name":"Strength Training for Football Players"')
    changed = changed.replace("<h1>Football Strength Training For</h1>", "<h1>Strength Training for Football Players</h1>")
    changed = changed.replace('alt="Football Strength Training For"', 'alt="Strength Training for Football Players"')
    changed = changed.replace(
        "Football Strength Training For Amateur and Beginner-to-Intermediate Players",
        "Strength Training for Amateur and Developing Football Players",
    )
    if changed != page:
        path.write_text(changed, encoding="utf-8")
        return True
    return False


def build_library() -> None:
    groups: dict[str, list[tuple[str, str, str]]] = {category: [] for category in CATEGORY_ORDER}
    extras: list[tuple[str, str, str, str]] = []

    for post in active_posts():
        page = post.read_text(encoding="utf-8", errors="ignore")
        title = extract_text(r"<h1[^>]*>(.*?)</h1>", page, title_from_slug(post.stem))
        category = extract_text(r'<span\s+class="tag"[^>]*>(.*?)</span>', page, "Football Training")
        description = extract_text(r'<p\s+class="article-description"[^>]*>(.*?)</p>', page, "Practical football training guide.")
        item = (post.name, title, description)
        if category in groups:
            groups[category].append(item)
        else:
            extras.append((category, *item))

    def cards(items: list[tuple[str, str, str]]) -> str:
        out = []
        for filename, title, description in sorted(items, key=lambda item: item[1].lower()):
            out.append(
                f'<article class="card"><span class="tag">Guide</span>'
                f'<h3><a href="{html.escape(filename)}">{html.escape(title)}</a></h3>'
                f'<p>{html.escape(description)}</p>'
                f'<a href="{html.escape(filename)}">Read guide →</a></article>'
            )
        return "".join(out)

    sections = []
    for category in CATEGORY_ORDER:
        if not groups[category]:
            continue
        sections.append(
            f'<section class="library-section"><p class="eyebrow">{html.escape(category)}</p>'
            f'<h2>{html.escape(category)}</h2><div class="article-grid">{cards(groups[category])}</div></section>'
        )

    if extras:
        extra_items = [(filename, title, description) for _, filename, title, description in extras]
        sections.append(
            f'<section class="library-section"><p class="eyebrow">More guides</p><h2>More football guides</h2>'
            f'<div class="article-grid">{cards(extra_items)}</div></section>'
        )

    page = f'''<!doctype html>
<html lang="en">
<head>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4653487457062463" crossorigin="anonymous"></script>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Football Training Articles | Football Training Lab</title>
  <meta name="description" content="Browse focused football training, fitness, strength, recovery, nutrition and equipment guides for developing players.">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{SITE}/posts/index.html">
  <link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="../article.css"><link rel="icon" href="/favicon.ico" sizes="any">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y6PG5M149E"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-Y6PG5M149E');</script>
</head>
<body>
<header class="site-header"><div class="container nav-wrap"><a class="brand" href="../index.html"><span class="brand-mark">FTL</span><span>Football Training Lab</span></a><nav class="main-nav" aria-label="Primary navigation"><a href="../index.html">Home</a><a href="index.html">Articles</a><a href="../pages/about.html">About</a><a href="../pages/contact.html">Contact</a></nav></div></header>
<main class="section"><div class="container"><p class="eyebrow">Training library</p><h1 class="library-title">Football training articles</h1><p>Focused guides with distinct training goals, practical steps and clear use cases. Overlapping articles are consolidated into stronger resources.</p>{''.join(sections)}</div></main>
<footer class="site-footer"><div class="container footer-grid"><div><a class="brand footer-brand" href="../index.html"><span class="brand-mark">FTL</span><span>Football Training Lab</span></a><p>Practical information for developing football players.</p></div><div><strong>Explore</strong><a href="index.html">Articles</a><a href="../pages/about.html">About</a><a href="../pages/editorial.html">Editorial Policy</a><a href="../pages/contact.html">Contact</a></div><div><strong>Legal</strong><a href="../pages/privacy.html">Privacy</a><a href="../pages/cookies.html">Cookies</a><a href="../pages/terms.html">Terms</a></div></div><div class="container footer-bottom"><p>© 2026 Football Training Lab</p><p>This site may earn a commission from qualifying purchases.</p></div></footer>
</body>
</html>'''
    (POSTS / "index.html").write_text(page, encoding="utf-8")


def build_sitemap() -> None:
    urls = [
        f"{SITE}/",
        f"{SITE}/posts/index.html",
        f"{SITE}/pages/about.html",
        f"{SITE}/pages/contact.html",
        f"{SITE}/pages/editorial.html",
        f"{SITE}/pages/privacy.html",
        f"{SITE}/pages/cookies.html",
        f"{SITE}/pages/terms.html",
    ]
    urls.extend(f"{SITE}/posts/{post.name}" for post in active_posts())
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls)
    xml += "</urlset>\n"
    Path("sitemap.xml").write_text(xml, encoding="utf-8")


def update_homepage() -> bool:
    path = Path("index.html")
    page = path.read_text(encoding="utf-8")
    changed = page.replace("complete-football-speed-training-guide.html", "speed-training-for-football.html")
    changed = changed.replace("Complete football speed training guide", "Football speed training guide")
    if changed != page:
        path.write_text(changed, encoding="utf-8")
        return True
    return False


def update_content_plan() -> int:
    if not CONTENT_PLAN.exists():
        return 0
    with CONTENT_PLAN.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    changed = 0
    for row in rows:
        slug = (row.get("Slug") or "").strip()
        if slug in REDIRECTS and row.get("Status") != "Merged":
            row["Status"] = "Merged"
            changed += 1
    if fieldnames:
        with CONTENT_PLAN.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return changed


def write_redirect_manifest() -> None:
    lines = ["# Consolidated article map", "", "These pages were consolidated during the AdSense low-value-content cleanup.", ""]
    for source, target in REDIRECTS.items():
        lines.append(f"- `{source}` → `{target}`")
    lines += [
        "",
        "GitHub Pages does not provide server-side 301 rules for this deployment, so source pages use `noindex`, a canonical target, and an immediate browser redirect. They are excluded from the article library and sitemap.",
        "",
        "Scheduled new-article generation is intentionally paused until the consolidated library has been reviewed and Search Console/AdSense signals improve.",
    ]
    Path("QUALITY_CLEANUP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for source, target in REDIRECTS.items():
        source_path = POSTS / f"{source}.html"
        if source_path.exists():
            source_path.write_text(make_redirect_stub(source, target), encoding="utf-8")

    fixed_strength = fix_strength_article()
    internal_updates = replace_internal_links()
    build_library()
    build_sitemap()
    homepage_updated = update_homepage()
    plan_updates = update_content_plan()
    write_redirect_manifest()

    print(f"Redirect stubs written: {len(REDIRECTS)}")
    print(f"Strength article fixed: {fixed_strength}")
    print(f"Active articles with internal links updated: {internal_updates}")
    print(f"Homepage updated: {homepage_updated}")
    print(f"Content-plan rows marked Merged: {plan_updates}")
    print(f"Active indexable article count: {len(active_posts())}")
    print("Article library and sitemap rebuilt without consolidated URLs.")


if __name__ == "__main__":
    main()
