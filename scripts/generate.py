from pathlib import Path
import random
import re
import html
import os
from openai import OpenAI

SITE = "https://borkorobko.github.io/auto-blog"
POSTS = Path("posts")
PAGES = Path("pages")
POSTS.mkdir(exist_ok=True)

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
  <p class="disclosure">This site may earn a commission from qualifying purchases through some links.</p>
</footer>
"""

FOOTER_POST = """
<footer>
  <p>
    <a href="../pages/privacy.html">Privacy Policy</a> |
    <a href="../pages/cookies.html">Cookie Policy</a> |
    <a href="../pages/terms.html">Terms of Service</a>
  </p>
  <p class="disclosure">This site may earn a commission from qualifying purchases through some links.</p>
</footer>
"""

keywords = [k.strip() for k in Path("keywords.txt").read_text(encoding="utf-8").splitlines() if k.strip()]
keyword = random.choice(keywords)

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

slug = slugify(keyword)
file = POSTS / f"{slug}.html"
safe_keyword = html.escape(keyword)

prompt = f"""
Write a helpful football fitness article for the keyword: "{keyword}".

Requirements:
- Write in English.
- Target amateur and beginner-to-intermediate football players.
- Make it practical, specific and useful.
- Avoid fake statistics.
- Do not mention that AI wrote it.
- Do not use markdown.
- Return only valid HTML sections that go inside an <article>.
- Use h2, h3, p, ul, li.
- Include:
  1. introduction
  2. why it matters
  3. practical advice
  4. mistakes to avoid
  5. simple weekly plan or buying guide depending on topic
  6. FAQ with 3 questions
- Around 900 to 1300 words.
- Add no external links.
"""

response = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt,
)

article_body = response.output_text.strip()

article = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_keyword} | Football Fitness Training</title>
  <meta name="description" content="Practical football guide about {safe_keyword}.">
  <link rel="stylesheet" href="../style.css">
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

posts_index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Football Training Articles</title>
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <header>
    {NAV_POST}
    <h1>Football Training Articles</h1>
  </header>

  <main>
    <ul class="article-list">
"""

for p in sorted(post_files):
    title = html.escape(p.stem.replace("-", " "))
    posts_index += f'      <li><a href="{p.name}">{title}</a></li>\n'

posts_index += f"""    </ul>
  </main>

  {FOOTER_POST}
</body>
</html>
"""

(POSTS / "index.html").write_text(posts_index, encoding="utf-8")

home = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Football Fitness Training</title>
  <meta name="description" content="Football training, recovery, nutrition and equipment guides.">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    {NAV_ROOT}
    <h1>Football Fitness Training</h1>
    <p>Improve your football performance with practical guides about speed, strength, recovery, nutrition and equipment.</p>
  </header>

  <main>
    <h2>Latest articles</h2>
    <ul class="article-list">
"""

for p in post_files[:10]:
    title = html.escape(p.stem.replace("-", " "))
    home += f'      <li><a href="posts/{p.name}">{title}</a></li>\n'

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

for p in sorted(post_files):
    sitemap_urls.append(f"{SITE}/posts/{p.name}")

sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for url in sitemap_urls:
    sitemap += f"  <url><loc>{url}</loc></url>\n"
sitemap += "</urlset>\n"

Path("sitemap.xml").write_text(sitemap, encoding="utf-8")

print(f"Generated AI article: {file}")
