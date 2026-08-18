from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


HISTORY_PATH = Path("seo/gsc_optimization_history.json")

# These phrases imply authority or evidence the site may not actually document.
# Replace them with neutral wording instead of publishing an unsupported claim.
REPLACEMENTS = [
    (r"\bexpert[- ]approved\b", "practical"),
    (r"\bexpert tips?\b", "practical tips"),
    (r"\bexpert advice\b", "practical advice"),
    (r"\bexpert guidance\b", "practical guidance"),
    (r"\bexpert recommendations?\b", "practical recommendations"),
    (r"\bprofessional recommendations?\b", "practical recommendations"),
    (r"\bscientifically proven\b", "commonly used"),
    (r"\bclinically proven\b", "commonly used"),
    (r"\bscience[- ]backed\b", "practical"),
    (r"\bresearch[- ]backed\b", "practical"),
    (r"\bdoctor[- ]approved\b", "practical"),
    (r"\bphysio(?:therapist)?[- ]approved\b", "practical"),
]


def sanitize_text(value: str) -> tuple[str, int]:
    changed = value
    replacements = 0
    for pattern, replacement in REPLACEMENTS:
        changed, count = re.subn(pattern, replacement, changed, flags=re.I)
        replacements += count
    return changed, replacements


def changed_post_files() -> list[Path]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "posts"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[Path] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        if len(line) < 4:
            continue
        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        path = Path(path_text)
        if path.suffix.lower() == ".html" and path.exists():
            paths.append(path)
    return sorted(set(paths))


def sanitize_history() -> int:
    if not HISTORY_PATH.exists():
        return 0
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(history, list):
        return 0

    replacements = 0
    for item in history:
        if not isinstance(item, dict):
            continue
        for key in ("new_title", "new_description", "reason"):
            value = item.get(key)
            if not isinstance(value, str):
                continue
            cleaned, count = sanitize_text(value)
            if count:
                item[key] = cleaned
                replacements += count

    if replacements:
        HISTORY_PATH.write_text(
            json.dumps(history, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return replacements


def main() -> int:
    files = changed_post_files()
    total_replacements = 0
    changed_files = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        cleaned, count = sanitize_text(original)
        if not count:
            continue
        path.write_text(cleaned, encoding="utf-8")
        total_replacements += count
        changed_files += 1
        print(f"SEO claim guardrail sanitized: {path} | replacements={count}")

    history_replacements = sanitize_history()
    total_replacements += history_replacements

    if total_replacements == 0:
        print("SEO claim guardrail: no unsupported authority-style phrases detected.")
    else:
        print(
            "SEO claim guardrail complete: "
            f"files_changed={changed_files}, total_replacements={total_replacements}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
