from __future__ import annotations

import json
import os
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from gsc_feedback import SITE_PROPERTY, refresh_access_token, request_json


HISTORY_PATH = Path("seo/gsc_optimization_history.json")
POST_WINDOW_DAYS = 28
FINAL_DATA_LAG_DAYS = 3
MIN_QUERY_IMPRESSIONS = 10
MIN_PAGE_IMPRESSIONS = 20


def env(name: str) -> str:
    return os.getenv(name, "").strip()


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def write_history(history: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def fetch_metrics(
    access_token: str,
    start_date: date,
    end_date: date,
    page: str,
    query: str | None = None,
) -> dict:
    encoded_site = urllib.parse.quote(SITE_PROPERTY, safe="")
    endpoint = (
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}"
        "/searchAnalytics/query"
    )

    filters = [
        {
            "dimension": "page",
            "operator": "equals",
            "expression": page,
        }
    ]
    if query:
        filters.append(
            {
                "dimension": "query",
                "operator": "equals",
                "expression": query,
            }
        )

    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "type": "web",
        "dataState": "final",
        "aggregationType": "auto",
        "dimensionFilterGroups": [
            {
                "groupType": "and",
                "filters": filters,
            }
        ],
        "rowLimit": 1,
        "startRow": 0,
    }
    result = request_json(
        endpoint,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    rows = result.get("rows", []) or []
    if not rows:
        return {
            "clicks": 0.0,
            "impressions": 0.0,
            "ctr": 0.0,
            "position": 0.0,
        }

    row = rows[0]
    return {
        "clicks": round(float(row.get("clicks", 0.0) or 0.0), 3),
        "impressions": round(float(row.get("impressions", 0.0) or 0.0), 3),
        "ctr": round(float(row.get("ctr", 0.0) or 0.0), 5),
        "position": round(float(row.get("position", 0.0) or 0.0), 2),
    }


def percent_change(after: float, before: float) -> float | None:
    if before <= 0:
        if after <= 0:
            return 0.0
        return None
    return (after - before) / before


def position_delta(before: dict, after: dict) -> float | None:
    before_position = float(before.get("position", 0) or 0)
    after_position = float(after.get("position", 0) or 0)
    if before_position <= 0 or after_position <= 0:
        return None
    # Positive means rankings improved because a smaller Google position is better.
    return round(before_position - after_position, 2)


def classify_result(
    query_before: dict,
    query_after: dict,
    page_before: dict,
    page_after: dict,
) -> tuple[str, int, list[str]]:
    score = 0
    signals: list[str] = []

    query_volume = max(
        float(query_before.get("impressions", 0) or 0),
        float(query_after.get("impressions", 0) or 0),
    )
    page_volume = max(
        float(page_before.get("impressions", 0) or 0),
        float(page_after.get("impressions", 0) or 0),
    )

    if query_volume < MIN_QUERY_IMPRESSIONS and page_volume < MIN_PAGE_IMPRESSIONS:
        return (
            "insufficient_data",
            0,
            ["Not enough impressions for a reliable automated judgment yet."],
        )

    if query_volume >= MIN_QUERY_IMPRESSIONS:
        pos = position_delta(query_before, query_after)
        if pos is not None and pos >= 2:
            score += 2
            signals.append(f"Target-query position improved by {pos:.2f}.")
        elif pos is not None and pos <= -2:
            score -= 2
            signals.append(f"Target-query position worsened by {abs(pos):.2f}.")

        ctr_delta = float(query_after.get("ctr", 0) or 0) - float(
            query_before.get("ctr", 0) or 0
        )
        if ctr_delta >= 0.005:
            score += 1
            signals.append(f"Target-query CTR improved by {ctr_delta * 100:.2f} percentage points.")
        elif ctr_delta <= -0.005:
            score -= 1
            signals.append(f"Target-query CTR fell by {abs(ctr_delta) * 100:.2f} percentage points.")

        imp_change = percent_change(
            float(query_after.get("impressions", 0) or 0),
            float(query_before.get("impressions", 0) or 0),
        )
        if imp_change is not None and imp_change >= 0.25:
            score += 1
            signals.append(f"Target-query impressions grew by {imp_change * 100:.1f}%.")
        elif imp_change is not None and imp_change <= -0.25:
            score -= 1
            signals.append(f"Target-query impressions fell by {abs(imp_change) * 100:.1f}%.")

        click_delta = float(query_after.get("clicks", 0) or 0) - float(
            query_before.get("clicks", 0) or 0
        )
        if click_delta >= 1:
            score += 1
            signals.append(f"Target-query clicks increased by {click_delta:.0f}.")
        elif click_delta <= -1:
            score -= 1
            signals.append(f"Target-query clicks decreased by {abs(click_delta):.0f}.")

    if page_volume >= MIN_PAGE_IMPRESSIONS:
        pos = position_delta(page_before, page_after)
        if pos is not None and pos >= 2:
            score += 1
            signals.append(f"Page-wide average position improved by {pos:.2f}.")
        elif pos is not None and pos <= -2:
            score -= 1
            signals.append(f"Page-wide average position worsened by {abs(pos):.2f}.")

        ctr_delta = float(page_after.get("ctr", 0) or 0) - float(
            page_before.get("ctr", 0) or 0
        )
        if ctr_delta >= 0.003:
            score += 1
            signals.append(f"Page-wide CTR improved by {ctr_delta * 100:.2f} percentage points.")
        elif ctr_delta <= -0.003:
            score -= 1
            signals.append(f"Page-wide CTR fell by {abs(ctr_delta) * 100:.2f} percentage points.")

        imp_change = percent_change(
            float(page_after.get("impressions", 0) or 0),
            float(page_before.get("impressions", 0) or 0),
        )
        if imp_change is not None and imp_change >= 0.25:
            score += 1
            signals.append(f"Page-wide impressions grew by {imp_change * 100:.1f}%.")
        elif imp_change is not None and imp_change <= -0.25:
            score -= 1
            signals.append(f"Page-wide impressions fell by {abs(imp_change) * 100:.1f}%.")

    if not signals:
        signals.append("Metrics moved only slightly; no strong positive or negative signal detected.")

    if score >= 2:
        status = "improved"
    elif score <= -2:
        status = "worse"
    else:
        status = "neutral"
    return status, score, signals


def main() -> int:
    history = load_history()
    if not history:
        print("GSC SEO measurement: no optimization history yet.")
        return 0

    client_id = env("GSC_CLIENT_ID")
    client_secret = env("GSC_CLIENT_SECRET")
    refresh_token = env("GSC_REFRESH_TOKEN")
    missing = [
        name
        for name, value in [
            ("GSC_CLIENT_ID", client_id),
            ("GSC_CLIENT_SECRET", client_secret),
            ("GSC_REFRESH_TOKEN", refresh_token),
        ]
        if not value
    ]
    if missing:
        print("GSC SEO measurement skipped: missing secret(s): " + ", ".join(missing))
        return 0

    access_token = refresh_access_token(client_id, client_secret, refresh_token)
    final_data_through = date.today() - timedelta(days=FINAL_DATA_LAG_DAYS)

    evaluated = 0
    pending = 0
    changed = False

    for item in history:
        if not isinstance(item, dict) or item.get("status") != "applied":
            continue
        if isinstance(item.get("evaluation"), dict) and item["evaluation"].get("status"):
            continue

        page = str(item.get("page", "")).strip()
        query = str(item.get("target_query", "")).strip()
        try:
            optimized_on = date.fromisoformat(str(item.get("date", "")))
        except ValueError:
            continue
        if not page or not query:
            continue

        pre_start = optimized_on - timedelta(days=POST_WINDOW_DAYS)
        pre_end = optimized_on - timedelta(days=1)
        post_start = optimized_on + timedelta(days=1)
        post_end = optimized_on + timedelta(days=POST_WINDOW_DAYS)

        if final_data_through < post_end:
            pending += 1
            continue

        query_before = fetch_metrics(access_token, pre_start, pre_end, page, query)
        query_after = fetch_metrics(access_token, post_start, post_end, page, query)
        page_before = fetch_metrics(access_token, pre_start, pre_end, page)
        page_after = fetch_metrics(access_token, post_start, post_end, page)

        status, score, signals = classify_result(
            query_before,
            query_after,
            page_before,
            page_after,
        )

        item["evaluation"] = {
            "status": status,
            "score": score,
            "evaluated_on": date.today().isoformat(),
            "pre_window": {
                "start": pre_start.isoformat(),
                "end": pre_end.isoformat(),
                "days": POST_WINDOW_DAYS,
            },
            "post_window": {
                "start": post_start.isoformat(),
                "end": post_end.isoformat(),
                "days": POST_WINDOW_DAYS,
            },
            "target_query_before": query_before,
            "target_query_after": query_after,
            "page_before": page_before,
            "page_after": page_after,
            "signals": signals,
        }
        evaluated += 1
        changed = True
        print(
            "GSC SEO measured: "
            f"{page} | query={query} | result={status} | score={score}"
        )
        for signal in signals:
            print(f"  - {signal}")

    if changed:
        write_history(history)

    print(f"GSC SEO measurement evaluated this run: {evaluated}")
    print(f"GSC SEO measurement still waiting for full post window: {pending}")
    print(
        "GSC SEO measurement uses a 28-day before/after window and waits for "
        f"Google's {FINAL_DATA_LAG_DAYS}-day final-data lag."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
