from pathlib import Path
import random
import re
import html
import os
import json
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


keywords = [
    line.strip()
    for line in Path("keywords.txt").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

if not keywords:
    raise RuntimeError("keywords.txt does not contain any usable keywords.")

keyword = random.choice(keywords)
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

Audience:
- Amateur football players
- Beginner-to-intermediate players
- Players who want practical advice they can apply safely

Requirements:
- Write in clear English.
- Aim for approximately 1000 to 1400 words.
- Be specific to the exact keyword.
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

print(f"Generated AI article: {file}")
