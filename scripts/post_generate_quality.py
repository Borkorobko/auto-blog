from pathlib import Path
import html
import os
import re
import subprocess
from openai import OpenAI

POSTS = Path("posts")
MODEL = "gpt-4.1-mini"
RELATED_LIMIT = 4
BACKLINK_LIMIT = 4

STOP_WORDS = {
    "a", "an", "and", "are", "best", "for", "from", "guide", "how", "in",
    "of", "on", "the", "to", "with", "football", "player", "players",
    "drill", "drills", "complete", "top", "routine",
}

BANNED_PATTERNS = [
    (r"\bprevent(?:s|ed|ing)?\s+(?:an?\s+)?(?:injury|injuries)\b", "injury-prevention claim"),
    (r"\bavoid(?:s|ed|ing)?\s+(?:an?\s+)?(?:injury|injuries)\b", "injury-avoidance guarantee"),
    (r"\bsafe to step on\b", "absolute safety claim"),
    (r"\brisk[- ]free\b", "risk-free claim"),
    (r"\bguarantee(?:s|d|ing)?\b", "guarantee claim"),
    (r"\bwill\s+(?:prevent|eliminate|ensure|guarantee)\b", "absolute outcome claim"),
    (r"\blactic acid\b", "oversimplified lactic-acid claim"),
    (r"\bhelmet(?:s)?\b", "American-football helmet reference"),
    (r"\bshoulder pads?\b", "American-football shoulder-pad reference"),
    (r"\bmouthguards?\b", "American-football mouthguard reference"),
    (r"\bquarterbacks?\b", "American-football position reference"),
    (r"\blinebackers?\b", "American-football position reference"),
    (r"\bwide receivers?\b", "American-football position reference"),
    (r"\bdefensive backs?\b", "American-football position reference"),
    (r"\btouchdowns?\b", "American-football scoring reference"),
    (r"\bNFL\b", "American-football league reference"),
]

EQUIPMENT_PATTERNS = [
    r"\bboot(?:s)?\b", r"\bcleat(?:s)?\b", r"\bshin guards?\b",
    r"\bglove(?:s)?\b", r"\bequipment\b", r"\bwater bottle\b",
    r"\bresistance bands?\b", r"\bgear\b", r"\bcone(?:s)?\b",
    r"\bladder\b", r"\bbackpack\b", r"\bsock(?:s)?\b",
    r"\brebounder\b", r"\bball\b",
]

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def find_new_article() -> Path:
    output = run_git("ls-files", "--others", "--exclude-standard", "posts")
    candidates = [
        Path(line.strip())
        for line in output.splitlines()
        if line.strip().startswith("posts/")
        and line.strip().endswith(".html")
        and not line.strip().endswith("posts/index.html")
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected exactly one newly generated article, found {len(candidates)}: "
            + ", ".join(str(p) for p in candidates)
        )
    return candidates[0]


def extract_article_body(page: str) -> str:
    match = re.search(
        r'(<div class="article-content">)(.*)(</div>\s*</article>)',
        page,
        flags=re.I | re.S,
    )
    if not match:
        raise RuntimeError("Could not locate article-content block in generated page.")
    return match.group(2).strip()


def replace_article_body(page: str, body: str) -> str:
    pattern = re.compile(
        r'(<div class="article-content">)(.*)(</div>\s*</article>)',
        flags=re.I | re.S,
    )
    replaced, count = pattern.subn(
        lambda m: f'{m.group(1)}{body}{m.group(3)}',
        page,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not replace article-content block exactly once.")
    return replaced


def extract_title(page: str, fallback: Path) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.I | re.S)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return fallback.stem.replace("-", " ").title()


def extract_category(page: str) -> str:
    match = re.search(r'<span class="tag">(.*?)</span>', page, flags=re.I | re.S)
    if not match:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1)).strip())


def effective_category(title: str, fallback: str) -> str:
    lower = title.lower()
    if any(re.search(pattern, lower, flags=re.I) for pattern in EQUIPMENT_PATTERNS):
        return "Equipment"
    return fallback


def visible_text(fragment: str) -> str:
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


def quality_issues(body: str, title: str, category: str) -> list[str]:
    issues = []
    text = visible_text(body)
    word_count = len(re.findall(r"\b[\w'-]+\b", text))

    if word_count < 900:
        issues.append(f"article is too short ({word_count} words; minimum 900)")
    if word_count > 2300:
        issues.append(f"article is too long ({word_count} words; maximum 2300)")
    if 'class="key-takeaways"' not in body:
        issues.append("missing key-takeaways section")
    if 'class="table-of-contents"' not in body:
        issues.append("missing table of contents")
    if 'class="faq"' not in body:
        issues.append("missing FAQ section")
    else:
        faq_match = re.search(
            r'<section[^>]*class="[^"]*faq[^"]*"[^>]*>(.*?)</section>',
            body,
            flags=re.I | re.S,
        )
        if not faq_match or len(re.findall(r"<h3\b", faq_match.group(1), flags=re.I)) != 3:
            issues.append("FAQ must contain exactly 3 h3 questions")

    if len(re.findall(r"<h2\b", body, flags=re.I)) < 4:
        issues.append("too few major h2 sections")

    for pattern, label in BANNED_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            issues.append(label)

    buyer_intent = bool(re.search(r"\b(best|top|under|for|with)\b", title, flags=re.I))
    if category.lower() == "equipment" and buyer_intent:
        first_words = " ".join(text.split()[:260]).lower()
        if not re.search(r"\b(choose|look for|pick|option|type|recommend|suit|best)\w*\b", first_words):
            issues.append("equipment buyer intent is not answered early enough")
        if "<table" not in body.lower():
            issues.append("strong equipment buyer-intent article should include a comparison table")

    return issues


def editorial_pass(body: str, title: str, category: str, issues: list[str] | None = None) -> str:
    issue_text = "\n".join(f"- {item}" for item in (issues or [])) or "- No deterministic failures were found; still perform a careful factual and editorial review."
    prompt = f'''
You are the final editorial quality gate for Football Training Lab.

Article title: {title}
Category: {category}

Review the draft below and return ONLY the corrected HTML fragment for the article content.
Do not include html, head, body, article, script, style, h1, Markdown fences, or commentary.

Known checks/issues:
{issue_text}

Mandatory editorial rules:
- This site is exclusively about association football (soccer), never American football. Interpret every use of "football" as association football. Remove or replace American-football equipment, positions and concepts such as helmets, shoulder pads, mouthguards, quarterbacks, linebackers, wide receivers, defensive backs, touchdowns and NFL-style gear. Use association-football terminology and equipment instead.
- Preserve the article's useful structure: key takeaways, table of contents, detailed h2 sections, practical details, a tip box, a warning box, exactly 3 FAQ h3 questions, and a concise conclusion.
- Correct factual overstatements and unsupported certainty.
- Never claim that equipment, a drill, a supplement, stretching, recovery work, or an exercise prevents or guarantees avoidance of injury.
- Avoid absolute safety wording such as "safe to step on"; use qualified wording such as lower-profile or more forgiving where justified.
- Do not use simplistic "lactic acid removal" explanations for recovery.
- Do not invent studies, statistics, certifications, prices, stock, release status, specifications, endorsements, or personal testing.
- Do not introduce any brand or product model name that is not already present in the draft.
- If brand/model names already appear, do not add unsupported specifications or claims about them.
- For equipment topics with buying intent, give a useful practical answer near the beginning and explain selection criteria and trade-offs instead of drifting into a generic guide.
- Keep advice appropriate for amateur and developing football players.
- Keep medical language conservative; sharp, persistent, or worsening pain is a reason to stop or reduce activity and seek qualified advice when appropriate.
- Keep links and anchor IDs valid. Use only these elements: section, nav, div, h2, h3, p, ul, ol, li, strong, em, a, table, thead, tbody, tr, th, td.
- Aim for roughly 1200-1700 useful words; do not pad with repetition.
- If the draft is already good, make only necessary edits.

DRAFT:
{body}
'''
    response = client.responses.create(model=MODEL, input=prompt)
    return clean_ai_html(response.output_text)


def topic_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 2
    }


def post_title(post: Path) -> str:
    try:
        page = post.read_text(encoding="utf-8")
        return extract_title(page, post)
    except Exception:
        return post.stem.replace("-", " ").title()


def post_category(post: Path) -> str:
    try:
        page = post.read_text(encoding="utf-8")
        return effective_category(extract_title(page, post), extract_category(page))
    except Exception:
        return ""


def relevance_score(source: Path, candidate: Path) -> int:
    source_tokens = topic_tokens(source.stem.replace("-", " "))
    candidate_tokens = topic_tokens(candidate.stem.replace("-", " "))
    overlap = len(source_tokens & candidate_tokens)
    if overlap <= 0:
        return 0
    same_category = bool(post_category(source)) and post_category(source) == post_category(candidate)
    score = overlap * 10
    if same_category:
        score += 3
    return score


def ranked_related(source: Path, all_posts: list[Path], limit: int = RELATED_LIMIT) -> list[Path]:
    ranked = []
    for candidate in all_posts:
        if candidate == source:
            continue
        score = relevance_score(source, candidate)
        if score <= 0:
            continue
        ranked.append((score, candidate.name, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def related_block(posts: list[Path]) -> str:
    if not posts:
        return ""
    cards = []
    for post in posts:
        cards.append(
            f'<a class="related-card" href="{html.escape(post.name)}">'
            f'<strong>{html.escape(post_title(post))}</strong>'
            f'<span>Read guide →</span></a>'
        )
    return (
        '\n<!-- RELATED-START -->\n'
        '<section class="related-articles">\n'
        '  <p class="eyebrow">Continue learning</p>\n'
        '  <h2>Related football guides</h2>\n'
        '  <div class="related-grid">\n'
        f'    {"".join(cards)}\n'
        '  </div>\n'
        '</section>\n'
        '<!-- RELATED-END -->\n'
    )


def set_related(post: Path, related: list[Path]) -> bool:
    page = post.read_text(encoding="utf-8")
    pattern = re.compile(r"\s*<!-- RELATED-START -->.*?<!-- RELATED-END -->\s*", flags=re.S)
    clean_page = pattern.sub("\n", page)
    block = related_block(related)
    if not block or "</article>" not in clean_page:
        return False
    new_page = clean_page.replace("</article>", f"{block}</article>", 1)
    if new_page != page:
        post.write_text(new_page, encoding="utf-8")
        return True
    return False


def revert_mass_related_changes(new_article: Path) -> list[Path]:
    changed = run_git("diff", "--name-only", "--", "posts").splitlines()
    reverted = []
    for raw in changed:
        raw = raw.strip()
        if not raw or raw == "posts/index.html" or raw == str(new_article):
            continue
        path = Path(raw)
        if path.suffix.lower() == ".html" and path.parent == POSTS:
            run_git("checkout", "--", raw)
            reverted.append(path)
    return reverted


def optimize_related_links(new_article: Path) -> tuple[int, int]:
    reverted = revert_mass_related_changes(new_article)
    all_posts = sorted([p for p in POSTS.glob("*.html") if p.name != "index.html"])

    new_related = ranked_related(new_article, all_posts, RELATED_LIMIT)
    touched = 1 if set_related(new_article, new_related) else 0

    backlink_candidates = []
    for candidate in all_posts:
        if candidate == new_article:
            continue
        score = relevance_score(candidate, new_article)
        if score > 0:
            backlink_candidates.append((score, candidate.name, candidate))
    backlink_candidates.sort(key=lambda item: (-item[0], item[1]))

    for _, _, candidate in backlink_candidates[:BACKLINK_LIMIT]:
        others = [p for p in ranked_related(candidate, all_posts, RELATED_LIMIT) if p != new_article]
        chosen = [new_article] + others[: max(0, RELATED_LIMIT - 1)]
        if set_related(candidate, chosen):
            touched += 1

    return len(reverted), touched


def main() -> None:
    new_article = find_new_article()
    page = new_article.read_text(encoding="utf-8")
    title = extract_title(page, new_article)
    category = effective_category(title, extract_category(page))
    body = extract_article_body(page)

    initial_issues = quality_issues(body, title, category)
    reviewed_body = editorial_pass(body, title, category, initial_issues)
    reviewed_issues = quality_issues(reviewed_body, title, category)

    if reviewed_issues:
        reviewed_body = editorial_pass(reviewed_body, title, category, reviewed_issues)
        reviewed_issues = quality_issues(reviewed_body, title, category)

    if reviewed_issues:
        raise RuntimeError("Quality gate failed after repair: " + "; ".join(reviewed_issues))

    new_article.write_text(replace_article_body(page, reviewed_body), encoding="utf-8")
    reverted_count, related_touched = optimize_related_links(new_article)

    final_body = extract_article_body(new_article.read_text(encoding="utf-8"))
    final_issues = quality_issues(final_body, title, category)
    if final_issues:
        raise RuntimeError("Final quality gate failed: " + "; ".join(final_issues))

    print(f"Quality gate passed: {new_article}")
    print(f"Initial quality issues detected: {len(initial_issues)}")
    print(f"Mass related-link rewrites reverted: {reverted_count}")
    print(f"Articles intentionally updated for related links: {related_touched}")


if __name__ == "__main__":
    main()
