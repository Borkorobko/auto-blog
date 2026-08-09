from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://footballtraininglab.com"
SITE_NAME = "Football Training Lab"
GA_ID = "G-Y6PG5M149E"

POSTS = Path("posts")
IMAGES = Path("images")

DEFAULT_TEST_ARTICLE = "home-speed-workout-for-football-players.html"

POSTS.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def infer_category(topic: str) -> str:
    t = topic.lower()

    if any(word in t for word in [
        "boot", "shin guard", "glove", "equipment", "water bottle",
        "resistance band", "gear", "cone", "ladder"
    ]):
        return "Equipment"

    if any(word in t for word in [
        "recovery", "stretch", "mobility", "protein", "creatine",
        "supplement", "nutrition", "eat", "food", "hydration"
    ]):
        return "Recovery & Nutrition"

    if any(word in t for word in [
        "strength", "gym", "power", "plyometric", "core",
        "leg workout", "stronger"
    ]):
        return "Strength & Power"

    if any(word in t for word in [
        "conditioning", "endurance", "stamina", "fitness",
        "pre season", "pre-season"
    ]):
        return "Fitness"

    return "Speed & Training"


def analytics_html() -> str:
    return f'''<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{GA_ID}');
</script>'''


def nav_html() -> str:
    return '''<header class="site-header">
<div class="container nav-wrap">
<a class="brand" href="../index.html"><span class="brand-mark">FTL</span><span>Football Training Lab</span></a>
<nav class="main-nav" aria-label="Primary navigation">
<a href="../index.html">Home</a><a href="index.html">Articles</a><a href="../pages/about.html">About</a><a href="../pages/contact.html">Contact</a>
</nav>
</div>
</header>'''


def footer_html() -> str:
    return '''<footer class="site-footer">
<div class="container footer-grid">
<div><a class="brand footer-brand" href="../index.html"><span class="brand-mark">FTL</span><span>Football Training Lab</span></a><p>Practical information for developing football players.</p></div>
<div><strong>Explore</strong><a href="index.html">Articles</a><a href="../pages/about.html">About</a><a href="../pages/contact.html">Contact</a></div>
<div><strong>Legal</strong><a href="../pages/privacy.html">Privacy</a><a href="../pages/cookies.html">Cookies</a><a href="../pages/terms.html">Terms</a></div>
</div>
<div class="container footer-bottom"><p>© 2026 Football Training Lab</p><p>This site may earn a commission from qualifying purchases.</p></div>
</footer>'''


def split_title(title: str, max_chars: int = 29) -> list[str]:
    words = title.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        lines.append(" ".join(current))

    return lines[:3]


def category_theme(category: str) -> tuple[str, str]:
    c = category.lower()

    if "recovery" in c or "nutrition" in c:
        return "#0b513e", "#d9ff82"

    if "equipment" in c:
        return "#173f35", "#b8f23d"

    if "strength" in c or "power" in c:
        return "#063c31", "#e2ff9a"

    if "fitness" in c:
        return "#0a4436", "#c9f27b"

    return "#052e25", "#b8f23d"


def create_svg(slug: str, title: str, category: str) -> Path:
    background, accent = category_theme(category)
    lines = split_title(title)

    y = 286
    title_nodes = []

    for line in lines:
        title_nodes.append(
            f'<text x="82" y="{y}" fill="#ffffff" font-size="58" font-weight="800" '
            f'font-family="Arial, Helvetica, sans-serif">{html.escape(line)}</text>'
        )
        y += 72

    badge_width = max(180, len(category) * 14 + 42)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0%" stop-color="{background}"/>
<stop offset="100%" stop-color="#117454"/>
</linearGradient>
<radialGradient id="glow">
<stop offset="0%" stop-color="{accent}" stop-opacity=".40"/>
<stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
</radialGradient>
</defs>
<rect width="1200" height="630" rx="36" fill="url(#bg)"/>
<circle cx="1040" cy="70" r="320" fill="url(#glow)"/>
<circle cx="1040" cy="70" r="215" fill="none" stroke="{accent}" stroke-opacity=".28" stroke-width="2"/>
<circle cx="1040" cy="70" r="150" fill="none" stroke="{accent}" stroke-opacity=".18" stroke-width="2"/>
<rect x="82" y="70" width="94" height="52" rx="14" fill="{accent}"/>
<text x="129" y="105" text-anchor="middle" fill="#052e25" font-size="23" font-weight="900" font-family="Arial, Helvetica, sans-serif">FTL</text>
<text x="198" y="106" fill="#dce9e3" font-size="25" font-weight="700" font-family="Arial, Helvetica, sans-serif">Football Training Lab</text>
<rect x="82" y="166" width="{badge_width}" height="44" rx="22" fill="{accent}"/>
<text x="104" y="195" fill="#052e25" font-size="19" font-weight="800" font-family="Arial, Helvetica, sans-serif">{html.escape(category.upper())}</text>
{''.join(title_nodes)}
<text x="82" y="565" fill="#d5e4dd" font-size="24" font-family="Arial, Helvetica, sans-serif">Practical football performance guide</text>
</svg>
'''

    image_path = IMAGES / f"{slug}.svg"
    image_path.write_text(svg, encoding="utf-8")
    return image_path


def extract_title(page: str, fallback: str) -> str:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.I | re.S)
    if h1:
        title = strip_tags(h1.group(1))
        if title:
            return title

    title_tag = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.I | re.S)
    if title_tag:
        title = strip_tags(title_tag.group(1)).split("|", 1)[0].strip()
        if title:
            return title

    return fallback.replace("-", " ").title()


def extract_meta_description(page: str) -> str:
    match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        page,
        flags=re.I | re.S,
    )
    if match:
        return html.unescape(match.group(1)).strip()
    return ""


def extract_article_html(page: str) -> str:
    match = re.search(r"<article[^>]*>(.*?)</article>", page, flags=re.I | re.S)
    if not match:
        raise RuntimeError("Could not find <article>...</article> in the old page.")
    return match.group(1).strip()


def extract_related_block(article_html: str) -> tuple[str, str]:
    pattern = re.compile(
        r"\s*(<!-- RELATED-START -->.*?<!-- RELATED-END -->)\s*",
        flags=re.I | re.S,
    )
    match = pattern.search(article_html)

    if not match:
        return article_html.strip(), ""

    related = match.group(1).strip()
    body = pattern.sub("\n", article_html, count=1).strip()
    return body, related


def remove_old_headings(body: str, title: str) -> str:
    body = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.I | re.S)

    first_h2 = re.match(r"\s*<h2[^>]*>(.*?)</h2>\s*", body, flags=re.I | re.S)
    if first_h2:
        h2_text = strip_tags(first_h2.group(1)).lower()
        if h2_text == title.strip().lower():
            body = body[first_h2.end():]

    return body.strip()


def wrap_faq_section(body: str) -> str:
    if re.search(r'<section[^>]+class=["\'][^"\']*\bfaq\b', body, flags=re.I):
        return body

    pattern = re.compile(
        r'(<h2[^>]*>\s*Frequently Asked Questions\s*</h2>)(.*?)(?=<h2\b|\Z)',
        flags=re.I | re.S,
    )

    match = pattern.search(body)
    if not match:
        return body

    faq_html = match.group(1) + match.group(2)
    wrapped = f'<section class="faq">\n{faq_html.strip()}\n</section>\n'
    return body[:match.start()] + wrapped + body[match.end():]


def add_unique_h2_ids(body: str) -> tuple[str, list[tuple[str, str]]]:
    used: set[str] = set()
    headings: list[tuple[str, str]] = []

    pattern = re.compile(r"<h2([^>]*)>(.*?)</h2>", flags=re.I | re.S)

    def repl(match: re.Match[str]) -> str:
        attrs = match.group(1)
        inner = match.group(2)
        label = strip_tags(inner)

        existing = re.search(r'\bid=["\']([^"\']+)["\']', attrs, flags=re.I)
        base = existing.group(1) if existing else slugify(label)
        base = base or "section"

        section_id = base
        counter = 2
        while section_id in used:
            section_id = f"{base}-{counter}"
            counter += 1

        used.add(section_id)

        if existing:
            attrs = re.sub(
                r'\bid=["\'][^"\']+["\']',
                f'id="{section_id}"',
                attrs,
                count=1,
                flags=re.I,
            )
        else:
            attrs = f'{attrs} id="{section_id}"'

        if label.lower() not in {"key takeaways", "in this guide", "related football guides"}:
            headings.append((section_id, label))

        return f"<h2{attrs}>{inner}</h2>"

    return pattern.sub(repl, body), headings


def build_key_takeaways(body: str) -> str:
    # Reuses wording already present in the old article; no new claims are invented.
    items = re.findall(r"<li[^>]*>(.*?)</li>", body, flags=re.I | re.S)

    clean_items: list[str] = []
    seen: set[str] = set()

    for item in items:
        text = strip_tags(item)
        if not text:
            continue

        key = text.lower()
        if key in seen:
            continue

        seen.add(key)
        clean_items.append(item.strip())

        if len(clean_items) >= 5:
            break

    if len(clean_items) < 3:
        return ""

    lis = "\n".join(f"<li>{item}</li>" for item in clean_items)

    return f'''<section class="key-takeaways">
<h2>Key takeaways</h2>
<ul>
{lis}
</ul>
</section>'''


def build_toc(headings: list[tuple[str, str]]) -> str:
    useful = [
        (section_id, label)
        for section_id, label in headings
        if label.lower() not in {"conclusion", "frequently asked questions"}
    ]

    if not useful:
        return ""

    links = "\n".join(
        f'<li><a href="#{html.escape(section_id)}">{html.escape(label)}</a></li>'
        for section_id, label in useful[:8]
    )

    return f'''<nav class="table-of-contents" aria-label="Article contents">
<h2>In this guide</h2>
<ul>
{links}
</ul>
</nav>'''


def split_intro(body: str) -> tuple[str, str]:
    first_h2 = re.search(r"<h2\b", body, flags=re.I)
    if not first_h2:
        return "", body

    intro = body[:first_h2.start()].strip()
    rest = body[first_h2.start():].strip()
    return intro, rest


def extract_faq(article_html: str) -> list[dict]:
    section_match = re.search(
        r'<section[^>]*class=["\'][^"\']*\bfaq\b[^"\']*["\'][^>]*>(.*?)</section>',
        article_html,
        flags=re.I | re.S,
    )

    if not section_match:
        return []

    pairs = re.findall(
        r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>",
        section_match.group(1),
        flags=re.I | re.S,
    )

    faq = []

    for question, answer in pairs[:5]:
        clean_question = strip_tags(question)
        clean_answer = strip_tags(answer)

        if clean_question and clean_answer:
            faq.append({
                "@type": "Question",
                "name": clean_question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": clean_answer,
                },
            })

    return faq


def migrate_article(post: Path, dry_run: bool = False) -> str:
    if not post.exists():
        return f"ERROR: {post} does not exist."

    original = post.read_text(encoding="utf-8")

    if 'class="article-shell"' in original and "../article.css" in original:
        return f"SKIPPED: {post.name} is already on the new article template."

    title = extract_title(original, post.stem)
    category = infer_category(title)
    slug = post.stem
    article_url = f"{SITE}/posts/{post.name}"

    description = extract_meta_description(original)
    if not description:
        first_p = re.search(r"<article[^>]*>.*?<p[^>]*>(.*?)</p>", original, flags=re.I | re.S)
        if first_p:
            description = strip_tags(first_p.group(1))[:155].rstrip()

    if not description:
        description = f"Practical football guide about {title} for developing players."

    article_body = extract_article_html(original)
    article_body, related_block = extract_related_block(article_body)
    article_body = remove_old_headings(article_body, title)
    article_body = wrap_faq_section(article_body)
    article_body, headings = add_unique_h2_ids(article_body)

    intro, rest = split_intro(article_body)
    key_takeaways = build_key_takeaways(article_body)
    toc = build_toc(headings)

    rebuilt_body_parts = [part for part in [intro, key_takeaways, toc, rest] if part]
    rebuilt_body = "\n\n".join(rebuilt_body_parts)

    if related_block:
        rebuilt_body += "\n\n" + related_block

    image_path = IMAGES / f"{slug}.svg"
    if not dry_run:
        create_svg(slug, title, category)

    image_url = f"{SITE}/images/{image_path.name}"
    today_utc = datetime.now(timezone.utc).date().isoformat()

    faq_entities = extract_faq(rebuilt_body)

    schema: dict = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "headline": title,
                "description": description,
                "url": article_url,
                "image": image_url,
                "dateModified": today_utc,
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": article_url,
                },
                "publisher": {
                    "@type": "Organization",
                    "name": SITE_NAME,
                    "url": SITE,
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": f"{SITE}/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Articles",
                        "item": f"{SITE}/posts/index.html",
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": title,
                        "item": article_url,
                    },
                ],
            },
        ],
    }

    if faq_entities:
        schema["@graph"].append({
            "@type": "FAQPage",
            "mainEntity": faq_entities,
        })

    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")

    safe_title = html.escape(f"{title} | {SITE_NAME}", quote=True)
    safe_h1 = html.escape(title)
    safe_description = html.escape(description, quote=True)
    safe_url = html.escape(article_url, quote=True)
    safe_image_url = html.escape(image_url, quote=True)
    safe_category = html.escape(category)

    new_page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<meta name="description" content="{safe_description}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{safe_url}">
<link rel="stylesheet" href="../style.css">
<link rel="stylesheet" href="../article.css">
<link rel="icon" href="/favicon.ico" sizes="any">

<meta property="og:locale" content="en_US">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_description}">
<meta property="og:url" content="{safe_url}">
<meta property="og:image" content="{safe_image_url}">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_description}">
<meta name="twitter:image" content="{safe_image_url}">

{analytics_html()}
<script type="application/ld+json">{schema_json}</script>
</head>
<body>
{nav_html()}

<main class="article-page">
<article class="article-shell">
<header class="article-header">
<nav class="breadcrumbs" aria-label="Breadcrumb">
<a href="../index.html">Home</a><span>›</span><a href="index.html">Articles</a><span>›</span><span>{safe_category}</span>
</nav>
<span class="tag">{safe_category}</span>
<h1>{safe_h1}</h1>
<p class="article-description">{safe_description}</p>
<div class="article-meta"><span>Updated {today_utc}</span><span>Practical player guide</span></div>
</header>

<img class="article-hero" src="../images/{html.escape(image_path.name)}" alt="{safe_h1}" width="1200" height="630">

<div class="article-content">
{rebuilt_body}
</div>
</article>
</main>

{footer_html()}
</body>
</html>
'''

    if dry_run:
        return (
            f"DRY RUN OK: {post.name}\n"
            f"  Title: {title}\n"
            f"  Category: {category}\n"
            f"  H2 sections found: {len(headings)}\n"
            f"  FAQ items found: {len(faq_entities)}\n"
            f"  Related block preserved: {'yes' if related_block else 'no'}"
        )

    post.write_text(new_page, encoding="utf-8")

    return (
        f"MIGRATED: {post.name}\n"
        f"  SVG: images/{image_path.name}\n"
        f"  Category: {category}\n"
        f"  H2 sections: {len(headings)}\n"
        f"  FAQ items: {len(faq_entities)}\n"
        f"  Related block preserved: {'yes' if related_block else 'no'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate old Football Training Lab articles to the new article template without rewriting their main content."
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--all",
        action="store_true",
        help="Migrate every old HTML article in posts/ except index.html.",
    )

    group.add_argument(
        "--file",
        help=f"Migrate one specific file in posts/. Default: {DEFAULT_TEST_ARTICLE}",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze the selected article(s) without writing any files.",
    )

    args = parser.parse_args()

    if args.all:
        targets = sorted(
            post for post in POSTS.glob("*.html")
            if post.name != "index.html"
        )
    else:
        filename = args.file or DEFAULT_TEST_ARTICLE
        targets = [POSTS / filename]

    migrated = 0
    skipped = 0
    errors = 0

    print("Football Training Lab — old article migration")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    print(f"Targets: {len(targets)}")
    print()

    for post in targets:
        try:
            result = migrate_article(post, dry_run=args.dry_run)
            print(result)
            print()

            if result.startswith("MIGRATED:"):
                migrated += 1
            elif result.startswith("SKIPPED:"):
                skipped += 1
            elif result.startswith("ERROR:"):
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"ERROR: {post.name}: {exc}")
            print()

    print("Summary")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

    if not args.all and not args.file and not args.dry_run:
        print()
        print("Only the default TEST article was migrated.")
        print("Do not use --all until you have visually checked that test article.")


if __name__ == "__main__":
    main()
