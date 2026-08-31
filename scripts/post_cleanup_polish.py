from pathlib import Path
import re

import adsense_quality_cleanup as cleanup

POSTS = Path("posts")


def polish_boots_guide() -> bool:
    path = POSTS / "best-football-boots-for-speed.html"
    page = path.read_text(encoding="utf-8")
    changed = page
    changed = changed.replace(
        "Practical guide to Football Boots for Speed: Fit, Traction & Buying Guide, covering fit, materials, durability, maintenance and value for football players.",
        "Compare fit, traction, soleplates, materials and position-specific trade-offs when choosing football boots for speed.",
    )
    changed = changed.replace(
        "Football Boots for Speed: Fit, Traction & Buying Guide: A Practical Guide for Amateur Football Players",
        "Football Boots for Speed: A Practical Guide for Amateur Players",
    )
    if changed != page:
        path.write_text(changed, encoding="utf-8")
        return True
    return False


def verify_cleanup() -> None:
    sitemap = Path("sitemap.xml").read_text(encoding="utf-8")
    library = (POSTS / "index.html").read_text(encoding="utf-8")

    problems: list[str] = []
    for source in cleanup.REDIRECTS:
        url_fragment = f"/posts/{source}.html"
        if url_fragment in sitemap:
            problems.append(f"redirect source still in sitemap: {source}")
        if f'href="{source}.html"' in library:
            problems.append(f"redirect source still in article library: {source}")

    if "Foootball News" in library or "foootball-news.html" in library:
        problems.append("typo news page still appears in active library")

    strength = (POSTS / "strength-training-for-football.html").read_text(encoding="utf-8")
    if "Football Strength Training For" in strength:
        problems.append("incomplete strength title still present")

    card_pattern = re.compile(r'<a class="related-card" href="([^"]+)"', flags=re.I)
    for post in cleanup.active_posts():
        page = post.read_text(encoding="utf-8", errors="ignore")
        hrefs = card_pattern.findall(page)
        if len(hrefs) != len(set(hrefs)):
            problems.append(f"duplicate related-card targets: {post.name}")

    for source, target in cleanup.REDIRECTS.items():
        source_page = (POSTS / f"{source}.html").read_text(encoding="utf-8", errors="ignore")
        if 'name="robots" content="noindex, follow"' not in source_page:
            problems.append(f"redirect source missing noindex: {source}")
        expected = cleanup.target_url(target)
        if expected not in source_page:
            problems.append(f"redirect source missing canonical target: {source}")

    if problems:
        raise RuntimeError("AdSense cleanup verification failed:\n- " + "\n- ".join(problems))

    print(f"Verified active indexable articles: {len(cleanup.active_posts())}")
    print(f"Verified consolidated/noindex URLs: {len(cleanup.REDIRECTS)}")
    print("Sitemap, article library, redirect canonicals and related links passed cleanup verification.")


def main() -> None:
    polished = polish_boots_guide()
    cleanup.build_library()
    cleanup.build_sitemap()
    print(f"Boots guide polished: {polished}")
    verify_cleanup()


if __name__ == "__main__":
    main()
