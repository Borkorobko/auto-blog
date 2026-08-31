from pathlib import Path
import html
import re

import adsense_quality_cleanup as cleanup

POSTS = Path("posts")
MIN_ARTICLE_WORDS = 650


def article_word_count(page: str) -> int:
    match = re.search(r'<div\s+class="article-content"[^>]*>(.*?)</div>\s*</article>', page, flags=re.I | re.S)
    body = match.group(1) if match else page
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", body))


def mark_noindex(page: str) -> str:
    page = re.sub(
        r'<meta\s+name="robots"\s+content="[^"]*"\s*/?>',
        '<meta name="robots" content="noindex, follow">',
        page,
        count=1,
        flags=re.I,
    )
    if 'name="robots"' not in page.lower():
        page = page.replace("</head>", '<meta name="robots" content="noindex, follow">\n</head>', 1)
    return page


def is_noindex(page: str) -> bool:
    return bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', page, flags=re.I))


def indexable_posts() -> list[Path]:
    retired = set(cleanup.REDIRECTS)
    result = []
    for post in POSTS.glob("*.html"):
        if post.name == "index.html" or post.stem in retired:
            continue
        page = post.read_text(encoding="utf-8", errors="ignore")
        if is_noindex(page):
            continue
        result.append(post)
    return sorted(result, key=lambda p: p.name)


def main() -> None:
    retired = set(cleanup.REDIRECTS)
    audit: list[tuple[str, int, str]] = []
    changed = 0

    for post in sorted(POSTS.glob("*.html")):
        if post.name == "index.html" or post.stem in retired:
            continue
        page = post.read_text(encoding="utf-8", errors="ignore")
        words = article_word_count(page)
        status = "index"
        if words < MIN_ARTICLE_WORDS:
            status = "noindex-thin"
            updated = mark_noindex(page)
            if updated != page:
                post.write_text(updated, encoding="utf-8")
                changed += 1
        elif is_noindex(page):
            status = "noindex-existing"
        audit.append((post.name, words, status))

    # For this cleanup pass, library and sitemap should include only indexable pages.
    cleanup.active_posts = indexable_posts
    cleanup.build_library()
    cleanup.build_sitemap()

    lines = [
        "# AdSense thin-content audit",
        "",
        f"Pages below {MIN_ARTICLE_WORDS} visible article words are temporarily noindexed and excluded from the active article library/sitemap until they are substantially improved.",
        "",
        "| Article | Visible words | Status |",
        "| --- | ---: | --- |",
    ]
    for name, words, status in sorted(audit, key=lambda row: (row[2] != "noindex-thin", row[1], row[0])):
        lines.append(f"| `{name}` | {words} | {status} |")
    lines += [
        "",
        f"Indexable article count after thin-content gate: {len(indexable_posts())}",
        f"Newly noindexed thin pages: {changed}",
    ]
    Path("THIN_CONTENT_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Thin pages newly noindexed: {changed}")
    print(f"Indexable articles after thin-content gate: {len(indexable_posts())}")
    if len(indexable_posts()) < 20:
        raise RuntimeError("Thin-content gate left too few indexable articles; review threshold before merging.")


if __name__ == "__main__":
    main()
