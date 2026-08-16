from pathlib import Path
import html
import re
import subprocess

POSTS = Path("posts")
MAX_SOURCE_LINKS = 3
LINKS_PER_NEW_ARTICLE = 5

STOP_WORDS = {
    "a", "an", "and", "best", "for", "from", "guide", "how", "in", "of",
    "on", "the", "to", "with", "football", "player", "players", "training",
    "workout", "workouts",
}


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def page_title(text: str, fallback: Path) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
    if match:
        title = clean_text(match.group(1))
        if title:
            return title
    return fallback.stem.replace("-", " ").title()


def page_category(text: str) -> str:
    match = re.search(r'<span[^>]*class="[^"]*tag[^"]*"[^>]*>(.*?)</span>', text, flags=re.I | re.S)
    return clean_text(match.group(1)).lower() if match else ""


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def detect_new_article() -> Path | None:
    """Find the article created by the current workflow before it is committed."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", "posts"],
            check=False,
            capture_output=True,
            text=True,
        )
        untracked = []
        for line in result.stdout.splitlines():
            if not line.startswith("?? "):
                continue
            path = Path(line[3:].strip())
            if path.suffix.lower() == ".html" and path.name != "index.html" and path.exists():
                untracked.append(path)
        if untracked:
            return max(untracked, key=lambda p: p.stat().st_mtime)
    except Exception as exc:
        print(f"WARN could not inspect git status: {exc}")

    candidates = [p for p in POSTS.glob("*.html") if p.name != "index.html"]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def relevance_score(target_title: str, target_category: str, source_title: str, source_category: str) -> int:
    target_tokens = tokens(target_title)
    source_tokens = tokens(source_title)
    common = target_tokens & source_tokens
    score = len(common) * 5

    if target_category and source_category == target_category:
        score += 3

    # Small semantic bridges between closely related football-performance categories.
    performance_categories = {"speed & training", "fitness", "strength & power", "recovery & nutrition"}
    if target_category in performance_categories and source_category in performance_categories:
        score += 1

    return score


def contextual_link_count(text: str) -> int:
    return text.count("<!-- AUTO-CONTEXT-LINK:")


def insert_contextual_link(source: Path, target: Path, target_title: str) -> bool:
    text = source.read_text(encoding="utf-8")
    target_href = target.name

    if f'href="{target_href}"' in text or f"href='{target_href}'" in text:
        print(f"OK already linked: {source.name} -> {target.name}")
        return False

    if contextual_link_count(text) >= MAX_SOURCE_LINKS:
        print(f"SKIP contextual-link cap reached: {source.name}")
        return False

    article_start = text.find('<div class="article-content">')
    if article_start == -1:
        print(f"WARN article-content not found: {source.name}")
        return False

    paragraph = re.search(r"<p(?:\s[^>]*)?>.*?</p>", text[article_start:], flags=re.I | re.S)
    if not paragraph:
        print(f"WARN intro paragraph not found: {source.name}")
        return False

    insert_at = article_start + paragraph.end()
    safe_title = html.escape(target_title)
    block = (
        f'\n<!-- AUTO-CONTEXT-LINK:{target.name} -->\n'
        f'<p class="contextual-link"><strong>Related guide:</strong> '
        f'For another practical guide in this area, see our '
        f'<a href="{html.escape(target_href)}">{safe_title}</a>.</p>\n'
    )
    new_text = text[:insert_at] + block + text[insert_at:]
    source.write_text(new_text, encoding="utf-8")
    print(f"LINKED: {source.name} -> {target.name}")
    return True


def main() -> None:
    target = detect_new_article()
    if target is None or not target.exists():
        print("No article found for contextual internal linking.")
        return

    target_text = target.read_text(encoding="utf-8")
    target_title = page_title(target_text, target)
    target_category = page_category(target_text)

    ranked = []
    for source in POSTS.glob("*.html"):
        if source.name == "index.html" or source == target:
            continue
        source_text = source.read_text(encoding="utf-8")
        if f'href="{target.name}"' in source_text or f"href='{target.name}'" in source_text:
            continue
        if contextual_link_count(source_text) >= MAX_SOURCE_LINKS:
            continue

        source_title = page_title(source_text, source)
        source_category = page_category(source_text)
        score = relevance_score(target_title, target_category, source_title, source_category)
        if score <= 0:
            continue

        # Prefer equally relevant pages that currently have fewer auto contextual links.
        ranked.append((score, -contextual_link_count(source_text), source.name, source))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    chosen = [item[3] for item in ranked[:LINKS_PER_NEW_ARTICLE]]

    changed = 0
    for source in chosen:
        if insert_contextual_link(source, target, target_title):
            changed += 1

    print(f"Contextual-link target: {target.name}")
    print(f"Contextual-link target category: {target_category or 'unknown'}")
    print(f"Contextual internal links added: {changed}")


if __name__ == "__main__":
    main()
