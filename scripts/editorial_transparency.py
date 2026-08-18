from pathlib import Path
import json
import re

SITE = "https://footballtraininglab.com"
AUTHOR_NAME = "Football Training Lab Editorial Team"
AUTHOR_URL = f"{SITE}/pages/editorial.html"
EDITORIAL_LINK = '<a href="/pages/editorial.html">Editorial Policy</a>'
BYLINE_HTML = (
    '\n      <div class="article-byline">'
    '<span>By <a href="../pages/editorial.html">Football Training Lab Editorial Team</a></span>'
    '<span>AI-assisted draft with automated quality checks</span>'
    '</div>'
)


def add_byline(text: str) -> tuple[str, bool]:
    if 'class="article-byline"' in text:
        return text, False
    pattern = re.compile(r'(<div class="article-meta">.*?</div>)', flags=re.I | re.S)
    updated, count = pattern.subn(lambda m: m.group(1) + BYLINE_HTML, text, count=1)
    return updated, bool(count)


def add_author_schema(text: str) -> tuple[str, bool]:
    pattern = re.compile(
        r'(<script\s+type="application/ld\+json"[^>]*>)(.*?)(</script>)',
        flags=re.I | re.S,
    )
    changed = False

    def repl(match: re.Match) -> str:
        nonlocal changed
        raw = match.group(2).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)

        nodes = data.get("@graph") if isinstance(data, dict) else None
        if not isinstance(nodes, list):
            return match.group(0)

        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Article":
                desired = {
                    "@type": "Organization",
                    "name": AUTHOR_NAME,
                    "url": AUTHOR_URL,
                }
                if node.get("author") != desired:
                    node["author"] = desired
                    changed = True
                break

        if not changed:
            return match.group(0)

        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        return match.group(1) + encoded + match.group(3)

    updated = pattern.sub(repl, text, count=1)
    return updated, changed


def add_footer_link(text: str) -> tuple[str, bool]:
    footer_pattern = re.compile(r'(<footer class="site-footer">.*?</footer>)', flags=re.I | re.S)
    match = footer_pattern.search(text)
    if not match:
        return text, False

    footer = match.group(1)
    if EDITORIAL_LINK in footer:
        return text, False

    about_pattern = re.compile(r'(<a[^>]+href="[^"]*about\.html"[^>]*>About</a>)', flags=re.I)
    new_footer, count = about_pattern.subn(lambda m: m.group(1) + EDITORIAL_LINK, footer, count=1)
    if not count:
        return text, False

    updated = text[:match.start(1)] + new_footer + text[match.end(1):]
    return updated, True


def update_html_file(path: Path, is_article: bool) -> tuple[bool, bool, bool]:
    text = path.read_text(encoding="utf-8")
    original = text
    byline_changed = False
    schema_changed = False

    if is_article:
        text, byline_changed = add_byline(text)
        text, schema_changed = add_author_schema(text)

    text, footer_changed = add_footer_link(text)

    if text != original:
        path.write_text(text, encoding="utf-8")

    return byline_changed, schema_changed, footer_changed


def ensure_editorial_in_sitemap() -> bool:
    path = Path("sitemap.xml")
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    editorial_url = f"{SITE}/pages/editorial.html"
    if editorial_url in text:
        return False
    marker = "</urlset>"
    if marker not in text:
        return False
    entry = f"  <url><loc>{editorial_url}</loc></url>\n"
    path.write_text(text.replace(marker, entry + marker, 1), encoding="utf-8")
    return True


def main() -> None:
    article_files = sorted(p for p in Path("posts").glob("*.html") if p.name != "index.html")
    other_files = [Path("index.html"), Path("posts/index.html")]
    other_files.extend(sorted(Path("pages").glob("*.html")))

    bylines = schemas = footers = 0

    for path in article_files:
        if not path.exists():
            continue
        b, s, f = update_html_file(path, is_article=True)
        bylines += int(b)
        schemas += int(s)
        footers += int(f)

    for path in other_files:
        if not path.exists():
            continue
        _, _, f = update_html_file(path, is_article=False)
        footers += int(f)

    sitemap_changed = ensure_editorial_in_sitemap()

    print(f"Editorial bylines added: {bylines}")
    print(f"Article author schemas updated: {schemas}")
    print(f"Footer editorial links added: {footers}")
    print(f"Editorial page added to sitemap: {sitemap_changed}")


if __name__ == "__main__":
    main()
