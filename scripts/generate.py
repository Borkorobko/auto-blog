from pathlib import Path
import html
import json
import os
import re
from datetime import datetime, timezone
from openai import OpenAI

SITE = "https://footballtraininglab.com"
SITE_NAME = "Football Training Lab"
GA_ID = "G-Y6PG5M149E"

POSTS = Path("posts")
IMAGES = Path("images")
KEYWORDS_FILE = Path("keywords.txt")

POSTS.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

OLD_SITES = [
    "https://borkorobko.github.io/auto-blog",
    "https://auto-blog-983.pages.dev",
]

STOP_WORDS = {
    "a", "an", "and", "for", "from", "how", "in", "of", "on", "the",
    "to", "with", "football", "player", "players",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def infer_category(topic: str) -> str:
    t = topic.lower()
    if any(word in t for word in ["boot", "shin guard", "glove", "equipment", "water bottle", "resistance band", "gear", "cone", "ladder"]):
        return "Equipment"
    if any(word in t for word in ["recovery", "stretch", "mobility", "protein", "creatine", "supplement", "nutrition", "eat", "food", "hydration"]):
        return "Recovery & Nutrition"
    if any(word in t for word in ["strength", "gym", "power", "plyometric", "core", "leg workout", "stronger"]):
        return "Strength & Power"
    if any(word in t for word in ["conditioning", "endurance", "stamina", "fitness", "pre season", "pre-season"]):
        return "Fitness"
    return "Speed & Training"


def approved_product_context(topic: str, category: str) -> str:
    """Return a small, verified product pool for buyer-intent articles.

    The named boot models below were checked against official Nike, adidas and
    PUMA product/category pages on 2026-08-16. The generator must not infer
    current prices, stock or unlisted specifications from this list.
    """
    if category != "Equipment":
        return "No named product recommendations are needed for this topic."

    t = topic.lower()
    is_boot_topic = any(word in t for word in ["boot", "boots", "cleat", "cleats"])
    if not is_boot_topic:
        return (
            "No specific named products are pre-verified for this equipment topic. "
            "Use equipment types, construction, fit, materials and use cases instead of inventing model names."
        )

    return '''Approved named football-boot examples (official brand listings checked 2026-08-16):
- Nike Mercurial Vapor 17 Elite — official Nike listings include Soft-Ground, Firm-Ground and Artificial-Grass versions.
- Nike Mercurial Superfly 11 Elite — official Nike listings include Soft-Ground, Firm-Ground and Artificial-Grass versions.
- Nike Tiempo Maestro Elite — official Nike listings include Soft-Ground and Firm-Ground versions.
- adidas F50 Elite — official adidas listings include Soft Ground, Firm Ground and Artificial Ground versions.
- PUMA FUTURE 8 ULTIMATE MxSG — Mixed/Soft Ground.
- PUMA ULTRA 6 ULTIMATE MxSG — Mixed/Soft Ground.
- PUMA KING ULTIMATE MxSG — Mixed/Soft Ground.

Rules for named recommendations:
- You may name ONLY products from the approved list above.
- Use only models and surface variants that genuinely match the exact topic.
- Never invent or state current prices, discounts, stock, release status, model years, weights or specifications that are not listed above.
- Do not call any model the latest/newest unless the topic explicitly asks for current releases and current data is supplied.
- For price-cap topics such as "under 100", do NOT claim any named model fits the price cap because current price data is intentionally not supplied; use product tiers/types and buying criteria instead.
- Do not claim personal testing. Frame picks as practical recommendations based on the listed surface/use information and explain trade-offs.
- When buying intent is strong, prefer a compact comparison table with 3 to 5 relevant named picks where the verified list genuinely supports them.'''


def clean_ai_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    cleaned = re.sub(r"</?(?:html|head|body|article)[^>]*>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<script.*?</script>", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<style.*?</style>", "", cleaned, flags=re.I | re.S)
    return cleaned.strip()


def meta_description(topic: str) -> str:
    text = f"Practical guide to {topic} for football players, with useful advice, common mistakes, recommendations, and FAQs."
    return text[:155].rstrip()


def topic_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOP_WORDS and len(token) > 2}


def title_from_post(post: Path) -> str:
    return post.stem.replace("-", " ").title()


def related_posts_for(current_post: Path, all_posts: list[Path], limit: int = 4) -> list[Path]:
    current_tokens = topic_tokens(current_post.stem.replace("-", " "))
    ranked = []
    for candidate in all_posts:
        if candidate == current_post:
            continue
        candidate_tokens = topic_tokens(candidate.stem.replace("-", " "))
        overlap = len(current_tokens & candidate_tokens)
        ranked.append((overlap, candidate.name, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def related_links_html(current_post: Path, all_posts: list[Path]) -> str:
    related = related_posts_for(current_post, all_posts)
    if not related:
        return ""
    cards = []
    for post in related:
        cards.append(
            f'<a class="related-card" href="{html.escape(post.name)}">'
            f'<strong>{html.escape(title_from_post(post))}</strong>'
            f'<span>Read guide →</span></a>'
        )
    return (
        '\n<!-- RELATED-START -->\n'
        '<section class="related-articles">\n'
        '  <p class="eyebrow">Continue learning</p>\n'
        '  <h2>Related football guides</h2>\n'
        '  <div class="related-grid">\n'
        f'    {"".join(cards)}\n'
        '  </div>\n'
        '</section>\n'
        '<!-- RELATED-END -->\n'
    )


def update_internal_links(all_posts: list[Path]) -> int:
    pattern = re.compile(r"\s*<!-- RELATED-START -->.*?<!-- RELATED-END -->\s*", flags=re.S)
    updated = 0
    for post in all_posts:
        page = post.read_text(encoding="utf-8")
        clean_page = pattern.sub("\n", page)
        block = related_links_html(post, all_posts)
        if not block or "</article>" not in clean_page:
            continue
        new_page = clean_page.replace("</article>", f"{block}</article>", 1)
        if new_page != page:
            post.write_text(new_page, encoding="utf-8")
            updated += 1
    return updated


def split_title(title: str, max_chars: int = 29) -> list[str]:
    words = title.split()
    lines, current = [], []
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


def extract_faq(article_html: str) -> list[dict]:
    section_match = re.search(r'<section[^>]*class="[^"]*faq[^"]*"[^>]*>(.*?)</section>', article_html, flags=re.I | re.S)
    if not section_match:
        return []
    pairs = re.findall(r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>", section_match.group(1), flags=re.I | re.S)
    faq = []
    for question, answer in pairs[:5]:
        clean_question = re.sub(r"<[^>]+>", "", question).strip()
        clean_answer = re.sub(r"<[^>]+>", "", answer).strip()
        if clean_question and clean_answer:
            faq.append({"@type": "Question", "name": clean_question, "acceptedAnswer": {"@type": "Answer", "text": clean_answer}})
    return faq


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


def migrate_existing_urls() -> int:
    html_files = [Path("index.html")]
    html_files.extend(POSTS.glob("*.html"))
    html_files.extend(Path("pages").glob("*.html"))
    updated = 0
    for page in html_files:
        if not page.exists():
            continue
        original = page.read_text(encoding="utf-8")
        changed = original
        for old_site in OLD_SITES:
            changed = changed.replace(old_site, SITE)
        changed = changed.replace("/auto-blog/favicon.ico", "/favicon.ico")
        if changed != original:
            page.write_text(changed, encoding="utf-8")
            updated += 1
    return updated


def create_posts_index(post_files: list[Path]) -> None:
    cards = []
    for post in sorted(post_files, key=lambda p: p.stat().st_mtime, reverse=True):
        title = html.escape(title_from_post(post))
        cards.append(f'<article class="card"><span class="tag">Guide</span><h3><a href="{html.escape(post.name)}">{title}</a></h3><a href="{html.escape(post.name)}">Read guide →</a></article>')
    url = f"{SITE}/posts/index.html"
    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Football Training Articles | {SITE_NAME}</title>
  <meta name="description" content="Browse practical football training, fitness, recovery, nutrition and equipment guides.">
  <meta name="robots" content="index, follow, max-image-preview:large"><link rel="canonical" href="{url}">
  <link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="../article.css"><link rel="icon" href="/favicon.ico" sizes="any">
  {analytics_html()}
</head>
<body>{nav_html()}<main class="section"><div class="container"><p class="eyebrow">Training library</p><h1 class="library-title">Football training articles</h1><div class="article-grid">{''.join(cards)}</div></div></main>{footer_html()}</body>
</html>'''
    (POSTS / "index.html").write_text(page, encoding="utf-8")


def write_sitemap_and_robots(post_files: list[Path]) -> None:
    urls = [f"{SITE}/", f"{SITE}/posts/index.html", f"{SITE}/pages/about.html", f"{SITE}/pages/contact.html", f"{SITE}/pages/privacy.html", f"{SITE}/pages/cookies.html", f"{SITE}/pages/terms.html"]
    urls.extend(f"{SITE}/posts/{post.name}" for post in sorted(post_files))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls)
    sitemap += "</urlset>\n"
    Path("sitemap.xml").write_text(sitemap, encoding="utf-8")
    Path("robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")


if not KEYWORDS_FILE.exists():
    raise RuntimeError("keywords.txt was not found in the repository root.")

keywords = [line.strip() for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
if not keywords:
    raise RuntimeError("No keywords left in keywords.txt.")

skipped_existing = []
keyword = None
for candidate in keywords:
    candidate_slug = slugify(candidate)
    if candidate_slug and (POSTS / f"{candidate_slug}.html").exists():
        skipped_existing.append(candidate)
        continue
    keyword = candidate
    break

if keyword is None:
    KEYWORDS_FILE.write_text("", encoding="utf-8")
    raise RuntimeError("All keywords in keywords.txt already have published articles. Add new keywords before running the workflow again.")

remaining_keywords = [item for item in keywords if item not in skipped_existing and item != keyword]
slug = slugify(keyword)
if not slug:
    raise RuntimeError(f"Could not create a valid slug from keyword: {keyword}")

category = infer_category(keyword)
article_file = POSTS / f"{slug}.html"
article_url = f"{SITE}/posts/{slug}.html"
image_path = create_svg(slug, keyword, category)
image_url = f"{SITE}/images/{image_path.name}"
description = meta_description(keyword)
today_utc = datetime.now(timezone.utc).date().isoformat()
product_context = approved_product_context(keyword, category)

prompt = f'''
Write a detailed, genuinely useful English article for Football Training Lab.
Exact topic: "{keyword}"
Category: {category}
Audience: amateur and developing football players, beginner-to-intermediate level.
Length: approximately 1200 to 1700 words.
Accuracy: do not invent studies, statistics, prices, certifications or endorsements; do not claim equipment or exercises prevent injuries; do not diagnose or treat medical conditions; tell readers to stop or reduce intensity when they feel sharp pain; never claim personal testing; do not mention artificial intelligence.

Product recommendation context:
{product_context}

For Equipment articles:
- If the topic has strong buying intent (for example Best, Top, For, With, Under, or a specific playing condition), answer the buying intent near the beginning instead of writing only a generic educational guide.
- When named products are allowed by the approved context, use 3 to 5 relevant models in a useful comparison table and explain who each suits plus its main trade-off.
- If no named products are approved for the topic, use clear product types or construction categories instead of inventing brand/model names.
- Never recommend a specific retailer and never invent affiliate links.

Return only valid HTML inside the article content. Do not include html, head, body, article, script, style or h1 tags. Do not use Markdown.
Use this structure:
1. Short direct introduction.
2. section class="key-takeaways" with h2 "Key takeaways" and 4 to 6 useful li points.
3. nav class="table-of-contents" with h2 "In this guide" and anchor links to major sections.
4. Several detailed h2 sections; each major h2 must have a unique lowercase id using hyphens.
5. Include practical steps, sets, repetitions, rest periods, weekly structure, or buying criteria when relevant.
6. Include one useful table when it genuinely helps; for strong Equipment buying intent, prefer a comparison table.
7. div class="tip-box" with one strong practical tip.
8. div class="warning-box" with a common mistake or safety point.
9. section class="faq" with h2 "Frequently asked questions" and exactly 3 h3 questions, each immediately followed by one p answer.
10. Concise conclusion.
Allowed elements: section, nav, div, h2, h3, p, ul, ol, li, strong, em, a, table, thead, tbody, tr, th, td.
'''

response = client.responses.create(model="gpt-4.1-mini", input=prompt)
article_body = clean_ai_html(response.output_text)
faq_entities = extract_faq(article_body)

schema = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "Article", "headline": keyword, "description": description, "url": article_url, "image": image_url, "datePublished": today_utc, "dateModified": today_utc, "mainEntityOfPage": {"@type": "WebPage", "@id": article_url}, "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Articles", "item": f"{SITE}/posts/index.html"},
            {"@type": "ListItem", "position": 3, "name": keyword, "item": article_url},
        ]},
    ],
}
if faq_entities:
    schema["@graph"].append({"@type": "FAQPage", "mainEntity": faq_entities})

schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
safe_title = html.escape(f"{keyword} | {SITE_NAME}", quote=True)
safe_keyword = html.escape(keyword)
safe_description = html.escape(description, quote=True)
safe_url = html.escape(article_url, quote=True)
safe_image_url = html.escape(image_url, quote=True)
safe_category = html.escape(category)

article_page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title><meta name="description" content="{safe_description}"><meta name="robots" content="index, follow, max-image-preview:large"><link rel="canonical" href="{safe_url}">
  <link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="../article.css"><link rel="icon" href="/favicon.ico" sizes="any">
  <meta property="og:locale" content="en_US"><meta property="og:type" content="article"><meta property="og:site_name" content="{SITE_NAME}"><meta property="og:title" content="{safe_title}"><meta property="og:description" content="{safe_description}"><meta property="og:url" content="{safe_url}"><meta property="og:image" content="{safe_image_url}">
  <meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{safe_title}"><meta name="twitter:description" content="{safe_description}"><meta name="twitter:image" content="{safe_image_url}">
  {analytics_html()}<script type="application/ld+json">{schema_json}</script>
</head>
<body>
  {nav_html()}
  <main class="article-page"><article class="article-shell">
    <header class="article-header">
      <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a><span>›</span><a href="index.html">Articles</a><span>›</span><span>{safe_category}</span></nav>
      <span class="tag">{safe_category}</span><h1>{safe_keyword}</h1><p class="article-description">{safe_description}</p>
      <div class="article-meta"><span>Published {today_utc}</span><span>Practical player guide</span></div>
    </header>
    <img class="article-hero" src="../images/{html.escape(image_path.name)}" alt="{safe_keyword}" width="1200" height="630">
    <div class="article-content">{article_body}</div>
  </article></main>
  {footer_html()}
</body>
</html>'''

article_file.write_text(article_page, encoding="utf-8")
post_files = sorted([p for p in POSTS.glob("*.html") if p.name != "index.html"], key=lambda p: p.stat().st_mtime, reverse=True)
updated_internal_links = update_internal_links(post_files)
migrated_pages = migrate_existing_urls()
post_files = sorted([p for p in POSTS.glob("*.html") if p.name != "index.html"], key=lambda p: p.stat().st_mtime, reverse=True)
create_posts_index(post_files)
write_sitemap_and_robots(post_files)
KEYWORDS_FILE.write_text("\n".join(remaining_keywords) + ("\n" if remaining_keywords else ""), encoding="utf-8")

print(f"Generated article: {article_file}")
print(f"Generated SVG image: {image_path}")
print(f"Published title: {keyword}")
print(f"Category: {category}")
print(f"Keywords remaining: {len(remaining_keywords)}")
print(f"Existing articles updated with related links: {updated_internal_links}")
print(f"Old site URLs migrated: {migrated_pages}")
print("Homepage preserved.")
print("Articles index, sitemap and robots.txt rebuilt.")
