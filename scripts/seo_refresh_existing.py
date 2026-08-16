from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path


def replace_meta(text: str, attr: str, key: str, value: str) -> str:
    pattern = rf'(<meta\s+{attr}="{re.escape(key)}"\s+content=")[^"]*(">)'
    return re.sub(pattern, lambda m: f'{m.group(1)}{value}{m.group(2)}', text, count=1)


def refresh_speed_training() -> bool:
    path = Path("posts/speed-training-for-football.html")
    if not path.exists():
        print(f"SEO refresh skipped: {path} not found")
        return False

    original = path.read_text(encoding="utf-8")
    text = original

    title = "Speed Training for Football: Drills, Acceleration & Weekly Plan"
    description = (
        "Improve speed for football with acceleration sprints, top-speed drills, "
        "change-of-direction work and a practical weekly training structure."
    )

    text = re.sub(r"<title>.*?</title>", f"<title>{title} | Football Training Lab</title>", text, count=1, flags=re.S)
    text = replace_meta(text, "name", "description", description)
    text = replace_meta(text, "property", "og:title", f"{title} | Football Training Lab")
    text = replace_meta(text, "property", "og:description", description)
    text = replace_meta(text, "name", "twitter:title", f"{title} | Football Training Lab")
    text = replace_meta(text, "name", "twitter:description", description)

    text = re.sub(r"<h1>.*?</h1>", f"<h1>{title}</h1>", text, count=1, flags=re.S)
    text = re.sub(
        r'<p class="article-description">.*?</p>',
        f'<p class="article-description">{description}</p>',
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r'alt="[^"]*" width="1200" height="630"',
        f'alt="{title}" width="1200" height="630"',
        text,
        count=1,
    )

    text = text.replace(
        '<h2 id="understanding-football-speed-and-its-components">Understanding Football Speed and Its Components</h2>',
        '<h2 id="understanding-football-speed-and-its-components">Football Speed vs Acceleration: What’s the Difference?</h2>',
    )

    quick_answer = """
<section class="key-takeaways search-answer" id="quick-answer">
<h2>Quick answer</h2>
<p>A practical speed-training plan for football starts with short acceleration sprints, then adds longer top-speed runs and change-of-direction work. Keep sprint reps high quality, use full recovery between hard efforts, and build volume gradually rather than turning every speed session into conditioning.</p>
</section>
"""
    if 'id="quick-answer"' not in text:
        text = text.replace('<div class="article-content">', '<div class="article-content">\n' + quick_answer, 1)

    weekly_plan = """
<h2 id="example-weekly-speed-training-plan">Example Weekly Speed Training Plan for Football</h2>
<p>This is a simple example for an amateur player. Adjust the total workload around team training and matches.</p>
<table>
<thead><tr><th>Session</th><th>Main focus</th><th>Example work</th></tr></thead>
<tbody>
<tr><td>Session 1</td><td>Acceleration</td><td>Short 5–15 m sprints with full recovery, followed by light strength work.</td></tr>
<tr><td>Session 2</td><td>Top speed + direction changes</td><td>Longer controlled sprints, then a small number of high-quality change-of-direction reps.</td></tr>
<tr><td>Before a match</td><td>Freshness</td><td>Reduce volume and avoid adding a hard sprint session when fatigue is already high.</td></tr>
</tbody>
</table>
<p>Quality matters more than accumulating tired sprint repetitions. Stop or reduce the session if sprint mechanics clearly deteriorate.</p>

"""
    if 'id="example-weekly-speed-training-plan"' not in text:
        marker = '<h2 id="safe-training-practices-and-recovery-considerations">'
        text = text.replace(marker, weekly_plan + marker, 1)

    text = text.replace(
        "<strong>Common mistakes:</strong> Patients overheating from improper warm-up or neglecting smooth deceleration technique leading to falls.",
        "<strong>Common mistakes:</strong> Rushing the drill while fatigued, turning with poor control, or neglecting smooth deceleration technique.",
    )

    # Keep structured data aligned with the visible page.
    script_match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', text, flags=re.S
    )
    if script_match:
        try:
            data = json.loads(script_match.group(1))
            for item in data.get("@graph", []):
                if item.get("@type") == "Article":
                    item["headline"] = title
                    item["description"] = description
                if item.get("@type") == "BreadcrumbList":
                    for crumb in item.get("itemListElement", []):
                        if crumb.get("position") == 3:
                            crumb["name"] = title
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            text = text[: script_match.start(1)] + encoded + text[script_match.end(1) :]
        except (json.JSONDecodeError, TypeError):
            print("Warning: could not update JSON-LD for speed-training-for-football.html")

    if text == original:
        print("SEO refresh: speed-training-for-football.html already up to date")
        return False

    today = date.today().isoformat()
    text = re.sub(r"Updated \d{4}-\d{2}-\d{2}", f"Updated {today}", text, count=1)

    # Update dateModified only after a real content change.
    script_match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', text, flags=re.S
    )
    if script_match:
        try:
            data = json.loads(script_match.group(1))
            for item in data.get("@graph", []):
                if item.get("@type") == "Article":
                    item["dateModified"] = today
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            text = text[: script_match.start(1)] + encoded + text[script_match.end(1) :]
        except (json.JSONDecodeError, TypeError):
            pass

    path.write_text(text, encoding="utf-8")
    print("SEO refreshed: posts/speed-training-for-football.html")
    return True


if __name__ == "__main__":
    refresh_speed_training()
