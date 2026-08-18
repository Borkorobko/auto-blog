from pathlib import Path
import re

PUBLISHER_ID = "ca-pub-4653487457062463"
ADSENSE_SNIPPET = (
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?'
    f'client={PUBLISHER_ID}" crossorigin="anonymous"></script>'
)


def html_files() -> list[Path]:
    files: list[Path] = []
    homepage = Path("index.html")
    if homepage.exists():
        files.append(homepage)
    files.extend(sorted(Path("posts").glob("*.html")))
    files.extend(sorted(Path("pages").glob("*.html")))
    return files


def inject(path: Path) -> bool:
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
            print(f"AdSense injected: {path}")

    print(f"AdSense integration complete: checked={checked}, changed={changed}")


if __name__ == "__main__":
    main()
