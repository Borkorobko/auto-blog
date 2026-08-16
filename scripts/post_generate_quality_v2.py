import html
import re
from pathlib import Path

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
_original_extract_title = quality.extract_title
_original_main = quality.main


def seo_title_case(text: str) -> str:
    small_words = {
        "a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
        "of", "on", "or", "the", "to", "vs", "with",
    }
    words = text.strip().split()
    polished = []
    for index, word in enumerate(words):
        lower = word.lower()
        if index not in (0, len(words) - 1) and lower in small_words:
            polished.append(lower)
        elif lower == "vs":
            polished.append("vs")
        else:
            polished.append(word[:1].upper() + word[1:].lower())
    return " ".join(polished)


def polished_extract_title(page: str, fallback: Path) -> str:
    return seo_title_case(_original_extract_title(page, fallback))


def quality_issues(body: str, title: str, category: str) -> list[str]:
    normalized = re.sub(
        r"class='([^']+)'",
        lambda match: f'class="{match.group(1)}"',
        body,
        flags=re.I,
    )
    return _original_quality_issues(normalized, title, category)


def first_paragraph_description(body: str, fallback_title: str) -> str:
    match = re.search(r"<p(?:\s[^>]*)?>(.*?)</p>", body, flags=re.I | re.S)
    if match:
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    else:
        text = f"Practical football guide to {fallback_title.lower()} with useful tips for developing players."

    # Keep metadata safe in both HTML attributes and JSON-LD string values.
    text = text.replace('"', "'").replace("\\", "").replace("&", "and")
    text = re.sub(r"[<>]", "", text).strip()

    if len(text) > 155:
        shortened = text[:155].rsplit(" ", 1)[0].rstrip(" ,;:-")
        text = shortened + "."
    elif text and text[-1] not in ".!?":
        text += "."

    return text


def polish_page_seo(post: Path) -> None:
    page = post.read_text(encoding="utf-8")
    old_title = _original_extract_title(page, post)
    new_title = seo_title_case(old_title)
    body = extract_article_body(page)
    new_description = first_paragraph_description(body, new_title)

    description_match = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        page,
        flags=re.I,
    )
    old_description = description_match.group(1) if description_match else ""

    if old_title and old_title != new_title:
        page = page.replace(old_title, new_title)

    if old_description:
        page = page.replace(old_description, new_description)

    post.write_text(page, encoding="utf-8")
    print(f"SEO title polished: {new_title}")
    print(f"Meta description polished: {new_description}")


quality.extract_article_body = extract_article_body
quality.replace_article_body = replace_article_body
quality.extract_title = polished_extract_title
quality.quality_issues = quality_issues


def main() -> None:
    _original_main()
    new_article = quality.find_new_article()
    polish_page_seo(new_article)


if __name__ == "__main__":
    main()
