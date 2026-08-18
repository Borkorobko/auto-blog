from __future__ import annotations

import html
import json
import re
from pathlib import Path


HISTORY_PATH = Path("seo/gsc_optimization_history.json")
POSTS = Path("posts")

UEFA_NUTRITION_URL = "https://www.uefa.com/news-media/news/0262-10b3a43fd486-f4484edc6615-1000--uefa-launches-expert-group-statement-on-nutrition-for-elit/"
IOC_SUPPLEMENTS_URL = "https://bjsm.bmj.com/content/52/7/439"
WHO_ACTIVITY_URL = "https://www.who.int/publications/i/item/9789240015128"
NHS_DEHYDRATION_URL = "https://www.nhs.uk/conditions/dehydration/"

APPROVED_SOURCE_URLS = {
    UEFA_NUTRITION_URL: "UEFA nutrition statement",
    IOC_SUPPLEMENTS_URL: "IOC supplement consensus",
    WHO_ACTIVITY_URL: "WHO physical activity guidelines",
    NHS_DEHYDRATION_URL: "NHS dehydration guidance",
}

# These phrases imply authority or evidence the site may not actually document.
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

BLOCK_RE = re.compile(r"<(?P<tag>p|li|td)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>", re.I | re.S)
SOURCE_LINK_RE = re.compile(
    r'<a\b(?=[^>]*\bclass=["\'][^"\']*\bsource-link\b[^"\']*["\'])(?=[^>]*\bhref=["\'](?P<href>[^"\']+)["\'])[^>]*>(?P<label>.*?)</a>',
    re.I | re.S,
)
TIMEFRAME_RE = re.compile(
    r"\b(?:within|in|after|over)\s+(?:about\s+|roughly\s+)?\d+(?:\s*(?:-|–|to)\s*\d+)?\s*(?:days?|weeks?|months?)\b",
    re.I,
)
DOSE_RE = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*(?:-|–|to)\s*\d+(?:\.\d+)?)?\s*(?:g(?:/kg)?|grams?|mg(?:/kg)?|milligrams?|ml|millilit(?:er|re)s?|lit(?:er|re)s?|cups?|glasses?)\b",
    re.I,
)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%\b")
OUTCOME_WORDS_RE = re.compile(r"\b(?:improv\w*|adapt\w*|recover\w*|recovery|result\w*|benefit\w*|performance|injur\w*)\b", re.I)
NUTRITION_WORDS_RE = re.compile(r"\b(?:protein|carbohydrate|carbs?|nutrition|creatine|caffeine|supplement\w*|hydration|fluid\w*|water|sodium|electrolyte\w*)\b", re.I)
PERFORMANCE_WORDS_RE = re.compile(r"\b(?:performance|speed|strength|power|recovery|injur\w*|stamina|endurance)\b", re.I)


def citation(url: str) -> str:
    label = APPROVED_SOURCE_URLS[url]
    return (
        f' <a class="source-link" href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">Source: {html.escape(label)}</a>'
    )


def plain_text(fragment: str) -> str:
    fragment = SOURCE_LINK_RE.sub("", fragment)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def sanitize_text(value: str) -> tuple[str, int]:
    changed = value
    replacements = 0
    for pattern, replacement in REPLACEMENTS:
        changed, count = re.subn(pattern, replacement, changed, flags=re.I)
        replacements += count
    return changed, replacements


def sanitize_source_links(page: str) -> tuple[str, int]:
    removed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        href = html.unescape(match.group("href")).strip()
        if href in APPROVED_SOURCE_URLS:
            return match.group(0)
        removed += 1
        return html.escape(plain_text(match.group("label")))

    return SOURCE_LINK_RE.sub(replace, page), removed


def risky_kind(text: str) -> str | None:
    lower = text.lower()
    if TIMEFRAME_RE.search(text) and OUTCOME_WORDS_RE.search(text):
        return "timeline"
    if DOSE_RE.search(text) and NUTRITION_WORDS_RE.search(text):
        if any(word in lower for word in ("supplement", "creatine", "caffeine")):
            return "supplement"
        if any(word in lower for word in ("hydration", "fluid", "water", "sodium", "electrolyte")):
            return "hydration"
        return "nutrition"
    if PERCENT_RE.search(text) and PERFORMANCE_WORDS_RE.search(text):
        return "performance"
    return None


def softened_block(kind: str) -> str:
    if kind == "supplement":
        return (
            "Supplement decisions should be individualized. Evidence, safety, eligibility and contamination risk all matter, "
            "so fixed doses or guaranteed effects should not be presented without direct supporting evidence."
            + citation(IOC_SUPPLEMENTS_URL)
        )
    if kind == "hydration":
        return (
            "Fluid needs vary with the player, environment, sweat losses and session demands, so a single universal intake "
            "amount should not be presented without direct supporting evidence."
            + citation(UEFA_NUTRITION_URL)
        )
    if kind == "nutrition":
        return (
            "Football nutrition needs vary with body size, training load, match demands and individual circumstances, so a "
            "single intake target should not be presented as universal without direct supporting evidence."
            + citation(UEFA_NUTRITION_URL)
        )
    if kind == "timeline":
        return (
            "Training, recovery and adaptation timelines vary between players and depend on training quality, consistency, "
            "recovery and individual circumstances; a fixed timetable should not be presented as guaranteed."
        )
    return (
        "Training responses vary between players, so a fixed percentage improvement or guaranteed performance effect should "
        "not be presented without direct supporting evidence."
    )


def soften_risky_quantified_claims(page: str) -> tuple[str, int]:
    softened = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal softened
        text = plain_text(match.group("body"))
        kind = risky_kind(text)
        if not kind:
            return match.group(0)
        softened += 1
        return f'<{match.group("tag")}{match.group("attrs")}>{softened_block(kind)}</{match.group("tag")}>'

    return BLOCK_RE.sub(replace, page), softened


def add_supported_citations(page: str) -> tuple[str, int]:
    added = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal added
        body = match.group("body")
        text = plain_text(body).lower()
        url = None

        if re.search(r"\b(?:food[- ]first|food over supplements?)\b", text):
            url = UEFA_NUTRITION_URL
        elif "supplement" in text and re.search(r"\b(?:doping|contaminat\w*|risk|evidence|vary|individual)\b", text):
            url = IOC_SUPPLEMENTS_URL
        elif "dehydrat" in text and re.search(r"\b(?:thirst|dark yellow|dizz\w*|lightheaded|sweat\w*|exercise)\b", text):
            url = NHS_DEHYDRATION_URL
        elif "physical activity" in text and "health benefit" in text:
            url = WHO_ACTIVITY_URL

        if not url or url in body:
            return match.group(0)

        added += 1
        return f'<{match.group("tag")}{match.group("attrs")}>{body}{citation(url)}</{match.group("tag")}>'

    return BLOCK_RE.sub(replace, page), added


def extract_visible_faq(page: str) -> list[tuple[str, str]]:
    section = re.search(r'<section[^>]*class=["\'][^"\']*\bfaq\b[^"\']*["\'][^>]*>(.*?)</section>', page, re.I | re.S)
    if not section:
        return []
    pairs = re.findall(r"<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>", section.group(1), re.I | re.S)
    return [(plain_text(q), plain_text(a)) for q, a in pairs if plain_text(q) and plain_text(a)]


def sync_faq_schema(page: str) -> tuple[str, int]:
    faq_pairs = extract_visible_faq(page)
    if not faq_pairs:
        return page, 0

    script_re = re.compile(r'(<script\s+type=["\']application/ld\+json["\']>)(.*?)(</script>)', re.I | re.S)
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        try:
            data = json.loads(match.group(2))
        except json.JSONDecodeError:
            return match.group(0)

        graph = data.get("@graph") if isinstance(data, dict) else None
        if not isinstance(graph, list):
            return match.group(0)

        for item in graph:
            if isinstance(item, dict) and item.get("@type") == "FAQPage":
                item["mainEntity"] = [
                    {
                        "@type": "Question",
                        "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": answer},
                    }
                    for question, answer in faq_pairs[:5]
                ]
                changed = 1
                return match.group(1) + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + match.group(3)
        return match.group(0)

    updated = script_re.sub(replace, page, count=1)
    return updated, changed


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def sanitize_history(history: list[dict]) -> int:
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
        HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return replacements


def all_article_files() -> list[Path]:
    return sorted(path for path in POSTS.glob("*.html") if path.name != "index.html")


def main() -> int:
    history = load_history()
    files = all_article_files()
    files_changed = 0
    authority_replacements = 0
    bad_source_links_removed = 0
    risky_claims_softened = 0
    supported_citations_added = 0
    faq_schemas_synced = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        updated, authority_count = sanitize_text(original)
        updated, source_count = sanitize_source_links(updated)
        updated, softened_count = soften_risky_quantified_claims(updated)
        updated, citation_count = add_supported_citations(updated)
        updated, faq_count = sync_faq_schema(updated)

        authority_replacements += authority_count
        bad_source_links_removed += source_count
        risky_claims_softened += softened_count
        supported_citations_added += citation_count
        faq_schemas_synced += faq_count

        if updated != original:
            path.write_text(updated, encoding="utf-8")
            files_changed += 1
            print(
                f"Evidence guardrail updated: {path} | authority={authority_count} | "
                f"softened={softened_count} | citations={citation_count} | bad_sources={source_count}"
            )

    history_replacements = sanitize_history(history)
    authority_replacements += history_replacements

    print(
        "Evidence guardrail complete: "
        f"files_scanned={len(files)}, files_changed={files_changed}, "
        f"authority_replacements={authority_replacements}, risky_claims_softened={risky_claims_softened}, "
        f"supported_citations_added={supported_citations_added}, bad_source_links_removed={bad_source_links_removed}, "
        f"faq_schemas_synced={faq_schemas_synced}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
