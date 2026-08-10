from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path

from openai import OpenAI

from migrate_old_articles import (
    POSTS,
    SITE,
    extract_title,
    infer_category,
    migrate_article,
    strip_tags,
)

DEFAULT_TEST_ARTICLE = "agility-drills-football.html"


def clean_ai_html(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"</?(?:html|head|body|article)[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<h1[^>]*>.*?</h1>", "", text, flags=re.I | re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    return text.strip()


def is_placeholder(page: str) -> bool:
    return (
        'class="article-shell"' not in page
        and re.search(r"<article[^>]*>.*?</article>", page, flags=re.I | re.S) is None
    )


def legacy_text(page: str) -> str:
    body = re.search(r"<body[^>]*>(.*?)</body>", page, flags=re.I | re.S)
    text = strip_tags(body.group(1) if body else page)
    return text[:1600].strip()


def normal_title(page: str, fallback: str) -> str:
    title = extract_title(page, fallback).strip()
    if title and title == title.lower():
        title = title.title()
    return title


def meta_description(title: str, category: str) -> str:
    if category == "Equipment":
        text = f"Practical guide to {title}, covering fit, materials, durability, maintenance and value for football players."
    elif category == "Recovery & Nutrition":
        text = f"Practical guide to {title} for football players, with useful recovery, nutrition, timing and common-mistake advice."
    else:
        text = f"Practical guide to {title} for football players, including drills, progression, training structure and common mistakes."
    return text[:155].rstrip()


def prompt_for(title: str, category: str, notes: str) -> str:
    return f'''
Write a detailed and genuinely useful football article for this exact topic:

"{title}"

Category: {category}

Audience:
- Amateur football players
- Beginner-to-intermediate players
- Players who want practical advice they can apply safely

Useful text from the old placeholder page:
{notes or "(No useful legacy text beyond the topic.)"}

Requirements:
- Write in clear English.
- Aim for about 1100 to 1500 words.
- Answer the search intent immediately.
- Be specific to the exact topic.
- Keep useful legacy ideas when relevant, but expand them substantially.
- Do not invent studies, statistics, prices, professional endorsements, product tests or personal experience.
- Do not claim that exercises or equipment guarantee injury prevention.
- Do not mention artificial intelligence or that the page was rewritten.
- Return only valid HTML for inside an article.
- Do not include html, head, body, article, h1, script or style tags.
- Use only h2, h3, p, ul, ol, li, strong and table elements.
- Include at least 5 useful H2 sections.
- Include exactly one H2 called "Frequently Asked Questions".
- Under it include exactly 3 H3 questions, each immediately followed by a P answer.
- Finish with exactly one H2 called "Conclusion".

For training, speed, agility, strength or conditioning topics:
- Give realistic drills, sets, reps, distances, rest periods or weekly frequency where appropriate.
- Explain beginner progression and common technique mistakes.
- Say to stop or reduce training for sharp or persistent pain and seek appropriate professional advice when needed.

For recovery or nutrition topics:
- Focus on practical timing, habits and choices without medical diagnosis or exaggerated claims.

For equipment topics:
- Explain fit, materials, durability, suitable users, maintenance and value.
- Do not pretend anything was personally tested.
- Do not recommend a specific retailer.
'''.strip()


def validate(body: str) -> None:
    h2 = [strip_tags(x).lower() for x in re.findall(r"<h2[^>]*>(.*?)</h2>", body, flags=re.I | re.S)]
    if len(h2) < 5:
        raise RuntimeError(f"Generated article has only {len(h2)} H2 sections.")
    if h2.count("frequently asked questions") != 1:
        raise RuntimeError("Expected exactly one Frequently Asked Questions H2.")
    if h2.count("conclusion") != 1:
        raise RuntimeError("Expected exactly one Conclusion H2.")

    faq = re.search(
        r"<h2[^>]*>\s*Frequently Asked Questions\s*</h2>(.*?)(?=<h2\b|\Z)",
        body,
        flags=re.I | re.S,
    )
    pairs = [] if not faq else re.findall(
        r"<h3[^>]*>.*?</h3>\s*<p[^>]*>.*?</p>",
        faq.group(1),
        flags=re.I | re.S,
    )
    if len(pairs) != 3:
        raise RuntimeError(f"Expected 3 FAQ items, found {len(pairs)}.")


def related_block(current: Path) -> str:
    stop = {"a","an","and","for","from","how","in","of","on","the","to","with","football","player","players"}

    def tokens(path: Path) -> set[str]:
        return {
            x for x in re.findall(r"[a-z0-9]+", path.stem.lower())
            if x not in stop and len(x) > 2
        }

    current_tokens = tokens(current)
    ranked = []

    for candidate in POSTS.glob("*.html"):
        if candidate == current or candidate.name == "index.html":
            continue
        try:
            page = candidate.read_text(encoding="utf-8")
        except Exception:
            continue
        if 'class="article-shell"' not in page:
            continue
        ranked.append((len(current_tokens & tokens(candidate)), candidate.name, candidate, page))

    ranked.sort(key=lambda x: (-x[0], x[1]))
    cards = []

    for _, _, candidate, page in ranked[:4]:
        title = extract_title(page, candidate.stem)
        cards.append(
            f'<a class="related-card" href="{html.escape(candidate.name)}">'
            f'<strong>{html.escape(title)}</strong><span>Read guide →</span></a>'
        )

    if not cards:
        return ""

    return (
        '<!-- RELATED-START -->\n'
        '<section class="related-articles">\n'
        '<p class="eyebrow">Continue learning</p>\n'
        '<h2>Related football guides</h2>\n'
        '<div class="related-grid">\n'
        + "\n".join(cards)
        + '\n</div>\n</section>\n'
        '<!-- RELATED-END -->'
    )


def rewrite(post: Path, dry_run: bool = False) -> str:
    if not post.exists():
        return f"ERROR: {post.name} does not exist."

    original = post.read_text(encoding="utf-8")

    if 'class="article-shell"' in original:
        return f"SKIPPED: {post.name} is already modern."

    if not is_placeholder(original):
        return f"SKIPPED: {post.name} is not a placeholder."

    title = normal_title(original, post.stem)
    category = infer_category(title)
    notes = legacy_text(original)
    description = meta_description(title, category)

    if dry_run:
        return (
            f"DRY RUN OK: {post.name}\n"
            f"  Title: {title}\n"
            f"  Category: {category}\n"
            f"  Legacy text characters: {len(notes)}\n"
            f"  URL preserved: {SITE}/posts/{post.name}"
        )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt_for(title, category, notes),
    )
    body = clean_ai_html(response.output_text)
    validate(body)

    related = related_block(post)
    intermediate = f'''<!doctype html>
<html lang="en">
<head>
<title>{html.escape(title)} | Football Training Lab</title>
<meta name="description" content="{html.escape(description, quote=True)}">
</head>
<body>
<article>
<h1>{html.escape(title)}</h1>
{body}
{related}
</article>
</body>
</html>
'''

    try:
        post.write_text(intermediate, encoding="utf-8")
        migration_result = migrate_article(post, dry_run=False)
    except Exception:
        post.write_text(original, encoding="utf-8")
        raise

    return (
        f"REWRITTEN: {post.name}\n"
        f"  Title: {title}\n"
        f"  Category: {category}\n"
        f"  URL preserved: {SITE}/posts/{post.name}\n"
        f"{migration_result}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true")
    group.add_argument("--file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.all:
        targets = []
        for post in sorted(POSTS.glob("*.html")):
            if post.name == "index.html":
                continue
            try:
                page = post.read_text(encoding="utf-8")
            except Exception:
                continue
            if is_placeholder(page):
                targets.append(post)
        if args.limit > 0:
            targets = targets[:args.limit]
    else:
        targets = [POSTS / (args.file or DEFAULT_TEST_ARTICLE)]

    rewritten = skipped = errors = 0

    print("Football Training Lab — placeholder rewrite")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    print(f"Targets: {len(targets)}")
    print()

    for post in targets:
        try:
            result = rewrite(post, dry_run=args.dry_run)
            print(result)
            print()
            if result.startswith("REWRITTEN:"):
                rewritten += 1
            elif result.startswith("SKIPPED:"):
                skipped += 1
            elif result.startswith("ERROR:"):
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"ERROR: {post.name}: {exc}")
            print()

    print("Summary")
    print(f"  Rewritten: {rewritten}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
