from pathlib import Path
import random
import re
import html

SITE = "https://borkorobko.github.io/auto-blog"

ROOT = Path(".")
POSTS = ROOT / "posts"
POSTS.mkdir(exist_ok=True)

keywords = [
    k.strip()
    for k in Path("keywords.txt").read_text(encoding="utf-8").splitlines()
    if k.strip()
]

keyword = random.choice(keywords)


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


slug = slugify(keyword)
file = POSTS / f"{slug}.html"
safe_keyword = html.escape(keyword)


def choose_template(keyword):
    k = keyword.lower()

    if any(x in k for x in ["speed", "faster", "agility", "drills"]):
        template_path = Path("templates/speed.html")
    elif any(x in k for x in ["boot", "shin", "glove", "bottle", "cones", "ladder", "bands", "backpack", "equipment", "socks", "rebounder"]):
        template_path = Path("templates/equipment.html")
    elif any(x in k for x in ["strength", "leg workout", "core workout", "gym workout", "plyometric"]):
        template_path = Path("templates/strength.html")
    else:
        template_path = None

    if template_path and template_path.exists():
        return template_path.read_text(encoding="utf-8").replace("{{KEYWORD}}", safe_keyword)

    return f"""
      <h2>Overview</h2>
      <p>This guide explains {safe_keyword} for football players who want practical and useful training advice.</p>

      <h2>Getting started</h2>
      <p>Start simple. Focus on consistency, correct technique and enough recovery between hard sessions.</p>

      <h2>Practical tips</h2>
      <ul>
        <li>Warm up properly before every session.</li>
        <li>Increase training volume gradually.</li>
        <li>Track fatigue and avoid training hard every day.</li>
      </ul>

      <h2>FAQ</h2>
      <h3>Is this suitable for beginners?</h3>
      <p>Yes. Beginners should start slowly and focus on good technique first.</p>
    """


template_body = choose_template(keyword)

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
    <p><a href="../index.html">← Home</a> · <a href="index.html">All articles</a></p>
  </header>

  <main>
    <article>
      <h1>{safe_keyword}</h1>
      {template_body}

      <p class="disclosure">This site may earn a commission from qualifying purchases through some links.</p>
    </article>
  </main>
</body>
</html>
"""

file.write_text(article, encoding="utf-8")

post_files = sorted(
    [p for p in POSTS.glob("*.html") if p.name != "index.html"],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

posts_index = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Football Training Articles</title>
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <h1>Football Training Articles</h1>
  <p><a href="../index.html">← Home</a></p>
  <ul class="article-list">
"""

for p in sorted(post_files):
    title = html.escape(p.stem.replace("-", " "))
    posts_index += f'    <li><a href="{p.name}">{title}</a></li>\n'

posts_index += """  </ul>
</body>
</html>
"""

(POSTS / "index.html").write_text(posts_index, encoding="utf-8")

home = """<!doctype html>
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

home += """    </ul>
    <p><a href="posts/index.html">View all articles</a></p>
    <p class="disclosure">This site may earn a commission from qualifying purchases through some links.</p>
  </main>
</body>
</html>
"""

Path("index.html").write_text(home, encoding="utf-8")

sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
sitemap += f"  <url><loc>{SITE}/</loc></url>\n"
sitemap += f"  <url><loc>{SITE}/posts/index.html</loc></url>\n"

for p in sorted(post_files):
    sitemap += f"  <url><loc>{SITE}/posts/{p.name}</loc></url>\n"

sitemap += "</urlset>\n"

Path("sitemap.xml").write_text(sitemap, encoding="utf-8")

print(f"Generated: {file}")
