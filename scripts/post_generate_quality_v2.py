import re
import post_generate_quality as quality


def article_content_bounds(page: str) -> tuple[int, int]:
    start_match = re.search(
        r'<div\s+class=["\']article-content["\']\s*>',
        page,
        flags=re.I,
    )
    if not start_match:
        raise RuntimeError("Could not locate article-content opening tag.")

    content_start = start_match.end()
    related_marker = page.find("<!-- RELATED-START -->", content_start)

    if related_marker != -1:
        content_end = page.rfind("</div>", content_start, related_marker)
    else:
        article_end = page.lower().find("</article>", content_start)
        if article_end == -1:
            raise RuntimeError("Could not locate closing article tag.")
        content_end = page.rfind("</div>", content_start, article_end)

    if content_end < content_start:
        raise RuntimeError("Could not locate article-content closing tag.")

    return content_start, content_end


def extract_article_body(page: str) -> str:
    start, end = article_content_bounds(page)
    return page[start:end].strip()


def replace_article_body(page: str, body: str) -> str:
    start, end = article_content_bounds(page)
    return page[:start] + body + page[end:]


_original_quality_issues = quality.quality_issues


def quality_issues(body: str, title: str, category: str) -> list[str]:
    normalized = re.sub(
        r"class='([^']+)'",
        lambda match: f'class="{match.group(1)}"',
        body,
        flags=re.I,
    )
    return _original_quality_issues(normalized, title, category)


quality.extract_article_body = extract_article_body
quality.replace_article_body = replace_article_body
quality.quality_issues = quality_issues


if __name__ == "__main__":
    quality.main()
