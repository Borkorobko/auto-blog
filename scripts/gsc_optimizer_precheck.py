from __future__ import annotations

import json
from pathlib import Path


FEEDBACK_PATH = Path("seo/gsc_feedback.json")
HISTORY_PATH = Path("seo/gsc_optimization_history.json")
BLOCKED_STATUSES = {"worse", "insufficient_data"}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def latest_evaluations(history: list[dict]) -> dict[str, str]:
    latest: dict[str, tuple[str, str]] = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        page = str(item.get("page", "")).strip()
        evaluation = item.get("evaluation")
        if not page or not isinstance(evaluation, dict):
            continue
        status = str(evaluation.get("status", "")).strip()
        evaluated_on = str(evaluation.get("evaluated_on", "")).strip()
        if not status:
            continue
        current = latest.get(page)
        if current is None or evaluated_on >= current[0]:
            latest[page] = (evaluated_on, status)
    return {page: status for page, (_, status) in latest.items()}


def main() -> int:
    feedback = load_json(FEEDBACK_PATH, {})
    history = load_json(HISTORY_PATH, [])
    if not isinstance(feedback, dict) or not isinstance(history, list):
        print("GSC optimizer precheck: nothing to filter.")
        return 0

    latest = latest_evaluations(history)
    blocked_pages = {
        page: status for page, status in latest.items() if status in BLOCKED_STATUSES
    }
    if not blocked_pages:
        print("GSC optimizer precheck: no pages blocked by prior measured outcomes.")
        return 0

    changed = False
    for key in ("top_query_opportunities", "top_page_opportunities"):
        rows = feedback.get(key)
        if not isinstance(rows, list):
            continue
        kept = [
            row
            for row in rows
            if not isinstance(row, dict) or str(row.get("page", "")) not in blocked_pages
        ]
        if len(kept) != len(rows):
            feedback[key] = kept
            changed = True

    if changed:
        FEEDBACK_PATH.write_text(
            json.dumps(feedback, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    for page, status in sorted(blocked_pages.items()):
        print(f"GSC optimizer precheck blocked: {page} | prior_result={status}")
    print(
        "GSC optimizer precheck: pages measured as worse or insufficient_data are "
        "not eligible for another automatic rewrite."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
