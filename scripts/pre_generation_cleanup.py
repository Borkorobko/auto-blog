from pathlib import Path
import re

POSTS = Path("posts")
IMAGES = Path("images")
KEYWORDS_FILE = Path("keywords.txt")

STOP_WORDS = {
    "a", "an", "and", "for", "from", "how", "in", "of", "on", "the",
    "to", "with", "football", "player", "players",
}

# Explicit consolidations where we know which URL should keep the SEO history.
# The target URL is preserved; the newer duplicate is removed before the site is rebuilt.
KNOWN_DUPLICATES = {
    "leg-workout-for-football-players.html": "leg-workout-for-football.html",
}


def topic_signature(text: str) -> tuple[str, ...]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 2
    }
    return tuple(sorted(tokens))


def remove_known_duplicates() -> int:
    removed = 0
    for duplicate_name, preferred_name in KNOWN_DUPLICATES.items():
        duplicate = POSTS / duplicate_name
        preferred = POSTS / preferred_name
        if duplicate.exists() and preferred.exists():
            duplicate.unlink()
            image = IMAGES / f"{Path(duplicate_name).stem}.svg"
            if image.exists():
                image.unlink()
            print(f"Consolidated duplicate: {duplicate_name} -> {preferred_name}")
            removed += 1
    return removed


def remove_duplicate_keywords() -> int:
    if not KEYWORDS_FILE.exists():
        return 0

    existing_signatures = {}
    for post in POSTS.glob("*.html"):
        if post.name == "index.html":
            continue
        signature = topic_signature(post.stem.replace("-", " "))
        if signature:
            existing_signatures.setdefault(signature, post.name)

    original = [line.strip() for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept = []
    removed = 0

    for keyword in original:
        signature = topic_signature(keyword)
        duplicate_of = existing_signatures.get(signature)
        if signature and duplicate_of:
            print(f"Removed duplicate keyword: {keyword} (matches {duplicate_of})")
            removed += 1
            continue
        kept.append(keyword)

    if kept != original:
        KEYWORDS_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    return removed


removed_pages = remove_known_duplicates()
removed_keywords = remove_duplicate_keywords()
print(f"Pre-generation cleanup: duplicate pages removed={removed_pages}, duplicate keywords removed={removed_keywords}")
