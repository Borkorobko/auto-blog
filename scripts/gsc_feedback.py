from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


SITE_PROPERTY = os.getenv("GSC_SITE_PROPERTY", "sc-domain:footballtraininglab.com")
SITE_ORIGIN = "https://footballtraininglab.com"
LOOKBACK_DAYS = 28
FINAL_DATA_LAG_DAYS = 3
ROW_LIMIT = 25000

OUTPUT_DIR = Path("seo")
JSON_PATH = OUTPUT_DIR / "gsc_feedback.json"
CSV_PATH = OUTPUT_DIR / "gsc_opportunities.csv"


def env(name: str) -> str:
    return os.getenv(name, "").strip()


def request_json(url: str, *, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> dict:
    body = None
    request_headers = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    token_body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token", "")
    if not token:
        raise RuntimeError("Google OAuth token refresh returned no access_token")
    return token


def fetch_search_analytics(access_token: str) -> tuple[dict, str, str]:
    end_date = date.today() - timedelta(days=FINAL_DATA_LAG_DAYS)
    start_date = end_date - timedelta(days=LOOKBACK_DAYS - 1)

    encoded_site = urllib.parse.quote(SITE_PROPERTY, safe="")
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query"
    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page", "query"],
        "type": "web",
        "dataState": "final",
        "aggregationType": "auto",
        "rowLimit": ROW_LIMIT,
        "startRow": 0,
    }
    result = request_json(
        endpoint,
        method="POST",
        data=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return result, start_date.isoformat(), end_date.isoformat()


def classify_opportunity(impressions: float, ctr: float, position: float) -> str:
    # Conservative thresholds: collect signals first; do not auto-rewrite pages yet.
    if impressions >= 20 and 4 <= position <= 15 and ctr < 0.03:
        return "high_ctr_opportunity"
    if impressions >= 10 and 8 <= position <= 30:
        return "quick_win"
    if impressions >= 5 and 15 <= position <= 50:
        return "rising_visibility"
    return "observe"


def opportunity_score(impressions: float, clicks: float, ctr: float, position: float) -> float:
    if position <= 0:
        return 0.0
    if position <= 3:
        position_factor = 0.25
    elif position <= 10:
        position_factor = 1.5
    elif position <= 20:
        position_factor = 1.25
    elif position <= 40:
        position_factor = 0.8
    else:
        position_factor = 0.25
    ctr_gap = max(0.0, 0.05 - ctr)
    return round(impressions * position_factor * (1.0 + ctr_gap * 10.0) + max(0.0, impressions - clicks), 3)


def local_post_exists(page_url: str) -> bool:
    parsed = urllib.parse.urlparse(page_url)
    if parsed.netloc not in {"footballtraininglab.com", "www.footballtraininglab.com"}:
        return False
    path = parsed.path
    if not path.startswith("/posts/"):
        return False
    filename = path.removeprefix("/posts/").strip("/")
    if not filename:
        return False
    if not filename.endswith(".html"):
        filename += ".html"
    return (Path("posts") / filename).exists()


def build_feedback(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    query_rows: list[dict] = []
    page_totals: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "weighted_position": 0.0})

    for row in rows:
        keys = row.get("keys", [])
        if len(keys) < 2:
            continue
        page, query = keys[0], keys[1]
        impressions = float(row.get("impressions", 0.0) or 0.0)
        clicks = float(row.get("clicks", 0.0) or 0.0)
        ctr = float(row.get("ctr", 0.0) or 0.0)
        position = float(row.get("position", 0.0) or 0.0)
        if impressions <= 0:
            continue

        kind = classify_opportunity(impressions, ctr, position)
        query_rows.append(
            {
                "page": page,
                "query": query,
                "clicks": round(clicks, 3),
                "impressions": round(impressions, 3),
                "ctr": round(ctr, 5),
                "position": round(position, 2),
                "opportunity": kind,
                "score": opportunity_score(impressions, clicks, ctr, position),
                "local_article": local_post_exists(page),
            }
        )

        totals = page_totals[page]
        totals["clicks"] += clicks
        totals["impressions"] += impressions
        totals["weighted_position"] += position * impressions

    query_rows.sort(key=lambda item: (item["score"], item["impressions"]), reverse=True)

    page_rows: list[dict] = []
    for page, totals in page_totals.items():
        impressions = totals["impressions"]
        clicks = totals["clicks"]
        ctr = clicks / impressions if impressions else 0.0
        position = totals["weighted_position"] / impressions if impressions else 0.0
        page_rows.append(
            {
                "page": page,
                "clicks": round(clicks, 3),
                "impressions": round(impressions, 3),
                "ctr": round(ctr, 5),
                "position": round(position, 2),
                "opportunity": classify_opportunity(impressions, ctr, position),
                "score": opportunity_score(impressions, clicks, ctr, position),
                "local_article": local_post_exists(page),
            }
        )
    page_rows.sort(key=lambda item: (item["score"], item["impressions"]), reverse=True)
    return query_rows, page_rows


def write_outputs(raw: dict, query_rows: list[dict], page_rows: list[dict], start_date: str, end_date: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    actionable_queries = [row for row in query_rows if row["opportunity"] != "observe" and row["local_article"]]
    actionable_pages = [row for row in page_rows if row["opportunity"] != "observe" and row["local_article"]]

    document = {
        "site_property": SITE_PROPERTY,
        "site_origin": SITE_ORIGIN,
        "date_range": {"start": start_date, "end": end_date, "days": LOOKBACK_DAYS},
        "source": "Google Search Console Search Analytics API",
        "mode": "read_only_feedback",
        "rows_received": len(raw.get("rows", []) or []),
        "actionable_query_count": len(actionable_queries),
        "actionable_page_count": len(actionable_pages),
        "top_query_opportunities": actionable_queries[:50],
        "top_page_opportunities": actionable_pages[:25],
        "all_page_summaries": page_rows[:250],
    }
    JSON_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fieldnames = ["score", "opportunity", "page", "query", "clicks", "impressions", "ctr", "position", "local_article"]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in actionable_queries[:250]:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    client_id = env("GSC_CLIENT_ID")
    client_secret = env("GSC_CLIENT_SECRET")
    refresh_token = env("GSC_REFRESH_TOKEN")

    missing = [name for name, value in [("GSC_CLIENT_ID", client_id), ("GSC_CLIENT_SECRET", client_secret), ("GSC_REFRESH_TOKEN", refresh_token)] if not value]
    if missing:
        print("Search Console feedback skipped: missing GitHub secret(s): " + ", ".join(missing))
        print("The site build continues normally until one-time OAuth setup is completed.")
        return 0

    try:
        access_token = refresh_access_token(client_id, client_secret, refresh_token)
        raw, start_date, end_date = fetch_search_analytics(access_token)
        rows = raw.get("rows", []) or []
        query_rows, page_rows = build_feedback(rows)
        write_outputs(raw, query_rows, page_rows, start_date, end_date)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        print(f"Search Console feedback failed with HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Search Console feedback failed: {exc}", file=sys.stderr)
        return 1

    actionable_queries = [row for row in query_rows if row["opportunity"] != "observe" and row["local_article"]]
    actionable_pages = [row for row in page_rows if row["opportunity"] != "observe" and row["local_article"]]
    print(f"GSC finalized date range: {start_date} to {end_date}")
    print(f"GSC rows fetched: {len(rows)}")
    print(f"GSC local pages summarized: {sum(1 for row in page_rows if row['local_article'])}")
    print(f"GSC actionable page opportunities: {len(actionable_pages)}")
    print(f"GSC actionable query opportunities: {len(actionable_queries)}")
    for row in actionable_queries[:5]:
        print(
            "GSC opportunity: "
            f"{row['query']} | impressions={row['impressions']} | clicks={row['clicks']} | "
            f"position={row['position']} | {row['opportunity']}"
        )
    print(f"GSC feedback written: {JSON_PATH} and {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
