from pathlib import Path
import re

PUBLISHER_ID = "ca-pub-4653487457062463"
ADSENSE_SNIPPET = (
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?'
    f'client={PUBLISHER_ID}" crossorigin="anonymous"></script>'
)
ADSENSE_PATTERN = re.compile(
    r'\s*<script\s+async\s+src="https://pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js\?client='
    + re.escape(PUBLISHER_ID)
    + r'"\s+crossorigin="anonymous"></script>\s*',
    flags=re.I,
)

# Google recommends that the privacy-policy URL used by its CMP does not host
# scripts that require consent, including ad tags. Keep both legal consent pages
# free of the AdSense loader.
NO_ADS_PAGES = {
    Path("pages/privacy.html"),
    Path("pages/cookies.html"),
}


def html_files() -> list[Path]:
    files: list[Path] = []
    homepage = Path("index.html")
    if homepage.exists():
        files.append(homepage)
    files.extend(sorted(Path("posts").glob("*.html")))
    files.extend(sorted(Path("pages").glob("*.html")))
    return files


def remove_adsense(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    updated = ADSENSE_PATTERN.sub("\n", text)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def inject(path: Path) -> bool:
    if path in NO_ADS_PAGES:
        if remove_adsense(path):
            print(f"AdSense removed from consent-policy page: {path}")
            return True
        print(f"AdSense intentionally skipped on consent-policy page: {path}")
        return False

    text = path.read_text(encoding="utf-8")

    # Idempotent: do not add the AdSense loader twice.
    if PUBLISHER_ID in text and "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in text:
        return False

    if not re.search(r"<head\b[^>]*>", text, flags=re.I):
        print(f"AdSense skipped (no <head>): {path}")
        return False

    updated = re.sub(
        r"(<head\b[^>]*>)",
        lambda match: match.group(1) + "\n" + ADSENSE_SNIPPET,
        text,
        count=1,
        flags=re.I,
    )
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    checked = 0
    for path in html_files():
        checked += 1
        if inject(path):
            changed += 1
            print(f"AdSense integration updated: {path}")

    print(f"AdSense integration complete: checked={checked}, changed={changed}")


if __name__ == "__main__":
    main()
