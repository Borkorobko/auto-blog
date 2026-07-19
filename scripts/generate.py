from pathlib import Path
import re
import html
import os
import json
import csv
from datetime import datetime, timezone
from openai import OpenAI

SITE = "https://borkorobko.github.io/auto-blog"
SITE_NAME = "Football Fitness Training"

POSTS = Path("posts")
POSTS.mkdir(exist_ok=True)

GA = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-Y6PG5M149E"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-Y6PG5M149E');
</script>
"""

FAVICON = """
<link rel="icon" href="/auto-blog/favicon.ico" sizes="any">
"""

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

NAV_ROOT = """
<nav>
  <a href="index.html">Home</a> |
  <a href="posts/index.html">Articles</a> |
  <a href="pages/about.html">About</a> |
  <a href="pages/contact.html">Contact</a>
</nav>
"""

NAV_POST = """
<nav>
  <a href="../index.html">Home</a> |
  <a href="index.html">Articles</a> |
  <a href="../pages/about.html">About</a> |
  <a href="../pages/contact.html">Contact</a>
</nav>
"""

FOOTER_ROOT = """
<footer>
  <p>
    <a href="pages/privacy.html">Privacy Policy</a> |
    <a href="pages/cookies.html">Cookie Policy</a> |
    <a href="pages/terms.html">Terms of Service</a>
  </p>
  <p class="disclosure">
    This site may earn a commission from qualifying purchases through some links.
  </p>
</footer>
"""

FOOTER_POST = """
<footer>
  <p>
    <a href="../pages/privacy.html">Privacy Policy</a> |
    <a href="../pages/cookies.html">Cookie Policy</a> |
    <a href="../pages/terms.html">Terms of Service</a>
  </p>
  <p class="disclosure">
    This site may earn a commission from qualifying purchases through some links.
  </p>
</footer>
"""


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def clean_ai_html(text):
    cleaned = text.strip()

    if cleaned.startswith("```html"):
        cleaned = cleaned[len("```html"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    cleaned = re.sub(r"</?article[^>]*>", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def article_meta_description(topic):
    description = (
        f"Learn about {topic} with practical football training advice, "
        f"common mistakes, useful tips and answers for amateur players."
    )
    return description[:155].rstrip()



STOP_WORDS = {
    "a", "an", "and", "for", "from", "how", "in", "of", "on", "the",
    "to", "with", "football", "player", "players"
}


def topic_tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 2
    }


def related_posts_for(current_post, all_posts, limit=5):
    current_tokens = topic_tokens(current_post.stem.replace("-", " "))
    ranked = []

    for candidate in all_posts:
        if candidate == current_post:
            continue

        candidate_tokens = topic_tokens(candidate.stem.replace("-", " "))
        overlap = len(current_tokens & candidate_tokens)

        # A small fallback score keeps the links useful even when there is
        # no exact word overlap.
        score = overlap * 10

        if current_post.stat().st_mtime <= candidate.stat().st_mtime:
            score += 1

        ranked.append((score, candidate.name, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def related_links_html(current_post, all_posts):
    related = related_posts_for(current_post, all_posts)

    if not related:
        return ""

    items = []
    for post in related:
        title = html.escape(post.stem.replace("-", " "))
        items.append(f'        <li><a href="{post.name}">{title}</a></li>')

    return (
        "\n      <!-- RELATED-START -->\n"
        "      <section class=\"related-articles\">\n"
        "        <h2>Related football guides</h2>\n"
        "        <ul>\n"
        + "\n".join(items)
        + "\n        </ul>\n"
        "      </section>\n"
        "      <!-- RELATED-END -->\n"
    )


def update_internal_links(all_posts):
    pattern = re.compile(
        r"\n?\s*<!-- RELATED-START -->.*?<!-- RELATED-END -->\s*\n?",
        flags=re.DOTALL,
    )

    updated = 0

    for post in all_posts:
        page = post.read_text(encoding="utf-8")
        page_without_old_block = pattern.sub("\n", page)
        related_block = related_links_html(post, all_posts)

        if not related_block or "</article>" not in page_without_old_block:
            continue

        new_page = page_without_old_block.replace(
            "</article>",
            f"{related_block}    </article>",
            1,
        )

        if new_page != page:
            post.write_text(new_page, encoding="utf-8")
            updated += 1

    return updated

CONTENT_PLAN_FILE = Path("content_plan.csv")
CONTENT_PLAN_FIELDS = [
    "Title",
    "Category",
    "Cluster",
    "Intent",
    "Priority",
    "Status",
    "PublishedDate",
    "Slug",
]


def normalize_status(value):
    return (value or "").strip().lower()


def priority_value(row):
    try:
        return int((row.get("Priority") or "999").strip())
    except ValueError:
        return 999


def load_content_plan():
    if not CONTENT_PLAN_FILE.exists():
        raise RuntimeError(
            "content_plan.csv was not found. Add it to the repository root."
        )

    with CONTENT_PLAN_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise RuntimeError("content_plan.csv is empty.")

    missing_fields = [
        field for field in CONTENT_PLAN_FIELDS
        if field not in (reader.fieldnames or [])
    ]

    if missing_fields:
        raise RuntimeError(
            "content_plan.csv is missing columns: "
            + ", ".join(missing_fields)
        )

    return rows


def save_content_plan(rows):
    temporary_file = CONTENT_PLAN_FILE.with_suffix(".csv.tmp")

    with temporary_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTENT_PLAN_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    temporary_file.replace(CONTENT_PLAN_FILE)


content_plan = load_content_plan()
today_utc = datetime.now(timezone.utc).date().isoformat()

# Mark rows as published when the matching article already exists.
# This also makes migration from keywords.txt safe.
existing_rows_updated = 0

for row in content_plan:
    title = (row.get("Title") or "").strip()
    row_slug = slugify(title)

    if not title or not row_slug:
        continue

    article_file = POSTS / f"{row_slug}.html"

    if article_file.exists() and normalize_status(row.get("Status")) != "published":
        row["Status"] = "Published"
        row["PublishedDate"] = row.get("PublishedDate") or today_utc
        row["Slug"] = row_slug
        existing_rows_updated += 1

pending_rows = [
    (index, row)
    for index, row in enumerate(content_plan)
    if normalize_status(row.get("Status")) in {"", "pending"}
    and (row.get("Title") or "").strip()
]

pending_rows.sort(
    key=lambda item: (
        priority_value(item[1]),
        item[0],
    )
)

if not pending_rows:
    if existing_rows_updated:
        save_content_plan(content_plan)

    print("No pending articles remain in content_plan.csv.")
    print(f"Existing articles synchronized: {existing_rows_updated}")
    raise SystemExit(0)

selected_index, selected_row = pending_rows[0]

keyword = selected_row["Title"].strip()
category = (selected_row.get("Category") or "Football").strip()
cluster = (selected_row.get("Cluster") or category).strip()
intent = (selected_row.get("Intent") or "Informational").strip()

slug = slugify(keyword)

if not slug:
    raise RuntimeError(f"Could not create a valid slug from keyword: {keyword}")

file = POSTS / f"{slug}.html"

safe_keyword = html.escape(keyword)
article_url = f"{SITE}/posts/{slug}.html"
article_title = f"{keyword} | {SITE_NAME}"
article_description = article_meta_description(keyword)

safe_article_title = html.escape(article_title, quote=True)
safe_article_description = html.escape(article_description, quote=True)
safe_article_url = html.escape(article_url, quote=True)

prompt = f"""
Write a detailed and genuinely useful football article for the keyword:
"{keyword}"

Content plan:
- Category: {category}
- Topic cluster: {cluster}
- Search intent: {intent}

Audience:
- Amateur football players
- Beginner-to-intermediate players
- Players who want practical advice they can apply safely

Requirements:
- Write in clear English.
- Aim for approximately 1000 to 1400 words.
- Be specific to the exact keyword, category, topic cluster and search intent.
- Satisfy the stated search intent early in the article.
- Do not write a generic article that could fit every football topic.
- Do not invent studies, statistics, prices or professional endorsements.
- Do not claim that a product prevents injuries.
- Do not mention artificial intelligence.
- Do not use Markdown.
- Return only valid HTML content for inside an <article>.
- Do not include html, head, body, article, script or style tags.
- You may use only h2, h3, p, ul, ol, li, strong and table elements.

Use this structure:
1. A useful introduction that directly answers the search intent
2. Why the topic matters for football players
3. Detailed practical advice
4. A step-by-step plan, weekly routine or buying guide depending on the topic
5. Common mistakes and how to avoid them
6. Beginner and intermediate recommendations
7. Three frequently asked questions with useful answers
8. A brief conclusion

For training topics:
- Include realistic sets, repetitions, rest periods or weekly frequency
  only where appropriate.
- Explain when players should reduce intensity or stop because of pain.

For equipment topics:
- Explain fit, durability, materials, suitable users, maintenance and value.
- Do not pretend to have personally tested products.
- Do not recommend a specific retailer.
"""

response = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt,
)

article_body = clean_ai_html(response.output_text)

article_schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": keyword,
    "description": article_description,
    "url": article_url,
    "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": article_url,
    },
    "publisher": {
        "@type": "Organization",
        "name": SITE_NAME,
        "url": SITE,
    },
}

article_schema_json = json.dumps(
    article_schema,
    ensure_ascii=False,
).replace("</", "<\\/")

article = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>{safe_article_title}</title>
  <meta name="description" content="{safe_article_description}">
  <meta name="robots" content="index, follow, max-image-preview:large">

  <link rel="canonical" href="{safe_article_url}">
  <link rel="stylesheet" href="../style.css">

  <meta property="og:locale" content="en_US">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{safe_article_title}">
  <meta property="og:description" content="{safe_article_description}">
  <meta property="og:url" content="{safe_article_url}">

  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{safe_article_title}">
  <meta name="twitter:description" content="{safe_article_description}">

  {FAVICON}
  {GA}

  <script type="application/ld+json">
  {article_schema_json}
  </script>
</head>
<body>
  <header>
    {NAV_POST}
  </header>

  <main>
    <article>
      <h1>{safe_keyword}</h1>
      {article_body}
    </article>
  </main>

  {FOOTER_POST}
</body>
</html>
"""

file.write_text(article, encoding="utf-8")

post_files = sorted(
    [p for p in POSTS.glob("*.html") if p.name != "index.html"],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

updated_internal_links = update_internal_links(post_files)

# Re-sort after updating the article files.
post_files = sorted(
    [p for p in POSTS.glob("*.html") if p.name != "index.html"],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

posts_index_url = f"{SITE}/posts/index.html"
posts_index_title = f"Football Training Articles | {SITE_NAME}"
posts_index_description = (
    "Browse practical football training, fitness, recovery, nutrition "
    "and equipment guides for amateur players."
)

posts_index_schema = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Football Training Articles",
    "description": posts_index_description,
    "url": posts_index_url,
    "isPartOf": {
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": SITE,
    },
}

posts_index_schema_json = json.dumps(
    posts_index_schema,
    ensure_ascii=False,
).replace("</", "<\\/")

posts_index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>{html.escape(posts_index_title, quote=True)}</title>
  <meta name="description" content="{html.escape(posts_index_description, quote=True)}">
  <meta name="robots" content="index, follow, max-image-preview:large">

  <link rel="canonical" href="{posts_index_url}">
  <link rel="stylesheet" href="../style.css">

  <meta property="og:locale" content="en_US">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{html.escape(posts_index_title, quote=True)}">
  <meta property="og:description" content="{html.escape(posts_index_description, quote=True)}">
  <meta property="og:url" content="{posts_index_url}">

  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{html.escape(posts_index_title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(posts_index_description, quote=True)}">

  {FAVICON}
  {GA}

  <script type="application/ld+json">
  {posts_index_schema_json}
  </script>
</head>
<body>
  <header>
    {NAV_POST}
    <h1>Football Training Articles</h1>
  </header>

  <main>
    <ul class="article-list">
"""

for post in sorted(post_files):
    title = html.escape(post.stem.replace("-", " "))
    posts_index += f'      <li><a href="{post.name}">{title}</a></li>\n'

posts_index += f"""    </ul>
  </main>

  {FOOTER_POST}
</body>
</html>
"""

(POSTS / "index.html").write_text(posts_index, encoding="utf-8")

home_url = f"{SITE}/"
home_title = "Football Fitness Training | Practical Player Guides"
home_description = (
    "Practical football guides about speed, strength, conditioning, "
    "recovery, nutrition and equipment for amateur players."
)

home_schema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": SITE_NAME,
    "url": home_url,
    "description": home_description,
}

home_schema_json = json.dumps(
    home_schema,
    ensure_ascii=False,
).replace("</", "<\\/")

home = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>{html.escape(home_title, quote=True)}</title>
  <meta name="description" content="{html.escape(home_description, quote=True)}">
  <meta name="robots" content="index, follow, max-image-preview:large">

  <link rel="canonical" href="{home_url}">
  <link rel="stylesheet" href="style.css">

  <meta property="og:locale" content="en_US">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{html.escape(home_title, quote=True)}">
  <meta property="og:description" content="{html.escape(home_description, quote=True)}">
  <meta property="og:url" content="{home_url}">

  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{html.escape(home_title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(home_description, quote=True)}">

  {FAVICON}
  {GA}

  <script type="application/ld+json">
  {home_schema_json}
  </script>
</head>
<body>
  <header>
    {NAV_ROOT}
    <h1>Football Fitness Training</h1>
    <p>
      Improve your football performance with practical guides about speed,
      strength, recovery, nutrition and equipment.
    </p>
  </header>

  <main>
    <h2>Latest articles</h2>
    <ul class="article-list">
"""

for post in post_files[:10]:
    title = html.escape(post.stem.replace("-", " "))
    home += f'      <li><a href="posts/{post.name}">{title}</a></li>\n'

home += f"""    </ul>
    <p><a href="posts/index.html">View all articles</a></p>
  </main>

  {FOOTER_ROOT}
</body>
</html>
"""

Path("index.html").write_text(home, encoding="utf-8")

sitemap_urls = [
    f"{SITE}/",
    f"{SITE}/posts/index.html",
    f"{SITE}/pages/about.html",
    f"{SITE}/pages/contact.html",
    f"{SITE}/pages/privacy.html",
    f"{SITE}/pages/cookies.html",
    f"{SITE}/pages/terms.html",
]

for post in sorted(post_files):
    sitemap_urls.append(f"{SITE}/posts/{post.name}")

sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

for url in sitemap_urls:
    sitemap += f"  <url><loc>{html.escape(url)}</loc></url>\n"

sitemap += "</urlset>\n"

Path("sitemap.xml").write_text(sitemap, encoding="utf-8")

# Mark the selected article as published only after the article and all
# generated site files were written successfully.
selected_row["Status"] = "Published"
selected_row["PublishedDate"] = today_utc
selected_row["Slug"] = slug
content_plan[selected_index] = selected_row
save_content_plan(content_plan)

pending_remaining = sum(
    1
    for row in content_plan
    if normalize_status(row.get("Status")) in {"", "pending"}
)

print(f"Generated AI article: {file}")
print(f"Published content-plan title: {keyword}")
print(f"Category: {category}")
print(f"Cluster: {cluster}")
print(f"Intent: {intent}")
print(f"Priority: {selected_row.get('Priority', '')}")
print(f"Existing articles synchronized: {existing_rows_updated}")
print(f"Pending articles remaining: {pending_remaining}")
print(f"Articles updated with internal links: {updated_internal_links}")
