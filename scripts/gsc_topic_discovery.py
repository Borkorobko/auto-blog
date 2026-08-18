from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


FEEDBACK_PATH = Path("seo/gsc_feedback.json")
HISTORY_PATH = Path("seo/gsc_topic_history.json")
KEYWORDS_PATH = Path("keywords.txt")
POSTS_DIR = Path("posts")

MIN_IMPRESSIONS = 6.0
MIN_POSITION = 8.0
MAX_POSITION = 50.0
MAX_TOPICS_PER_RUN = 1
MAX_HISTORY = 300

STOP_WORDS = {
    "a", "an", "and", "are", "best", "for", "from", "guide", "how", "in",
    "is", "of", "on", "the", "to", "with", "football", "footballer",
    "footballers", "player", "players", "soccer",
}

BANNED_PATTERNS = [
    r"\bamerican football\b", r"\bnfl\b", r"\bquarterbacks?\b",
    r"\blinebackers?\b", r"\bwide receivers?\b", r"\bdefensive backs?\b",
    r"\btouchdowns?\b", r"\bhelmet(?:s)?\b", r"\bshoulder pads?\b",
    r"\bnews\b", r"\btransfers?\b", r"\bfixtures?\b", r"\bresults?\b",
    r"\bscores?\b", r"\blive\b", r"\b202[0-9]\b",
    r"\binjur(?:y|ies)\b", r"\brehab(?:ilitation)?\b", r"\btreat(?:ment|ing)?\b",
    r"\bdiagnos(?:is|e|ed)\b", r"\bpain\b", r"\bsprain(?:s|ed)?\b",
    r"\bnike\b", r"\badidas\b", r"\bpuma\b", r"\bnew balance\b",
]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_topic(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("soccer", "football")
    text = re.sub(r"[^a-z0-9' -]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def normalize_token(token: str) -> str:
    token = token.lower()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def topic_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        token = normalize_token(token)
        if len(token) > 2 and token not in STOP_WORDS:
            tokens.add(token)
    return tokens


def too_similar(candidate: str, existing: list[str]) -> bool:
    candidate_slug = slugify(candidate)
    c_tokens = topic_tokens(candidate)
    if not candidate_slug or len(c_tokens) < 2:
        return True

    for item in existing:
        if slugify(item) == candidate_slug:
            return True
        i_tokens = topic_tokens(item)
        if not i_tokens:
            continue
        union = c_tokens | i_tokens
        if not union:
            continue
        jaccard = len(c_tokens & i_tokens) / len(union)
        if jaccard >= 0.60:
            return True
        if c_tokens.issubset(i_tokens) or i_tokens.issubset(c_tokens):
            if len(c_tokens & i_tokens) >= 2:
                return True
    return False


def valid_topic(topic: str) -> bool:
    words = re.findall(r"[a-z0-9'-]+", topic.lower())
    if len(words) < 4 or len(words) > 10:
        return False
    if "football" not in words and "footballers" not in words:
        return False
    if any(re.search(pattern, topic, flags=re.I) for pattern in BANNED_PATTERNS):
        return False
    if len(topic_tokens(topic)) < 2:
        return False
    if topic.startswith(("is it ", "what is the best way to ")):
        return False
    return True


def published_topics() -> list[str]:
    topics: list[str] = []
    if not POSTS_DIR.exists():
        return topics
    for post in POSTS_DIR.glob("*.html"):
        if post.name == "index.html":
            continue
        text = post.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I | re.S)
        if match:
            title = re.sub(r"<[^>]+>", " ", match.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                topics.append(title)
                continue
        topics.append(post.stem.replace("-", " "))
    return topics


def load_queue() -> list[str]:
    if not KEYWORDS_PATH.exists():
        return []
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in KEYWORDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("entries", [])
    return payload if isinstance(payload, list) else []


def candidate_score(row: dict) -> float:
    impressions = float(row.get("impressions", 0.0) or 0.0)
    position = float(row.get("position", 0.0) or 0.0)
    ctr = float(row.get("ctr", 0.0) or 0.0)
    if position <= 0:
        return 0.0
    position_factor = 1.4 if position <= 30 else 1.0
    low_ctr_bonus = 1.15 if ctr < 0.03 else 1.0
    return impressions * position_factor * low_ctr_bonus


def main() -> int:
    if not FEEDBACK_PATH.exists():
        print("GSC topic discovery skipped: seo/gsc_feedback.json not found.")
        return 0

    try:
        feedback = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"GSC topic discovery skipped: invalid feedback JSON: {exc}")
        return 0

    rows = feedback.get("all_query_summaries") or feedback.get("top_query_opportunities") or []
    if not isinstance(rows, list):
        rows = []

    queue = load_queue()
    published = published_topics()
    existing = published + queue
    history = load_history()
    historical_queries = {
        normalize_topic(str(item.get("source_query", "")))
        for item in history
        if isinstance(item, dict) and item.get("source_query")
    }

    eligible: list[tuple[float, dict, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        query = normalize_topic(str(row.get("query", "")))
        impressions = float(row.get("impressions", 0.0) or 0.0)
        position = float(row.get("position", 0.0) or 0.0)

        if impressions < MIN_IMPRESSIONS:
            continue
        if not (MIN_POSITION <= position <= MAX_POSITION):
            continue
        if query in historical_queries:
            continue
        if not valid_topic(query):
            continue
        if too_similar(query, existing):
            continue

        eligible.append((candidate_score(row), row, query))

    eligible.sort(
        key=lambda item: (
            item[0],
            float(item[1].get("impressions", 0.0) or 0.0),
            -float(item[1].get("position", 999.0) or 999.0),
        ),
        reverse=True,
    )

    if not eligible:
        print("GSC topic discovery: no sufficiently distinct new topic found this run.")
        print(f"GSC topic discovery thresholds: impressions>={MIN_IMPRESSIONS}, position={MIN_POSITION}-{MAX_POSITION}.")
        return 0

    added: list[str] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for score, row, topic in eligible:
        if len(added) >= MAX_TOPICS_PER_RUN:
            break

        queue = [item for item in queue if slugify(item) != slugify(topic)]
        queue.insert(0, topic)
        existing.insert(0, topic)
        added.append(topic)

        history.append(
            {
                "queued_at": now,
                "topic": topic,
                "source_query": normalize_topic(str(row.get("query", ""))),
                "source_page": str(row.get("page", "")),
                "impressions": float(row.get("impressions", 0.0) or 0.0),
                "clicks": float(row.get("clicks", 0.0) or 0.0),
                "ctr": float(row.get("ctr", 0.0) or 0.0),
                "position": float(row.get("position", 0.0) or 0.0),
                "discovery_score": round(score, 3),
                "status": "queued",
            }
        )

    KEYWORDS_PATH.write_text("\n".join(queue) + ("\n" if queue else ""), encoding="utf-8")
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps({"entries": history[-MAX_HISTORY:]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    for topic in added:
        row = next(item[1] for item in eligible if item[2] == topic)
        print(
            "GSC-derived topic queued for the next article run: "
            f"{topic} | impressions={row.get('impressions', 0)} | "
            f"position={row.get('position', 0)}"
        )
    print(f"GSC-derived topics added this run: {len(added)}")
    print("GSC topic priority: inserted at the top of keywords.txt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
