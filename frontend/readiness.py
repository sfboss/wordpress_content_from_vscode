"""
Site readiness assessment for the web UI.

Aggregates volume baselines, content gaps, featured images, and publish-readiness
into a prioritized TODO queue with green / yellow / red severity and fix actions.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wp_factory.config import load_site  # noqa: E402
from wp_factory.seo_tools import run_publish_readiness  # noqa: E402
from wp_factory.tools import load_tool_documents, run_site_dashboard  # noqa: E402


def _tone(actual: float, target: float) -> str:
    if target <= 0:
        return "green"
    ratio = actual / target
    if ratio >= 1.0:
        return "green"
    if ratio >= 0.6:
        return "yellow"
    return "red"


def _pct(actual: float, target: float) -> int:
    if target <= 0:
        return 100
    return min(100, int(round(100 * actual / target)))


def _action(
    label: str,
    *,
    task_id: str | None = None,
    tool: str | None = None,
    target: str | None = None,
    confirm: bool = False,
    open_report: bool = False,
    open_content: str | None = None,
    primary: bool = False,
) -> dict[str, Any]:
    return {
        "label": label,
        "task_id": task_id,
        "tool": tool,
        "target": target,
        "confirm": confirm,
        "open_report": open_report,
        "open_content": open_content,
        "primary": primary,
    }


def _has_featured(doc: Any) -> bool:
    if doc.metadata.get("featured_image") or doc.metadata.get("featured_media"):
        return True
    images = doc.metadata.get("images")
    return isinstance(images, dict) and bool(images)


def assess_site(site_key: str) -> dict[str, Any]:
    """Return readiness payload for one site folder."""
    site = load_site(site_key, require_credentials=False)
    has_credentials = bool(site.username and site.app_password)

    dash = run_site_dashboard(site)
    docs, parse_issues = load_tool_documents(site)
    publish_docs = [d for d in docs if d.collection in {"posts", "pages"}]
    if publish_docs:
        pr = run_publish_readiness(site, None, publish_docs)
    else:
        pr = {
            "summary": {
                "documents": 0,
                "ready": 0,
                "almost": 0,
                "blocked": 0,
                "drafts_ready_to_publish": 0,
                "published": 0,
                "drafts": 0,
            },
            "documents": [],
            "queue": {},
        }

    baselines = dash.get("baselines") or {}
    totals = dash.get("totals") or {}
    short_posts = list(dash.get("short_posts") or [])
    missing_images = list(dash.get("posts_missing_images") or [])
    content_issues = list(dash.get("content_issues") or [])

    min_posts = int(baselines.get("minimum_posts") or 25)
    min_pages = int(baselines.get("minimum_pages") or 5)
    min_cats = int(baselines.get("minimum_categories") or 5)
    min_words = int(baselines.get("minimum_words_per_post") or 800)

    posts = int(totals.get("posts") or 0)
    pages = int(totals.get("pages") or 0)
    categories = int(totals.get("categories") or 0)

    missing_featured: list[str] = []
    missing_excerpt: list[str] = []
    uncategorized: list[str] = []
    placeholders: list[str] = []
    for doc in publish_docs:
        if doc.collection == "posts" and not _has_featured(doc):
            missing_featured.append(doc.key)
        excerpt = str(
            doc.metadata.get("excerpt") or doc.metadata.get("meta_description") or ""
        ).strip()
        if doc.collection == "posts" and not (120 <= len(excerpt) <= 165):
            missing_excerpt.append(doc.key)
        cats = doc.metadata.get("categories")
        if doc.collection == "posts" and not cats:
            uncategorized.append(doc.key)
        body = doc.markdown.lower()
        if "lorem ipsum" in body or "[image prompt" in body or "todo" in body:
            placeholders.append(doc.key)

    pr_docs = pr.get("documents") or []
    blocked_docs = [r for r in pr_docs if r.get("readiness") == "blocked"]
    almost_docs = [r for r in pr_docs if r.get("readiness") == "almost"]
    ready_docs = [r for r in pr_docs if r.get("readiness") == "ready"]
    draft_ready = [r for r in ready_docs if r.get("status") in {"draft", "pending"}]

    kpis: list[dict[str, Any]] = [
        {
            "id": "posts",
            "label": "Posts",
            "actual": posts,
            "target": min_posts,
            "pct": _pct(posts, min_posts),
            "tone": _tone(posts, min_posts),
            "unit": "docs",
        },
        {
            "id": "pages",
            "label": "Pages",
            "actual": pages,
            "target": min_pages,
            "pct": _pct(pages, min_pages),
            "tone": _tone(pages, min_pages),
            "unit": "docs",
        },
        {
            "id": "categories",
            "label": "Categories",
            "actual": categories,
            "target": min_cats,
            "pct": _pct(categories, min_cats),
            "tone": _tone(categories, min_cats),
            "unit": "terms",
        },
        {
            "id": "ready_docs",
            "label": "Docs ready",
            "actual": len(ready_docs),
            "target": max(1, len(pr_docs)) if pr_docs else 1,
            "pct": _pct(len(ready_docs), max(1, len(pr_docs))),
            "tone": (
                "green"
                if pr_docs and not blocked_docs and not almost_docs
                else "yellow"
                if pr_docs and len(ready_docs) / max(1, len(pr_docs)) >= 0.4
                else "red"
            ),
            "unit": f"of {len(pr_docs)}",
        },
        {
            "id": "credentials",
            "label": "Credentials",
            "actual": 1 if has_credentials else 0,
            "target": 1,
            "pct": 100 if has_credentials else 0,
            "tone": "green" if has_credentials else "red",
            "unit": "env",
        },
    ]

    todos: list[dict[str, Any]] = []

    def add_todo(
        todo_id: str,
        severity: str,
        title: str,
        detail: str,
        *,
        category: str,
        items: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
        priority: int = 50,
    ) -> None:
        todos.append(
            {
                "id": todo_id,
                "severity": severity,
                "title": title,
                "detail": detail,
                "category": category,
                "items": (items or [])[:25],
                "item_count": len(items or []),
                "actions": actions or [],
                "priority": priority,
            }
        )

    if not has_credentials:
        add_todo(
            "credentials",
            "red",
            "Add WordPress credentials",
            f"Copy websites/{site_key}/.env.example to .env and set WP_USERNAME + WP_APP_PASSWORD. "
            "Connection, push, and verify stay blocked until this is done.",
            category="setup",
            priority=5,
            actions=[_action("Test connection (after .env)", task_id="doctor")],
        )
    else:
        add_todo(
            "credentials-ok",
            "green",
            "Credentials present",
            "Application password is configured. Run doctor anytime to re-check REST access.",
            category="setup",
            priority=200,
            actions=[_action("Test connection", task_id="doctor", primary=True)],
        )

    if posts < min_posts:
        deficit = min_posts - posts
        add_todo(
            "volume-posts",
            _tone(posts, min_posts),
            f"Add {deficit} more post(s)",
            f"{posts}/{min_posts} posts — below first-run baseline. New Markdown under content/posts/.",
            category="volume",
            priority=15,
            actions=[
                _action("Open content folder", open_content="content/posts", primary=True),
                _action("Content inventory", task_id="tool-content-inventory", open_report=True),
            ],
        )
    if pages < min_pages:
        deficit = min_pages - pages
        add_todo(
            "volume-pages",
            _tone(pages, min_pages),
            f"Add {deficit} more page(s)",
            f"{pages}/{min_pages} pages — about, contact, home, and policy pages close this gap.",
            category="volume",
            priority=16,
            actions=[
                _action("Open pages", open_content="content/pages", primary=True),
                _action("Content inventory", task_id="tool-content-inventory", open_report=True),
            ],
        )
    if categories < min_cats:
        deficit = min_cats - categories
        add_todo(
            "volume-categories",
            _tone(categories, min_cats),
            f"Add {deficit} more categor(ies)",
            f"{categories}/{min_cats} category files under content/categories/.",
            category="volume",
            priority=17,
            actions=[_action("Open categories", open_content="content/categories", primary=True)],
        )

    issue_paths = [
        (i.get("path", str(i)) if isinstance(i, dict) else str(i))
        for i in (content_issues or parse_issues)
    ]
    if issue_paths:
        add_todo(
            "parse-errors",
            "red",
            f"Fix {len(issue_paths)} unreadable Markdown file(s)",
            "Broken frontmatter or YAML stops lint, SEO tools, and push for those paths.",
            category="quality",
            items=issue_paths,
            priority=10,
            actions=[
                _action("Lint site", task_id="lint", primary=True),
                _action("Open first file", open_content=issue_paths[0]),
            ],
        )

    if placeholders:
        add_todo(
            "placeholders",
            "red",
            f"Remove placeholders in {len(placeholders)} document(s)",
            "lorem ipsum, TODO, or IMAGE PROMPT markers block publish readiness.",
            category="quality",
            items=placeholders,
            priority=12,
            actions=[
                _action(
                    "Publish readiness",
                    task_id="tool-publish-readiness",
                    open_report=True,
                    primary=True,
                ),
                _action("Open first", open_content=placeholders[0]),
            ],
        )

    if short_posts:
        add_todo(
            "short-posts",
            "yellow" if len(short_posts) / max(1, posts) < 0.4 else "red",
            f"Expand {len(short_posts)} short post(s)",
            f"Below {min_words} words — thin posts drag readiness and SEO floors.",
            category="quality",
            items=short_posts,
            priority=20,
            actions=[
                _action("Site dashboard", task_id="tool-site-dashboard", open_report=True),
                _action("Open first short post", open_content=short_posts[0], primary=True),
                _action("Content refresh queue", task_id="tool-content-refresh", open_report=True),
            ],
        )

    if missing_images:
        add_todo(
            "missing-images",
            "red" if len(missing_images) > 3 else "yellow",
            f"Add body images to {len(missing_images)} post(s)",
            "Posts without content images fail the image baseline and look thin in SERPs.",
            category="media",
            items=missing_images,
            priority=18,
            actions=[
                _action("Image inventory", task_id="tool-image-fixer", primary=True),
                _action("Open first post", open_content=missing_images[0]),
            ],
        )

    if missing_featured:
        add_todo(
            "featured-images",
            "yellow",
            f"Set featured images on {len(missing_featured)} document(s)",
            "Idempotent fixer picks first body image / images map / media slug match.",
            category="media",
            items=missing_featured,
            priority=22,
            actions=[
                _action(
                    "Auto-fix featured images",
                    task_id="tool-featured-image-fixer",
                    confirm=True,
                    open_report=True,
                    primary=True,
                ),
                _action(
                    "Fix then SEO audit",
                    task_id="tool-featured-then-seo",
                    confirm=True,
                    open_report=True,
                ),
            ],
        )

    if missing_excerpt:
        add_todo(
            "excerpts",
            "yellow",
            f"Fix excerpts on {len(missing_excerpt)} post(s)",
            "Want 120–165 characters in frontmatter excerpt (or meta_description).",
            category="seo",
            items=missing_excerpt,
            priority=25,
            actions=[
                _action("SEO audit", task_id="tool-seo-audit", open_report=True, primary=True),
                _action("Open first", open_content=missing_excerpt[0]),
            ],
        )

    if uncategorized:
        add_todo(
            "uncategorized",
            "yellow",
            f"Categorize {len(uncategorized)} post(s)",
            "Posts without categories hurt inventory, calendar, and topical structure.",
            category="seo",
            items=uncategorized,
            priority=26,
            actions=[
                _action(
                    "Content inventory",
                    task_id="tool-content-inventory",
                    open_report=True,
                    primary=True,
                ),
                _action("Open first", open_content=uncategorized[0]),
            ],
        )

    if blocked_docs:
        sample = [r["document"] for r in blocked_docs[:15]]
        add_todo(
            "publish-blocked",
            "red",
            f"{len(blocked_docs)} document(s) blocked for publish",
            "Title, slug, excerpt, depth, or placeholder checks still fail.",
            category="publish",
            items=sample,
            priority=14,
            actions=[
                _action(
                    "Publish readiness report",
                    task_id="tool-publish-readiness",
                    open_report=True,
                    primary=True,
                ),
                _action("SEO audit", task_id="tool-seo-audit", open_report=True),
                _action("Open first blocked", open_content=sample[0] if sample else None),
            ],
        )

    if almost_docs:
        sample = [r["document"] for r in almost_docs[:15]]
        add_todo(
            "publish-almost",
            "yellow",
            f"{len(almost_docs)} document(s) almost ready",
            "Warnings only (SEO floor, featured image, links). Tighten then promote.",
            category="publish",
            items=sample,
            priority=30,
            actions=[
                _action(
                    "Publish readiness",
                    task_id="tool-publish-readiness",
                    open_report=True,
                    primary=True,
                ),
                _action("Internal linker", task_id="tool-internal-linker"),
                _action("External linker", task_id="tool-external-linker"),
                _action(
                    "Featured image fixer",
                    task_id="tool-featured-image-fixer",
                    confirm=True,
                    open_report=True,
                ),
            ],
        )

    if draft_ready:
        sample = [r["document"] for r in draft_ready[:15]]
        add_todo(
            "drafts-ready",
            "green",
            f"{len(draft_ready)} draft(s) ready to publish",
            "Checklist clear — lint, plan, then push (or set status: publish in frontmatter first).",
            category="publish",
            items=sample,
            priority=40,
            actions=[
                _action("Lint", task_id="lint"),
                _action("Preview plan", task_id="plan", primary=True),
                _action("Push site", task_id="push", confirm=True),
            ],
        )

    if publish_docs:
        add_todo(
            "overlap-scan",
            "green",
            "Optional: scan content overlap before more long-tail pages",
            "Near-duplicates and intent collisions are cheaper to fix before push.",
            category="seo",
            priority=55,
            actions=[
                _action(
                    "Content overlap map",
                    task_id="tool-content-overlap",
                    open_report=True,
                    primary=True,
                ),
            ],
        )
        add_todo(
            "sync-path",
            "green",
            "Sync ladder when content is ready",
            "Lint → plan → push → verify. Push never deletes remote records.",
            category="sync",
            priority=60,
            actions=[
                _action("Lint", task_id="lint"),
                _action("Plan", task_id="plan", primary=True),
                _action("Push", task_id="push", confirm=True),
                _action("Verify", task_id="verify"),
            ],
        )

    score = 100
    if not has_credentials:
        score -= 25
    if posts < min_posts:
        score -= min(20, int((1 - posts / max(1, min_posts)) * 20))
    if pages < min_pages:
        score -= min(10, int((1 - pages / max(1, min_pages)) * 10))
    if categories < min_cats:
        score -= min(8, int((1 - categories / max(1, min_cats)) * 8))
    score -= min(15, len(short_posts) * 2)
    score -= min(12, len(missing_images) * 2)
    score -= min(10, len(missing_featured))
    score -= min(15, len(blocked_docs))
    score -= min(8, len(almost_docs) // 2)
    score -= min(10, len(placeholders) * 3)
    score -= min(10, len(issue_paths) * 4)
    score = max(0, min(100, score))

    open_red = sum(1 for t in todos if t["severity"] == "red")
    open_yellow = sum(1 for t in todos if t["severity"] == "yellow")
    blocking_red = [t for t in todos if t["severity"] == "red"]
    blocking_yellow = [t for t in todos if t["severity"] == "yellow"]

    if not blocking_red and not blocking_yellow and score >= 80:
        overall = "ready"
    elif blocking_red:
        overall = "blocked"
    else:
        overall = "almost"

    severity_rank = {"red": 0, "yellow": 1, "green": 2}
    todos.sort(key=lambda t: (severity_rank.get(t["severity"], 9), t["priority"], t["title"]))

    doc_rows: list[dict[str, Any]] = []
    for r in pr_docs:
        tone = {"ready": "green", "almost": "yellow", "blocked": "red"}.get(
            r.get("readiness"), "yellow"
        )
        doc_rows.append(
            {
                "document": r.get("document"),
                "title": r.get("title"),
                "collection": r.get("collection"),
                "status": r.get("status"),
                "readiness": r.get("readiness"),
                "tone": tone,
                "seo_score": r.get("seo_score"),
                "words": r.get("words"),
                "blockers": r.get("blockers") or [],
                "warnings": r.get("warnings") or [],
                "recommended_action": r.get("recommended_action"),
            }
        )
    doc_rows.sort(
        key=lambda d: (
            {"blocked": 0, "almost": 1, "ready": 2}.get(d["readiness"], 9),
            -(d.get("seo_score") or 0),
            d.get("document") or "",
        )
    )

    next_actions: list[dict[str, Any]] = []
    for t in todos:
        if t["severity"] == "green" and t["id"] not in {"drafts-ready", "sync-path"}:
            continue
        for a in t["actions"]:
            if a.get("primary") or not next_actions:
                next_actions.append({**a, "todo_id": t["id"], "todo_title": t["title"]})
                break
        if len(next_actions) >= 4:
            break

    return {
        "site": site_key,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall": overall,
        "score": score,
        "label": {
            "ready": "Ready",
            "almost": "Almost ready",
            "blocked": "Not ready",
        }.get(overall, overall),
        "summary": {
            "red_todos": open_red,
            "yellow_todos": open_yellow,
            "documents": len(pr_docs),
            "docs_ready": len(ready_docs),
            "docs_almost": len(almost_docs),
            "docs_blocked": len(blocked_docs),
            "drafts_ready_to_publish": len(draft_ready),
            "has_credentials": has_credentials,
            "posts": posts,
            "pages": pages,
            "categories": categories,
        },
        "kpis": kpis,
        "todos": todos,
        "next_actions": next_actions,
        "documents": doc_rows[:80],
        "baselines": baselines,
        "totals": totals,
    }


def quick_site_tone(
    site_key: str, has_credentials: bool, counts: dict[str, int]
) -> dict[str, Any]:
    """Cheap traffic-light for the site list (no full SEO audit)."""
    posts = counts.get("posts", 0)
    pages = counts.get("pages", 0)
    categories = counts.get("categories", 0)
    if not has_credentials or posts == 0:
        tone = "red"
    elif posts < 15 or pages < 3 or categories < 3:
        tone = "yellow"
    else:
        tone = "green"
    return {
        "tone": tone,
        "posts": posts,
        "pages": pages,
        "categories": categories,
        "has_credentials": has_credentials,
    }
