import html
import json
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


EQUIPMENT_TERMS = {
    "boots", "boot", "rebounder", "ladder", "cones", "cone", "bands", "band",
    "gloves", "glove", "shin guards", "shin guard", "socks", "sock", "bottle",
    "backpack", "ball", "balls", "equipment", "gear",
}


def clean_meta_text(text: str) -> str:
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    text = text.replace('"', "'").replace("\\", "").replace("&", "and")
    return re.sub(r"[<>]", "", text).strip()


def build_meta_description(title: str, category: str) -> str:
    lower_title = title.lower().strip()
    is_equipment = any(term in lower_title for term in EQUIPMENT_TERMS)

    if is_equipment:
        if lower_title.startswith("best "):
            description = (
                f"Learn how to choose the {lower_title}, including key features, trade-offs, "
                "training uses and practical buying tips."
            )
        else:
            description = (
                f"Learn how to choose {lower_title}, including key features, trade-offs, "
                "training uses and practical buying tips."
            )
    elif "recovery" in category.lower() or "nutrition" in category.lower():
        description = (
            f"Practical guide to {lower_title}, with useful recovery, nutrition, timing and "
            "common-mistake advice for football players."
        )
    elif "strength" in category.lower() or "fitness" in category.lower():
        description = (
            f"Practical guide to {lower_title}, with useful exercises, progressions, common "
            "mistakes and training tips for football players."
        )
    else:
        description = (
            f"Practical guide to {lower_title}, with useful drills, progressions, common "
            "mistakes and training tips for football players."
        )

    description = clean_meta_text(description)
    if len(description) > 155:
        compact = description.replace(" practical", "").replace(" useful", "")
        description = compact if len(compact) <= 155 else description
    if len(description) > 155:
        description = f"Practical guide to {lower_title} with clear football training tips, common mistakes and actionable advice."
    return clean_meta_text(description)


def replace_description_fields(page: str, description: str) -> str:
    escaped_attr = html.escape(description, quote=True)
    escaped_json = json.dumps(description)[1:-1]

    substitutions = [
        (
            re.compile(r'(<meta\s+name="description"\s+content=")[^"]*(")', re.I),
            lambda m: f"{m.group(1)}{escaped_attr}{m.group(2)}",
        ),
        (
            re.compile(r'(<meta\s+property="og:description"\s+content=")[^"]*(")', re.I),
            lambda m: f"{m.group(1)}{escaped_attr}{m.group(2)}",
        ),
        (
            re.compile(r'(<meta\s+name="twitter:description"\s+content=")[^"]*(")', re.I),
            lambda m: f"{m.group(1)}{escaped_attr}{m.group(2)}",
        ),
        (
            re.compile(r'(<p\s+class="article-description">).*?(</p>)', re.I | re.S),
            lambda m: f"{m.group(1)}{html.escape(description)}{m.group(2)}",
        ),
    ]

    updated = page
    for pattern, replacement in substitutions:
        updated = pattern.sub(replacement, updated, count=1)

    updated = re.sub(
        r'("description"\s*:\s*")[^"]*(")',
        lambda m: f"{m.group(1)}{escaped_json}{m.group(2)}",
        updated,
        count=1,
    )
    return updated


def polish_page_seo(post: Path) -> None:
    page = post.read_text(encoding="utf-8")
    old_title = _original_extract_title(page, post)
    new_title = seo_title_case(old_title)
    category = quality.extract_category(page)
    new_description = build_meta_description(new_title, category)

    if old_title and old_title != new_title:
        page = page.replace(old_title, new_title)

    page = replace_description_fields(page, new_description)
    post.write_text(page, encoding="utf-8")

    verification = post.read_text(encoding="utf-8")
    if new_description not in html.unescape(verification):
        raise RuntimeError("SEO metadata update did not persist in the generated article.")

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
