from pathlib import Path
import json
import os
import re

from openai import OpenAI

KEYWORDS_FILE = Path("keywords.txt")
POSTS = Path("posts")
MIN_QUEUE = 8
TARGET_QUEUE = 24
MODEL = "gpt-4.1-mini"

STOP_WORDS = {
    "a", "an", "and", "best", "for", "from", "guide", "how", "in", "of",
    "on", "the", "to", "with", "football", "soccer", "player", "players",
}

BANNED_PATTERNS = [
    r"\bamerican football\b", r"\bnfl\b", r"\bquarterbacks?\b",
    r"\blinebackers?\b", r"\bwide receivers?\b", r"\bdefensive backs?\b",
    r"\btouchdowns?\b", r"\bhelmet(?:s)?\b", r"\bshoulder pads?\b",
    r"\blive scores?\b", r"\bnews\b", r"\btransfer(?:s)?\b",
    r"\bresults?\b", r"\bfixtures?\b", r"\b202[0-9]\b",
]

FALLBACK_TOPICS = [
    "football acceleration drills for beginners",
    "football deceleration training drills",
    "change of direction drills for football",
    "football reaction speed drills",
    "football sprint workout for beginners",
    "football interval training workout",
    "football aerobic conditioning workout",
    "football anaerobic conditioning drills",
    "football agility workout at home",
    "football balance exercises for players",
    "single leg strength exercises for football",
    "football hamstring strengthening exercises",
    "football calf strengthening exercises",
    "football hip mobility routine",
    "football ankle mobility exercises",
    "football recovery day routine",
    "football cooldown routine after training",
    "football hydration guide for training",
    "pre match meal ideas for football players",
    "football training snack ideas",
    "football dribbling drills for beginners",
    "football first touch drills at home",
    "football passing drills for beginners",
    "football shooting drills for beginners",
    "football ball control drills at home",
    "football weak foot training drills",
    "football training plan for goalkeepers",
    "football fitness plan for beginners",
    "football strength workout at home",
    "football core stability exercises",
    "football resistance band workout",
    "football plyometric exercises for beginners",
    "football warm up for speed training",
    "football warm up for gym training",
    "football stretching after training",
    "football recovery nutrition after training",
    "football training bag essentials",
    "how to choose shin guards for football",
    "how to choose goalkeeper gloves",
    "best football equipment for beginners",
    "football training equipment for home",
    "football cones drills for beginners",
    "football agility ladder drills for beginners",
    "football rebounder drills for beginners",
    "football boots for hard ground",
    "football boots for soft ground",
    "football boots for grass pitches",
    "football boots for beginner players",
]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def topic_tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def too_similar(candidate: str, existing: list[str]) -> bool:
    c_tokens = topic_tokens(candidate)
    if not c_tokens:
        return True
    for item in existing:
        i_tokens = topic_tokens(item)
        if not i_tokens:
            continue
        union = c_tokens | i_tokens
        if not union:
            continue
        jaccard = len(c_tokens & i_tokens) / len(union)
        if jaccard >= 0.82:
            return True
    return False


def valid_topic(topic: str) -> bool:
    topic = re.sub(r"\s+", " ", topic).strip(" -–—.,:;\t\n")
    words = re.findall(r"[A-Za-z0-9'-]+", topic)
    if len(words) < 4 or len(words) > 10:
        return False
    lowered = topic.lower()
    if any(re.search(pattern, lowered, flags=re.I) for pattern in BANNED_PATTERNS):
        return False
    if "football" not in lowered and "footballers" not in lowered:
        return False
    return True


def published_topics() -> list[str]:
    topics = []
    if not POSTS.exists():
        return topics
    for post in POSTS.glob("*.html"):
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


def ai_candidates(existing: list[str], needed: int) -> list[str]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sample = existing[-100:]
    prompt = f'''
Generate 36 evergreen English SEO article topics for a website called Football Training Lab.
The website is ONLY about association football (soccer), never American football.
Audience: amateur, beginner and developing football players.

Priorities:
- practical training, speed, stamina, strength, recovery, skills and useful equipment buying intent
- search phrases that a real player might type into Google
- mostly long-tail topics with clear intent
- topics that can remain useful for years
- include a healthy mix of training, fitness, strength, recovery, skills and equipment

Do NOT include:
- news, transfers, scores, fixtures, clubs, players, tournaments or current events
- years or dates
- American-football positions/equipment
- medical diagnosis or injury-treatment topics
- brand/model names
- topics that duplicate or closely paraphrase anything in the existing list

Each topic must be 4 to 10 words and must contain the word "football" or "footballers".
Return ONLY a valid JSON array of strings, no Markdown and no explanation.

Existing/pending topics to avoid:
{json.dumps(sample, ensure_ascii=False)}
'''
    response = client.responses.create(model=MODEL, input=prompt)
    raw = response.output_text.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, flags=re.S)
        if not match:
            print("WARN keyword replenisher could not parse AI output; using fallbacks.")
            return []
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if isinstance(item, str)]


def main() -> None:
    if not KEYWORDS_FILE.exists():
        KEYWORDS_FILE.write_text("", encoding="utf-8")

    queue = [
        re.sub(r"\s+", " ", line).strip()
        for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"Keyword queue before replenishment: {len(queue)}")

    if len(queue) >= MIN_QUEUE:
        print("Keyword replenishment not needed.")
        print(f"Keyword queue after replenishment: {len(queue)}")
        return

    published = published_topics()
    existing = published + queue
    existing_slugs = {slugify(item) for item in existing if slugify(item)}
    needed = max(0, TARGET_QUEUE - len(queue))

    candidates = []
    try:
        candidates.extend(ai_candidates(existing, needed))
    except Exception as exc:
        print(f"WARN AI keyword replenishment failed: {exc}")

    candidates.extend(FALLBACK_TOPICS)

    added = []
    comparison_pool = list(existing)
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        candidate_slug = slugify(candidate)
        if len(added) >= needed:
            break
        if not candidate_slug or candidate_slug in existing_slugs:
            continue
        if not valid_topic(candidate):
            continue
        if too_similar(candidate, comparison_pool):
            continue
        added.append(candidate.lower())
        comparison_pool.append(candidate)
        existing_slugs.add(candidate_slug)

    if added:
        new_queue = queue + added
        KEYWORDS_FILE.write_text("\n".join(new_queue) + "\n", encoding="utf-8")
    else:
        new_queue = queue

    print(f"New evergreen keyword topics added: {len(added)}")
    print(f"Keyword queue after replenishment: {len(new_queue)}")
    if len(new_queue) < MIN_QUEUE:
        raise RuntimeError(
            f"Keyword queue is still too small ({len(new_queue)}). Replenishment could not create enough safe topics."
        )


if __name__ == "__main__":
    main()
