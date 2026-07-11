from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from .config import ROOT, SiteConfig
from .models import PlanItem, SyncResult


def report_path(site: SiteConfig, command: str) -> Path:
    directory = ROOT / "reports" / site.key
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"{stamp}-{command}.json"


def write_report(site: SiteConfig, command: str, payload: Any) -> Path:
    path = report_path(site, command)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def result_dict(result: SyncResult) -> dict[str, Any]:
    return {
        "key": result.key,
        "action": result.action,
        "ok": result.ok,
        "message": result.message,
        "wp_id": result.wp_id,
        "url": result.url,
    }


def plan_dict(item: PlanItem) -> dict[str, Any]:
    return {
        "key": item.document.key,
        "action": item.action,
        "reason": item.reason,
        "wp_id": item.remote.get("id") if item.remote else None,
        "url": item.remote.get("link") if item.remote else None,
    }


def notify_slack(site: SiteConfig, command: str, rows: list[dict[str, Any]], report: Path) -> None:
    if not site.slack_webhook_url:
        return
    counts: dict[str, int] = {}
    failed = 0
    for row in rows:
        action = str(row.get("action", "unknown"))
        counts[action] = counts.get(action, 0) + 1
        if row.get("ok") is False:
            failed += 1
    count_text = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "no content"
    text = f"WordPress Factory · {site.key} · {command}: {count_text}; failures={failed}; report={report.name}"
    try:
        response = requests.post(site.slack_webhook_url, json={"text": text}, timeout=site.timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARNING Slack notification failed: {exc}")

