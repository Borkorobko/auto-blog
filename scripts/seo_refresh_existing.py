from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path


def replace_meta(text: str, attr: str, key: str, value: str) -> str:
    pattern = rf'(<meta\s+{attr}="{re.escape(key)}"\s+content=")[^"]*(">)'
    return re.sub(pattern, lambda m: f'{m.group(1)}{value}{m.group(2)}', text, count=1)


def update_json_ld(text: str, title: str, description: str, today: str | None = None, faq_items: list[tuple[str, str]] | None = None) -> str:
    script_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, flags=re.S)
    if not script_match:
        return text

    try:
        data = json.loads(script_match.group(1))
        for item in data.get("@graph", []):
            if item.get("@type") == "Article":
                item["headline"] = title
                item["description"] = description
                if today:
                    item["dateModified"] = today
            elif item.get("@type") == "BreadcrumbList":
                for crumb in item.get("itemListElement", []):
                    if crumb.get("position") == 3:
                        crumb["name"] = title
            elif item.get("@type") == "FAQPage" and faq_items:
                item["mainEntity"] = [
                    {
                        "@type": "Question",
                        "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": answer},
                    }
                    for question, answer in faq_items
                ]
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return text[: script_match.start(1)] + encoded + text[script_match.end(1) :]
    except (json.JSONDecodeError, TypeError):
        return text


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

    text = update_json_ld(text, title, description)

    if text == original:
        print("SEO refresh: speed-training-for-football.html already up to date")
        return False

    today = date.today().isoformat()
    text = re.sub(r"Updated \d{4}-\d{2}-\d{2}", f"Updated {today}", text, count=1)
    text = update_json_ld(text, title, description, today=today)

    path.write_text(text, encoding="utf-8")
    print("SEO refreshed: posts/speed-training-for-football.html")
    return True


def refresh_leg_workout() -> bool:
    path = Path("posts/leg-workout-for-football.html")
    if not path.exists():
        print(f"SEO refresh skipped: {path} not found")
        return False

    original = path.read_text(encoding="utf-8")
    text = original

    title = "Leg Workout for Football Players: Strength & Power Plan"
    description = (
        "Build stronger, more explosive legs with a football-specific lower body workout "
        "using squats, lunges, jumps, sprints, sets, reps and a simple weekly plan."
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

    quick_answer = """
<section class="key-takeaways search-answer" id="leg-workout-quick-answer">
<h2>Quick answer</h2>
<p>A strong lower-body workout for football players should train the quads, hamstrings, glutes and calves while also developing single-leg strength and explosiveness. A practical session can combine squats or lunges, hip-dominant work, step-ups, jumps and short sprints. For most amateur players, two well-spaced leg sessions per week is a sensible starting point around team training and matches.</p>
</section>
"""
    if 'id="leg-workout-quick-answer"' not in text:
        text = text.replace('<div class="article-content">', '<div class="article-content">\n' + quick_answer, 1)

    text = text.replace(
        '<h2 id="football-leg-workout-for-strength-power">Football Leg Workout For Strength & Power</h2>',
        '<h2 id="football-leg-workout-for-strength-power">Best Leg Workout for Football Players: Strength &amp; Power</h2>',
    )
    text = text.replace(
        '<h2 id="key-components-of-a-football-leg-workout-for-strength-power">Key Components of a Football Leg Workout for Strength & Power</h2>',
        '<h2 id="key-components-of-a-football-leg-workout-for-strength-power">Lower Body Workout for Football Players: What to Train</h2>',
    )
    text = text.replace(
        '<h2 id="the-workout-exercises-sets-and-progressions">The Workout: Exercises, Sets, and Progressions</h2>',
        '<h2 id="the-workout-exercises-sets-and-progressions">Best Leg Exercises for Football Players: Sets and Reps</h2>',
    )

    text = text.replace(
        '<li><a href="#football-leg-workout-for-strength-power">Football Leg Workout For Strength &amp; Power</a></li>',
        '<li><a href="#football-leg-workout-for-strength-power">Best Leg Workout for Football Players</a></li>',
    )
    text = text.replace(
        '<li><a href="#key-components-of-a-football-leg-workout-for-strength-power">Key Components of a Football Leg Workout for Strength &amp; Power</a></li>',
        '<li><a href="#key-components-of-a-football-leg-workout-for-strength-power">Lower Body Workout: What to Train</a></li>',
    )
    text = text.replace(
        '<li><a href="#the-workout-exercises-sets-and-progressions">The Workout: Exercises, Sets, and Progressions</a></li>',
        '<li><a href="#the-workout-exercises-sets-and-progressions">Best Leg Exercises: Sets and Reps</a></li>',
    )

    # The duplicate page was consolidated, so never link back to it.
    text = text.replace(
        '<a class="related-card" href="leg-workout-for-football-players.html"><strong>Leg Workout for Football Players</strong><span>Read guide →</span></a>',
        '<a class="related-card" href="strength-training-for-football.html"><strong>Strength Training for Football</strong><span>Read guide →</span></a>',
    )

    faq_items = [
        (
            "What is the best leg workout for football players?",
            "A balanced football leg workout combines a squat or lunge pattern, hip-dominant hamstring and glute work, single-leg exercises, calf work, a small amount of jumping and short sprints. The best version is one you can perform with good technique and recover from around team training and matches.",
        ),
        (
            "How often should football players train legs?",
            "For many amateur players, two lower-body strength sessions per week is a practical starting point. Space hard leg sessions apart and reduce gym volume when match or team-training load is high.",
        ),
        (
            "Do football players need weights to build stronger legs?",
            "Weights are useful but not essential. Bodyweight squats, split squats, lunges, step-ups, bridges, jumps and resistance-band exercises can build a useful strength base. Add external load gradually when technique is consistent.",
        ),
    ]

    text = re.sub(
        r'<h3>Can I do strength and power training on my own if I’m just starting football\?</h3>\s*<p>.*?</p>',
        f'<h3>{faq_items[0][0]}</h3>\n<p>{faq_items[0][1]}</p>',
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r'<h3>How soon will I notice improvements in my football performance from leg workouts\?</h3>\s*<p>.*?</p>',
        f'<h3>{faq_items[1][0]}</h3>\n<p>{faq_items[1][1]}</p>',
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r'<h3>Is it necessary to use weights like barbells or machines to build leg strength\?</h3>\s*<p>.*?</p>',
        f'<h3>{faq_items[2][0]}</h3>\n<p>{faq_items[2][1]}</p>',
        text,
        count=1,
        flags=re.S,
    )

    text = update_json_ld(text, title, description, faq_items=faq_items)

    if text == original:
        print("SEO refresh: leg-workout-for-football.html already up to date")
        return False

    today = date.today().isoformat()
    text = re.sub(r"Updated \d{4}-\d{2}-\d{2}", f"Updated {today}", text, count=1)
    text = update_json_ld(text, title, description, today=today, faq_items=faq_items)

    path.write_text(text, encoding="utf-8")
    print("SEO refreshed: posts/leg-workout-for-football.html")
    return True


if __name__ == "__main__":
    refresh_speed_training()
    refresh_leg_workout()
