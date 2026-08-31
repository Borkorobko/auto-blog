from pathlib import Path
import re
import subprocess

import adsense_quality_cleanup as cleanup

POSTS = Path("posts")


def recover_stronger_boots_guide() -> None:
    """Promote the stronger legacy boots article into the preferred canonical URL."""
    result = subprocess.run(
        ["git", "show", "origin/main:posts/best-boots-for-speed.html"],
        check=True,
        capture_output=True,
        text=True,
    )
    page = result.stdout
    replacements = {
        "Best Boots For Speed | Football Training Lab": "Football Boots for Speed: Fit, Traction & Buying Guide | Football Training Lab",
        "Best Boots For Speed": "Football Boots for Speed: Fit, Traction & Buying Guide",
        "Practical guide to Best Boots For Speed, covering fit, materials, durability, maintenance and value for football players.": "Football boots for speed explained: compare fit, traction, soleplates, materials and position-specific trade-offs before you buy.",
        "https://footballtraininglab.com/posts/best-boots-for-speed.html": "https://footballtraininglab.com/posts/best-football-boots-for-speed.html",
        "https://footballtraininglab.com/images/best-boots-for-speed.svg": "https://footballtraininglab.com/images/best-football-boots-for-speed.svg",
        "../images/best-boots-for-speed.svg": "../images/best-football-boots-for-speed.svg",
        "protect yourself from injury": "support comfort and secure movement",
        "slipping reduces efficiency and increases injury risk": "slipping can reduce efficiency, stability and comfort",
        "which can decrease speed and increase injury risk": "which can reduce sprint efficiency and place extra stress on the body",
        "worn-out boots can negatively impact speed and safety": "worn-out boots can reduce traction, fit and comfort",
    }
    for old, new in replacements.items():
        page = page.replace(old, new)

    # Keep a clean, descriptive H1 rather than implying hands-on product testing.
    page = page.replace(
        "<h1>Football Boots for Speed: Fit, Traction & Buying Guide</h1>",
        "<h1>Football Boots for Speed: Fit, Traction & Buying Guide</h1>",
    )
    target = POSTS / "best-football-boots-for-speed.html"
    target.write_text(page, encoding="utf-8")
    print(f"Promoted stronger boots guide to {target}")


def dedupe_related_cards() -> int:
    pattern = re.compile(
        r'<a class="related-card" href="([^"]+)">.*?</a>',
        flags=re.I | re.S,
    )
    updated = 0
    retired = set(cleanup.REDIRECTS)
    for post in sorted(POSTS.glob("*.html")):
        if post.name == "index.html" or post.stem in retired:
            continue
        page = post.read_text(encoding="utf-8", errors="ignore")
        seen: set[str] = set()

        def keep_first(match: re.Match[str]) -> str:
            href = match.group(1)
            if href in seen:
                return ""
            seen.add(href)
            return match.group(0)

        changed = pattern.sub(keep_first, page)
        if changed != page:
            post.write_text(changed, encoding="utf-8")
            updated += 1
    return updated


def main() -> None:
    recover_stronger_boots_guide()
    cleanup.main()
    deduped = dedupe_related_cards()
    # Rebuild the library/sitemap after final content/title changes.
    cleanup.build_library()
    cleanup.build_sitemap()
    print(f"Articles with duplicate related-card links cleaned: {deduped}")


if __name__ == "__main__":
    main()
