from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from openai import OpenAI


FEEDBACK_PATH = Path("seo/gsc_feedback.json")
HISTORY_PATH = Path("seo/gsc_optimization_history.json")
MODEL = "gpt-4.1-mini"

MIN_QUERY_IMPRESSIONS = 10
MIN_PAGE_IMPRESSIONS = 20
COOLDOWN_DAYS = 28
MAX_OPTIMIZATIONS_PER_PAGE = 3

# These two pages are still maintained by the older deterministic refresh script.
EXCLUDED_FILES = {
    "speed-training-for-football.html",
    "leg-workout-for-football.html",
}

STOP_WORDS = {
    "a", "an", "and", "are", "best", "for", "from", "how", "in", "is",
    "of", "on", "the", "to", "with", "football", "footballers", "player", "players",
}

BANNED_PATTERNS = [
    r"\bamerican football\b",
    r"\bnfl\b",
    r"\bquarterbacks?\b",
    r"\blinebackers?\b",
    r"\bwide receivers?\b",
    r"\bdefensive backs?\b",
    r"\btouchdowns?\b",
    r"\bhelmets?\b",
    r"\bshoulder pads?\b",
]


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(value: str) -> str:
    return normalize_space(html.unescape(re.sub(r"<[^>]+>", " ", value)))


def extract_first(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, flags=re.I | re.S)
    return strip_tags(match.group(1)) if match else default


def current_title(text: str) -> str:
    title = extract_first(r"<h1[^>]*>(.*?)</h1>", text)
    if title:
        return title
    title = extract_first(r"<title>(.*?)</title>", text)
    return re.sub(r"\s*\|\s*Football Training Lab\s*$", "", title, flags=re.I)


def current_description(text: str) -> str:
    match = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"\s*/?>',
        text,
        flags=re.I,
    )
    if match:
        return html.unescape(match.group(1)).strip()
    return extract_first(r'<p class="article-description">(.*?)</p>', text)


def page_to_post(page_url: str) -> Path | None:
    parsed = urllib.parse.urlparse(page_url)
    if parsed.netloc not in {"footballtraininglab.com", "www.footballtraininglab.com"}:
        return None
    if not parsed.path.startswith("/posts/"):
        return None
    filename = parsed.path.removeprefix("/posts/").strip("/")
    if not filename:
        return None
    if not filename.endswith(".html"):
        filename += ".html"
    path = Path("posts") / filename
    return path if path.exists() else None


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def recently_optimized(page: str, history: list[dict]) -> bool:
    cutoff = date.today() - timedelta(days=COOLDOWN_DAYS)
    dates: list[date] = []
    for item in history:
        if item.get("page") != page:
            continue
        try:
            dates.append(date.fromisoformat(str(item.get("date", ""))))
        except ValueError:
            continue
    return bool(dates and max(dates) >= cutoff)


def optimization_count(page: str, history: list[dict]) -> int:
    return sum(
        1
        for item in history
        if item.get("page") == page and item.get("status") == "applied"
    )


def candidate_rows(feedback: dict, history: list[dict]) -> list[dict]:
    page_summaries = {
        row.get("page"): row
        for row in feedback.get("all_page_summaries", [])
        if isinstance(row, dict) and row.get("page")
    }

    candidates: list[dict] = []
    seen_pages: set[str] = set()
    for row in feedback.get("top_query_opportunities", []):
        if not isinstance(row, dict):
            continue
        page = str(row.get("page", ""))
        if not page or page in seen_pages:
            continue
        if row.get("opportunity") not in {"high_ctr_opportunity", "quick_win"}:
            continue
        if float(row.get("impressions", 0) or 0) < MIN_QUERY_IMPRESSIONS:
            continue

        summary = page_summaries.get(page, {})
        if float(summary.get("impressions", 0) or 0) < MIN_PAGE_IMPRESSIONS:
            continue

        path = page_to_post(page)
        if not path or path.name in EXCLUDED_FILES:
            continue
        if recently_optimized(page, history):
            continue
        if optimization_count(page, history) >= MAX_OPTIMIZATIONS_PER_PAGE:
            continue

        copy = dict(row)
        copy["page_impressions"] = float(summary.get("impressions", 0) or 0)
        copy["page_position"] = float(summary.get("position", 0) or 0)
        candidates.append(copy)
        seen_pages.add(page)

    candidates.sort(
        key=lambda item: (
            1 if item.get("opportunity") == "high_ctr_opportunity" else 0,
            float(item.get("score", 0) or 0),
            float(item.get("impressions", 0) or 0),
        ),
        reverse=True,
    )
    return candidates


def target_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def enough_query_overlap(value: str, query: str) -> bool:
    required = target_tokens(query)
    if not required:
        return "football" in value.lower()
    present = set(re.findall(r"[a-z0-9]+", value.lower()))
    return len(required & present) / len(required) >= 0.6


def has_banned_context(value: str) -> bool:
    return any(re.search(pattern, value, flags=re.I) for pattern in BANNED_PATTERNS)


def article_evidence(text: str, max_chars: int = 9000) -> str:
    content_match = re.search(
        r'<div class="article-content">(.*?)</div>\s*</article>',
        text,
        flags=re.I | re.S,
    )
    source = content_match.group(1) if content_match else text
    return strip_tags(source)[:max_chars]


def parse_ai_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise ValueError("AI output did not contain a JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI output was not a JSON object")
    return data


def generate_optimization(text: str, candidate: dict, related_queries: list[str]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    old_title = current_title(text)
    old_description = current_description(text)
    query = str(candidate["query"])

    prompt = f'''
You are making ONE conservative SEO edit to an existing association-football (soccer) article.

Website: Football Training Lab
Audience: amateur, beginner and developing football players.
The article is already indexed/visible in Google. Preserve its topic, URL, factual meaning and overall structure.

Google Search Console signal:
- target query: {query}
- query impressions: {candidate.get("impressions", 0)}
- query clicks: {candidate.get("clicks", 0)}
- query CTR: {candidate.get("ctr", 0)}
- query average position: {candidate.get("position", 0)}
- page impressions: {candidate.get("page_impressions", 0)}
- page average position: {candidate.get("page_position", 0)}
- other related queries for this same page: {json.dumps(related_queries[:6], ensure_ascii=False)}

Current title:
{old_title}

Current meta description:
{old_description}

Existing article evidence:
{article_evidence(text)}

Return ONLY valid JSON with exactly these keys:
{{
  "title": "...",
  "description": "...",
  "quick_answer": "...",
  "reason": "..."
}}

Rules:
- This is association football / soccer only, never American football.
- Do not change the article into a different topic.
- Do not invent products, brands, prices, studies, statistics, rules or claims absent from the existing article evidence.
- No clickbait and no false promises.
- The title must be natural English, truthful, 40-68 characters, and strongly match the target query intent.
- The title must NOT contain "| Football Training Lab"; the site suffix is added by code.
- The description must be 120-165 characters and describe what the existing article genuinely covers.
- The quick_answer must be 45-90 words, directly answer the target query, and use only information supported by the article evidence.
- If the current title is already excellent, you may keep it unchanged rather than forcing a rewrite.
- Prefer a small precise improvement over a dramatic rewrite.
- Do not use a year or date.
'''.strip()

    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=MODEL, input=prompt)
    return parse_ai_json(response.output_text)


def validate_optimization(data: dict, query: str) -> tuple[str, str, str, str]:
    title = normalize_space(strip_tags(str(data.get("title", ""))))
    description = normalize_space(strip_tags(str(data.get("description", ""))))
    quick_answer = normalize_space(strip_tags(str(data.get("quick_answer", ""))))
    reason = normalize_space(strip_tags(str(data.get("reason", ""))))

    if not 40 <= len(title) <= 68:
        raise ValueError(f"title length {len(title)} is outside 40-68")
    if not 120 <= len(description) <= 165:
        raise ValueError(f"description length {len(description)} is outside 120-165")
    words = quick_answer.split()
    if not 45 <= len(words) <= 90:
        raise ValueError(f"quick_answer word count {len(words)} is outside 45-90")
    if "football" not in title.lower():
        raise ValueError("title does not mention football")
    if not enough_query_overlap(title + " " + description, query):
        raise ValueError("optimized title/description do not sufficiently match target query")
    if has_banned_context(" ".join([title, description, quick_answer])):
        raise ValueError("American-football context detected")
    if re.search(r"\b202\d\b", title + " " + description):
        raise ValueError("year/date detected in SEO fields")

    return title, description, quick_answer, reason


def replace_meta(text: str, attr: str, key: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    pattern = rf'(<meta\s+{attr}="{re.escape(key)}"\s+content=")[^"]*("\s*/?>)'
    return re.sub(
        pattern,
        lambda match: f"{match.group(1)}{escaped}{match.group(2)}",
        text,
        count=1,
        flags=re.I,
    )


def update_json_ld(text: str, title: str, description: str, today: str) -> str:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        text,
        flags=re.I | re.S,
    )
    if not match:
        return text
    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return text

    graph = data.get("@graph", []) if isinstance(data, dict) else []
    for item in graph:
        if not isinstance(item, dict):
            continue
        if item.get("@type") == "Article":
            item["headline"] = title
            item["description"] = description
            item["dateModified"] = today
        elif item.get("@type") == "BreadcrumbList":
            for crumb in item.get("itemListElement", []):
                if isinstance(crumb, dict) and crumb.get("position") == 3:
                    crumb["name"] = title

    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text[: match.start(1)] + encoded + text[match.end(1) :]


def replace_quick_answer(text: str, answer: str) -> tuple[str, str]:
    escaped = html.escape(answer, quote=False)

    paragraph_pattern = r'(<p>\s*<strong>Quick answer:</strong>\s*).*?(</p>)'
    if re.search(paragraph_pattern, text, flags=re.I | re.S):
        return (
            re.sub(
                paragraph_pattern,
                lambda match: f"{match.group(1)}{escaped}{match.group(2)}",
                text,
                count=1,
                flags=re.I | re.S,
            ),
            "replaced_existing_paragraph",
        )

    section_pattern = (
        r'(<section[^>]+id="[^"]*quick-answer[^"]*"[^>]*>.*?'
        r'<h2[^>]*>\s*Quick answer\s*</h2>\s*<p>).*?(</p>)'
    )
    if re.search(section_pattern, text, flags=re.I | re.S):
        return (
            re.sub(
                section_pattern,
                lambda match: f"{match.group(1)}{escaped}{match.group(2)}",
                text,
                count=1,
                flags=re.I | re.S,
            ),
            "replaced_existing_section",
        )

    section = (
        '\n<section class="key-takeaways search-answer gsc-search-answer" id="gsc-search-answer">\n'
        "<h2>Quick answer</h2>\n"
        f"<p>{escaped}</p>\n"
        "</section>\n"
    )
    marker = '<div class="article-content">'
    if marker in text:
        return text.replace(marker, marker + section, 1), "inserted_new_section"

    return text, "not_changed"


def apply_optimization(path: Path, data: dict, candidate: dict) -> dict:
    original = path.read_text(encoding="utf-8")
    old_title = current_title(original)
    old_description = current_description(original)

    title, description, quick_answer, reason = validate_optimization(
        data,
        str(candidate["query"]),
    )
    text = original
    display_title = html.escape(title, quote=False)
    meta_title = f"{title} | Football Training Lab"

    text = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(meta_title, quote=False)}</title>",
        text,
        count=1,
        flags=re.I | re.S,
    )
    text = replace_meta(text, "name", "description", description)
    text = replace_meta(text, "property", "og:title", meta_title)
    text = replace_meta(text, "property", "og:description", description)
    text = replace_meta(text, "name", "twitter:title", meta_title)
    text = replace_meta(text, "name", "twitter:description", description)

    text = re.sub(
        r"<h1[^>]*>.*?</h1>",
        f"<h1>{display_title}</h1>",
        text,
        count=1,
        flags=re.I | re.S,
    )
    text = re.sub(
        r'(<p class="article-description">).*?(</p>)',
        lambda match: (
            f"{match.group(1)}{html.escape(description, quote=False)}{match.group(2)}"
        ),
        text,
        count=1,
        flags=re.I | re.S,
    )
    text = re.sub(
        r'(<img\s+class="article-hero"[^>]*\salt=")[^"]*(")',
        lambda match: f'{match.group(1)}{html.escape(title, quote=True)}{match.group(2)}',
        text,
        count=1,
        flags=re.I,
    )

    text, answer_action = replace_quick_answer(text, quick_answer)

    today = date.today().isoformat()
    text = re.sub(r"Updated \d{4}-\d{2}-\d{2}", f"Updated {today}", text, count=1)
    text = update_json_ld(text, title, description, today)

    if text == original:
        return {
            "changed": False,
            "old_title": old_title,
            "new_title": title,
            "old_description": old_description,
            "new_description": description,
            "quick_answer_action": answer_action,
            "reason": reason,
        }

    path.write_text(text, encoding="utf-8")
    return {
        "changed": True,
        "old_title": old_title,
        "new_title": title,
        "old_description": old_description,
        "new_description": description,
        "quick_answer_action": answer_action,
        "reason": reason,
    }


def related_queries_for_page(feedback: dict, page: str) -> list[str]:
    rows: list[str] = []
    for row in feedback.get("top_query_opportunities", []):
        if isinstance(row, dict) and row.get("page") == page and row.get("query"):
            rows.append(str(row["query"]))
    return rows


def write_history(history: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if not FEEDBACK_PATH.exists():
        print("GSC SEO optimizer skipped: feedback file is missing.")
        return 0

    try:
        feedback = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"GSC SEO optimizer skipped: invalid feedback JSON: {exc}")
        return 0

    history = load_history()
    candidates = candidate_rows(feedback, history)
    print(f"GSC SEO optimizer eligible pages: {len(candidates)}")

    if not candidates:
        print("GSC SEO optimizer: no page meets the conservative thresholds this run.")
        return 0

    candidate = candidates[0]
    page = str(candidate["page"])
    path = page_to_post(page)
    if path is None:
        print(f"GSC SEO optimizer skipped: local article not found for {page}")
        return 0

    print(f"GSC SEO optimizer selected: {path}")
    print(
        "GSC SEO target: "
        f"{candidate['query']} | impressions={candidate.get('impressions', 0)} | "
        f"clicks={candidate.get('clicks', 0)} | position={candidate.get('position', 0)}"
    )

    original = path.read_text(encoding="utf-8")
    try:
        proposal = generate_optimization(
            original,
            candidate,
            related_queries_for_page(feedback, page),
        )
        result = apply_optimization(path, proposal, candidate)
    except Exception as exc:
        print(f"WARN GSC SEO optimizer skipped selected page safely: {exc}")
        return 0

    if not result["changed"]:
        print("GSC SEO optimizer: AI proposal produced no file changes; nothing was recorded.")
        return 0

    history.append(
        {
            "date": date.today().isoformat(),
            "status": "applied",
            "page": page,
            "file": str(path),
            "target_query": candidate.get("query"),
            "query_impressions": candidate.get("impressions"),
            "query_clicks": candidate.get("clicks"),
            "query_ctr": candidate.get("ctr"),
            "query_position": candidate.get("position"),
            "page_impressions": candidate.get("page_impressions"),
            "page_position": candidate.get("page_position"),
            "old_title": result["old_title"],
            "new_title": result["new_title"],
            "old_description": result["old_description"],
            "new_description": result["new_description"],
            "quick_answer_action": result["quick_answer_action"],
            "reason": result["reason"],
        }
    )
    write_history(history)

    print("GSC SEO optimizer applied exactly 1 article this run.")
    print(f"GSC SEO title changed: {result['old_title'] != result['new_title']}")
    print(
        f"GSC SEO description changed: "
        f"{result['old_description'] != result['new_description']}"
    )
    print(f"GSC SEO quick answer: {result['quick_answer_action']}")
    print(f"GSC SEO cooldown: {COOLDOWN_DAYS} days per page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
