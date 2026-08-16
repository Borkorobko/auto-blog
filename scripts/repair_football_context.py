from pathlib import Path
import html
import json
import os
import re
from datetime import datetime, timezone

from openai import OpenAI

POSTS = Path("posts")
MODEL = "gpt-4.1-mini"
MAX_REPAIRS_PER_RUN = 3

AMERICAN_FOOTBALL_PATTERNS = [
    r"\bhelmet(?:s)?\b",
    r"\bshoulder pads?\b",
    r"\bmouthguards?\b",
    r"\bquarterbacks?\b",
    r"\blinebackers?\b",
    r"\bwide receivers?\b",
    r"\bdefensive backs?\b",
    r"\btouchdowns?\b",
    r"\bNFL\b",
]

EQUIPMENT_PATTERNS = [
    r"\bboot(?:s)?\b", r"\bcleat(?:s)?\b", r"\bshin guards?\b",
    r"\bglove(?:s)?\b", r"\bequipment\b", r"\bwater bottle\b",
    r"\bresistance bands?\b", r"\bgear\b", r"\bcone(?:s)?\b",
    r"\bladder\b", r"\bbackpack\b", r"\bsock(?:s)?\b",
    r"\brebounder\b", r"\bball\b",
]

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def clean_text(fragment: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", fragment, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def clean_ai_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    cleaned = re.sub(r"</?(?:html|head|body|article)[^>]*>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<script.*?</script>", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<style.*?</style>", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<h1[^>]*>.*?</h1>", "", cleaned, flags=re.I | re.S)
    return cleaned.strip()


def article_content_bounds(page: str) -> tuple[int, int]:
    start_match = re.search(r'<div\s+class=["\']article-content["\']\s*>', page, flags=re.I)
    if not start_match:
        raise RuntimeError("article-content opening tag not found")
    start = start_match.end()
    related = page.find("<!-- RELATED-START -->", start)
    if related != -1:
        end = page.rfind("</div>", start, related)
    else:
        article_end = page.lower().find("</article>", start)
        end = page.rfind("</div>", start, article_end)
    if end < start:
        raise RuntimeError("article-content closing tag not found")
    return start, end


def extract_body(page: str) -> str:
    start, end = article_content_bounds(page)
    return page[start:end].strip()


def replace_body(page: str, body: str) -> str:
    start, end = article_content_bounds(page)
    return page[:start] + body + page[end:]


def extract_title(page: str, fallback: Path) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.I | re.S)
    if match:
        return clean_text(match.group(1))
    return fallback.stem.replace("-", " ").title()


def extract_category(page: str) -> str:
    match = re.search(r'<span\s+class="tag">(.*?)</span>', page, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def has_american_football_markers(body: str) -> bool:
    text = clean_text(body)
    return any(re.search(pattern, text, flags=re.I) for pattern in AMERICAN_FOOTBALL_PATTERNS)


def marker_labels(body: str) -> list[str]:
    text = clean_text(body)
    labels = []
    for pattern in AMERICAN_FOOTBALL_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            labels.append(pattern)
    return labels


def inferred_category(title: str, fallback: str) -> str:
    lower = title.lower()
    if any(re.search(pattern, lower, flags=re.I) for pattern in EQUIPMENT_PATTERNS):
        return "Equipment"
    return fallback


def update_visible_category(page: str, category: str) -> str:
    escaped = html.escape(category)
    page = re.sub(
        r'(<span\s+class="tag">).*?(</span>)',
        lambda m: f"{m.group(1)}{escaped}{m.group(2)}",
        page,
        count=1,
        flags=re.I | re.S,
    )

    breadcrumb = re.search(
        r'(<nav\s+class="breadcrumbs"[^>]*>)(.*?)(</nav>)',
        page,
        flags=re.I | re.S,
    )
    if breadcrumb:
        inner = breadcrumb.group(2)
        spans = list(re.finditer(r"<span>.*?</span>", inner, flags=re.I | re.S))
        if spans:
            last = spans[-1]
            inner = inner[:last.start()] + f"<span>{escaped}</span>" + inner[last.end():]
            page = page[:breadcrumb.start(2)] + inner + page[breadcrumb.end(2):]
    return page


def extract_faq(body: str) -> list[dict]:
    section = re.search(
        r'<section[^>]*class="[^"]*faq[^"]*"[^>]*>(.*?)</section>',
        body,
        flags=re.I | re.S,
    )
    if not section:
        return []
    pairs = re.findall(r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>", section.group(1), flags=re.I | re.S)
    result = []
    for question, answer in pairs[:5]:
        q = clean_text(question)
        a = clean_text(answer)
        if q and a:
            result.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            })
    return result


def sync_schema(page: str, body: str) -> str:
    script = re.search(
        r'(<script\s+type="application/ld\+json">)(.*?)(</script>)',
        page,
        flags=re.I | re.S,
    )
    if not script:
        return page
    try:
        data = json.loads(script.group(2))
    except Exception:
        return page

    graph = data.get("@graph") if isinstance(data, dict) else None
    if not isinstance(graph, list):
        return page

    faq = extract_faq(body)
    faq_node = next((node for node in graph if isinstance(node, dict) and node.get("@type") == "FAQPage"), None)
    if faq:
        if faq_node is None:
            graph.append({"@type": "FAQPage", "mainEntity": faq})
        else:
            faq_node["mainEntity"] = faq
    elif faq_node is not None:
        graph.remove(faq_node)

    today = datetime.now(timezone.utc).date().isoformat()
    for node in graph:
        if isinstance(node, dict) and node.get("@type") == "Article":
            node["dateModified"] = today

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return page[:script.start(2)] + payload + page[script.end(2):]


def rewrite_body(title: str, category: str, body: str) -> str:
    prompt = f'''
You are repairing an existing Football Training Lab article that incorrectly drifted into American football.

Article title: {title}
Category: {category}

Return ONLY the corrected HTML fragment for the article-content body.
This website is exclusively about association football (soccer). Every use of "football" must mean association football.

Requirements:
- Remove all American-football equipment, roles and concepts, including helmets, shoulder pads, mouthguards, quarterbacks, linebackers, wide receivers, defensive backs, touchdowns and NFL-style gear.
- Replace them with association-football-specific examples only where relevant: boots/cleats, shin guards, footballs, goalkeeper gloves, kit, cones, training bibs, bags and water bottles.
- Preserve the article's original topic, usefulness and overall HTML structure.
- Preserve key takeaways, table of contents, detailed sections, table if useful, tip box, warning box, exactly 3 FAQ h3 questions and conclusion.
- Correct any claims that only make sense for American football.
- Do not invent prices, studies, statistics, certifications, endorsements, product specifications or personal testing.
- Do not add brand/model names that were not already present.
- Keep medical and injury wording conservative.
- Use only section, nav, div, h2, h3, p, ul, ol, li, strong, em, a, table, thead, tbody, tr, th, td.
- Do not output html, head, body, article, script, style, h1, Markdown or commentary.

CURRENT ARTICLE BODY:
{body}
'''
    response = client.responses.create(model=MODEL, input=prompt)
    return clean_ai_html(response.output_text)


def repair_post(post: Path) -> bool:
    page = post.read_text(encoding="utf-8")
    body = extract_body(page)
    if not has_american_football_markers(body):
        return False

    title = extract_title(page, post)
    category = inferred_category(title, extract_category(page))
    print(f"Association-football repair needed: {post.name}; markers={marker_labels(body)}")

    rewritten = rewrite_body(title, category, body)
    if has_american_football_markers(rewritten):
        rewritten = rewrite_body(title, category, rewritten)
    if has_american_football_markers(rewritten):
        print(f"WARN association-football repair still contains banned markers: {post.name}")
        return False

    updated = replace_body(page, rewritten)
    updated = update_visible_category(updated, category)
    updated = sync_schema(updated, rewritten)
    post.write_text(updated, encoding="utf-8")
    print(f"Association-football repaired: {post.name}")
    return True


def main() -> None:
    repaired = 0
    candidates = []
    for post in sorted(POSTS.glob("*.html")):
        if post.name == "index.html":
            continue
        try:
            if has_american_football_markers(extract_body(post.read_text(encoding="utf-8"))):
                candidates.append(post)
        except Exception as exc:
            print(f"WARN could not inspect {post.name}: {exc}")

    for post in candidates[:MAX_REPAIRS_PER_RUN]:
        try:
            if repair_post(post):
                repaired += 1
        except Exception as exc:
            print(f"WARN association-football repair failed for {post.name}: {exc}")

    print(f"Association-football contaminated articles found: {len(candidates)}")
    print(f"Association-football articles repaired this run: {repaired}")
    if len(candidates) > MAX_REPAIRS_PER_RUN:
        print(f"Association-football repairs deferred to future runs: {len(candidates) - MAX_REPAIRS_PER_RUN}")


if __name__ == "__main__":
    main()
