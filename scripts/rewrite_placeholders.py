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

    # Many legacy slugs were written like "agility-drills-football".
    # Turn those into natural English: "Football Agility Drills".
    stem_words = fallback.replace(".html", "").split("-")
    if stem_words and stem_words[-1].lower() == "football":
        core = " ".join(stem_words[:-1]).strip()
        if core:
            return f"Football {core.title()}"

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
- IMPORTANT: "football" always means association football / soccer, never American football.
- Use association-football terminology such as goalkeeper, centre-back, full-back, midfielder, winger and striker.
- Never use American-football positions or concepts such as quarterback, receiver, defensive back, linebacker, running back, touchdown or NFL.
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
    plain = strip_tags(body).lower()

    banned_terms = [
        "quarterback",
        "wide receiver",
        "receivers",
        "defensive back",
        "defensive backs",
        "linebacker",
        "linebackers",
        "running back",
        "touchdown",
        "nfl",
    ]
    found = [term for term in banned_terms if term in plain]
    if found:
        raise RuntimeError(
            "American-football terminology detected: " + ", ".join(found)
        )

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


def related_block(current: Path, current_category: str) -> str:
    stop = {
        "a","an","and","for","from","how","in","of","on","the","to","with",
        "football","player","players","best","guide"
    }

    def tokens(path: Path) -> set[str]:
        return {
            x for x in re.findall(r"[a-z0-9]+", path.stem.lower())
            if x not in stop and len(x) > 2
        }

    def display_title(page: str, candidate: Path) -> str:
        title = extract_title(page, candidate.stem).strip()
        if title and title == title.lower():
            title = title.title()
        return title

    current_tokens = tokens(current)
    same_category = []
    fallback = []

    for candidate in POSTS.glob("*.html"):
        if candidate == current or candidate.name == "index.html":
            continue

        try:
            page = candidate.read_text(encoding="utf-8")
        except Exception:
            continue

        if 'class="article-shell"' not in page:
            continue

        candidate_title = extract_title(page, candidate.stem)
        candidate_category = infer_category(candidate_title)
        overlap = len(current_tokens & tokens(candidate))

        item = (overlap, candidate.name, candidate, page)

        if candidate_category == current_category:
            same_category.append(item)
        elif overlap > 0:
            fallback.append(item)

    # Relevance first. Do NOT pad the block with unrelated articles just to reach 4 cards.
    same_category.sort(key=lambda x: (-x[0], x[1]))
    fallback.sort(key=lambda x: (-x[0], x[1]))

    chosen = same_category[:4]

    # Only use another category when there are zero same-category guides,
    # and even then require a direct keyword overlap.
    if not chosen:
        chosen = fallback[:4]

    cards = []
    for _, _, candidate, page in chosen:
        title = display_title(page, candidate)
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


def refresh_related(post: Path, dry_run: bool = False) -> str:
    if not post.exists():
        return f"ERROR: {post.name} does not exist."

    page = post.read_text(encoding="utf-8")

    if 'class="article-shell"' not in page:
        return f"SKIPPED: {post.name} is not a modern article."

    title = extract_title(page, post.stem).strip()
    category = infer_category(title)
    new_block = related_block(post, category)

    pattern = re.compile(
        r"<!-- RELATED-START -->.*?<!-- RELATED-END -->",
        flags=re.I | re.S,
    )
    match = pattern.search(page)

    if not match:
        return f"SKIPPED: {post.name} has no managed related block."

    if dry_run:
        card_count = new_block.count('class="related-card"')
        return (
            f"DRY RUN RELATED OK: {post.name}\n"
            f"  Category: {category}\n"
            f"  Related cards selected: {card_count}"
        )

    updated = page[:match.start()] + new_block + page[match.end():]

    if updated == page:
        return f"RELATED UNCHANGED: {post.name}"

    post.write_text(updated, encoding="utf-8")
    card_count = new_block.count('class="related-card"')
    return (
        f"RELATED UPDATED: {post.name}\n"
        f"  Category: {category}\n"
        f"  Related cards selected: {card_count}"
    )


def rewrite(post: Path, dry_run: bool = False, force: bool = False, related_only: bool = False) -> str:
    if not post.exists():
        return f"ERROR: {post.name} does not exist."

    if related_only:
        return refresh_related(post, dry_run=dry_run)

    original = post.read_text(encoding="utf-8")

    if 'class="article-shell"' in original and not force:
        return f"SKIPPED: {post.name} is already modern."

    if not is_placeholder(original) and not force:
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

    body = ""
    last_error = None
    for attempt in range(1, 4):
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt_for(title, category, notes),
        )
        body = clean_ai_html(response.output_text)
        try:
            validate(body)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            print(f"Validation failed on attempt {attempt}: {exc}")

    if last_error is not None:
        raise RuntimeError(f"Article validation failed after 3 attempts: {last_error}")

    related = related_block(post, category)
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
    parser.add_argument("--force", action="store_true", help="Rewrite even if the selected file is already modern.")
    parser.add_argument("--related-only", action="store_true", help="Refresh only the Related football guides block; do not regenerate article content.")
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
            result = rewrite(post, dry_run=args.dry_run, force=args.force, related_only=args.related_only)
            print(result)
            print()
            if result.startswith("REWRITTEN:") or result.startswith("RELATED UPDATED:"):
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
