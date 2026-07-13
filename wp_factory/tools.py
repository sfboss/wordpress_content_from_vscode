from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, date
from pathlib import Path
from typing import Any, Callable

from .config import ROOT, SiteConfig, list_site_keys, load_site
from .content import COLLECTIONS, LOCAL_IMAGE_RE, load_documents, resolve_local_image
from .content_overlap import run_content_overlap, write_content_overlap_html
from .dashboard import write_dashboard_html
from .models import Document
from .featured_images import run_featured_image_fixer
from .seo_tools import (
    run_link_health,
    run_publish_readiness,
    run_readability,
    run_schema_suggest,
    run_seo_audit,
    write_tool_html,
)
from .utils import slugify, title_from_filename
import frontmatter
from .reporting import write_report

LINK_RE = re.compile(r"(?<![!])\[[^\]]+\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
WORD_RE = re.compile(r"\b[\w'-]+\b")
DATA_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(data:image/[^)]+\)")

@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    batch_safe: bool
    runner: Callable[[SiteConfig, Path | None], dict[str, Any]]


def load_tool_documents(site: SiteConfig) -> tuple[list[Document], list[dict[str, str]]]:
    documents: list[Document] = []
    issues: list[dict[str, str]] = []
    # Prefer the featured-image-aware loader (YAML colon repair) so SEO tools
    # keep seeing progress after fixer runs, without re-implementing parse logic.
    from .featured_images import load_markdown_document

    for collection, spec in COLLECTIONS.items():
        directory = site.content_dir / spec["directory"]
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            try:
                post, _raw, _repaired = load_markdown_document(path)
            except Exception as exc:  # report malformed content without blocking dashboards
                issues.append({"path": path.relative_to(site.directory).as_posix(), "error": str(exc)})
                continue
            metadata = dict(post.metadata)
            title = str(metadata.get("title") or title_from_filename(path)).strip()
            slug = slugify(str(metadata.get("slug") or path.stem))
            documents.append(Document(path.relative_to(site.directory).as_posix(), collection, spec["endpoint"], path, metadata, post.content, title, slug, str(metadata.get("status") or site.default_status), "tool-scan"))
    return documents, issues


def _target_docs(site: SiteConfig, target: Path | None):
    docs, _issues = load_tool_documents(site)
    return _filter_target_docs(docs, target)


def _filter_target_docs(docs: list[Document], target: Path | None) -> list[Document]:
    if not target:
        return docs
    target = target.resolve()
    return [doc for doc in docs if doc.path.resolve() == target or target in doc.path.resolve().parents]


def run_image_fixer(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    rows = []
    for doc in _target_docs(site, target):
        for src in LOCAL_IMAGE_RE.findall(doc.markdown):
            local = resolve_local_image(src, doc.path, site)
            kind = "remote" if src.startswith(("http://", "https://", "//")) else "data-uri" if src.startswith("data:") else "local"
            configured = doc.metadata.get("images", {}).get(src, {}) if isinstance(doc.metadata.get("images"), dict) else {}
            rows.append({
                "document": doc.key,
                "src": src[:120],
                "kind": kind,
                "status": "ready-for-upload" if local and local.exists() else "needs-import" if kind in {"remote", "data-uri"} else "missing-local-file",
                "alt": configured.get("alt", ""),
                "title": configured.get("title", ""),
                "required_next_step": "upload to WordPress media library and rewrite HTML during push" if kind == "local" else "download/decode into content/media, create metadata, upload, then rewrite",
            })
        for match in DATA_IMAGE_RE.findall(doc.markdown):
            if not any(row["document"] == doc.key and row["kind"] == "data-uri" for row in rows):
                rows.append({"document": doc.key, "src": match[:120], "kind": "data-uri", "status": "needs-import"})
    return {"tool": "image-fixer", "target": str(target) if target else "site", "images": rows, "counts": _counts(rows, "status")}


def run_external_linker(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    rows = []
    for doc in _target_docs(site, target):
        links = [href for href in LINK_RE.findall(doc.markdown) if href.startswith(("http://", "https://")) and site.site_url not in href]
        words = [w.lower() for w in WORD_RE.findall(doc.markdown) if len(w) > 4]
        candidates = sorted(set(words), key=words.count, reverse=True)[:12]
        rows.append({"document": doc.key, "external_links": links, "candidate_entities": candidates, "status": "needs-authoritative-links" if len(links) < 2 else "ok"})
    return {"tool": "external-linker", "target": str(target) if target else "site", "documents": rows, "counts": _counts(rows, "status")}


def run_internal_linker(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    all_docs, issues = load_tool_documents(site)
    catalog = [{"title": d.title, "slug": d.slug, "key": d.key, "collection": d.collection} for d in all_docs]
    rows = []
    for doc in _target_docs(site, target):
        internal = [href for href in LINK_RE.findall(doc.markdown) if href.startswith(("wp://", "/")) or site.site_url in href]
        suggestions = [item for item in catalog if item["key"] != doc.key and item["title"].lower().split()[0] in doc.markdown.lower()][:8]
        rows.append({"document": doc.key, "internal_links": internal, "suggestions": suggestions, "status": "needs-internal-links" if len(internal) < 2 and suggestions else "ok"})
    return {"tool": "internal-linker", "target": str(target) if target else "site", "documents": rows, "content_issues": issues, "counts": _counts(rows, "status")}


def run_site_dashboard(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    docs, issues = load_tool_documents(site)
    categories = sorted((site.content_dir / "categories").glob("*.md")) if (site.content_dir / "categories").exists() else []
    rows = []
    for doc in docs:
        word_count = len(WORD_RE.findall(doc.markdown))
        images = LOCAL_IMAGE_RE.findall(doc.markdown)
        rows.append({"document": doc.key, "collection": doc.collection, "status": doc.status, "words": word_count, "images": len(images), "headings": len(HEADING_RE.findall(doc.markdown)), "categories": doc.metadata.get("categories", [])})
    totals = {"documents": len(rows), "posts": sum(r["collection"] == "posts" for r in rows), "pages": sum(r["collection"] == "pages" for r in rows), "categories": len(categories), "words": sum(r["words"] for r in rows)}
    baselines = {"minimum_posts": 25, "minimum_pages": 5, "minimum_categories": 5, "minimum_words_per_post": 800, "minimum_images_per_post": 1}
    kpis = {key: {"target": val, "actual": totals.get(key.removeprefix("minimum_"), 0)} for key, val in baselines.items() if key in {"minimum_posts", "minimum_pages", "minimum_categories"}}
    short_posts = [r["document"] for r in rows if r["collection"] == "posts" and r["words"] < baselines["minimum_words_per_post"]]
    missing_images = [r["document"] for r in rows if r["collection"] == "posts" and r["images"] < baselines["minimum_images_per_post"]]
    return {"tool": "site-dashboard", "generated_at": datetime.now(UTC).isoformat(), "totals": totals, "baselines": baselines, "kpis": kpis, "short_posts": short_posts, "posts_missing_images": missing_images, "content_issues": issues, "documents": rows}



def _meta_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _doc_date(doc: Document) -> date | None:
    for key in ("date", "publish_date", "published_at", "modified", "updated_at", "last_reviewed"):
        found = _meta_date(doc.metadata.get(key))
        if found:
            return found
    return None


<<<<<<< ours
<<<<<<< ours
def run_content_inventory(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    docs, issues = load_tool_documents(site)
    scoped = _target_docs(site, target)
=======
=======
>>>>>>> theirs
def _categories(doc: Document) -> list[str]:
    value = doc.metadata.get("categories")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _has_excerpt(doc: Document) -> bool:
    return bool(doc.metadata.get("excerpt") or doc.metadata.get("meta_description") or doc.metadata.get("seo_description"))


def run_content_inventory(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    docs, issues = load_tool_documents(site)
    scoped = _filter_target_docs(docs, target)
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
    slug_counts = Counter(d.slug for d in docs)
    title_counts = Counter(d.title.strip().lower() for d in docs)
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    collection_counts: Counter[str] = Counter()
    rows = []
    for doc in scoped:
        words = len(WORD_RE.findall(doc.markdown))
<<<<<<< ours
<<<<<<< ours
        cats = doc.metadata.get("categories") if isinstance(doc.metadata.get("categories"), list) else []
=======
        cats = _categories(doc)
>>>>>>> theirs
=======
        cats = _categories(doc)
>>>>>>> theirs
        category_counts.update(str(c) for c in cats)
        status_counts.update([doc.status])
        collection_counts.update([doc.collection])
        flags = []
        if slug_counts[doc.slug] > 1:
            flags.append("duplicate-slug")
        if title_counts[doc.title.strip().lower()] > 1:
            flags.append("duplicate-title")
        if doc.collection == "posts" and not cats:
            flags.append("uncategorized")
        if words < (800 if doc.collection == "posts" else 300):
            flags.append("thin-content")
<<<<<<< ours
<<<<<<< ours
        if not doc.metadata.get("excerpt") and not doc.metadata.get("meta_description"):
=======
        if not _has_excerpt(doc):
>>>>>>> theirs
=======
        if not _has_excerpt(doc):
>>>>>>> theirs
            flags.append("missing-excerpt")
        rows.append({"document": doc.key, "collection": doc.collection, "status": doc.status, "title": doc.title, "slug": doc.slug, "words": words, "categories": cats, "flags": flags})
    return {"tool": "content-inventory", "generated_at": datetime.now(UTC).isoformat(), "target": str(target) if target else "site", "summary": {"documents": len(rows), "collections": dict(collection_counts), "statuses": dict(status_counts), "categories": dict(category_counts), "flagged": sum(bool(r["flags"]) for r in rows), "duplicate_slugs": sum(1 for c in slug_counts.values() if c > 1)}, "documents": rows, "content_issues": issues}


def run_content_refresh(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    rows = []
    for doc in _target_docs(site, target):
        reviewed = _meta_date(doc.metadata.get("last_reviewed"))
        updated = _doc_date(doc)
        basis = reviewed or updated
        age_days = (today - basis).days if basis else None
        issues = []
        if basis is None:
            issues.append("missing-review-date")
        elif age_days is not None and age_days >= 180:
            issues.append("stale-review")
        if re.search(r"\b(20[0-2][0-9]|last year|this year|recently|currently)\b", doc.markdown, re.I):
            issues.append("time-sensitive-language")
        if "TODO" in doc.markdown or "[UPDATE" in doc.markdown:
            issues.append("editorial-placeholder")
        priority = "high" if "editorial-placeholder" in issues or "missing-review-date" in issues else "medium" if issues else "low"
        rows.append({"document": doc.key, "title": doc.title, "status": doc.status, "last_reviewed": str(reviewed) if reviewed else None, "content_date": str(updated) if updated else None, "age_days": age_days, "issues": issues, "priority": priority, "recommended_action": "Refresh facts, screenshots, links, and SERP intent; update last_reviewed." if issues else "No refresh needed right now."})
    rows.sort(key=lambda r: ({"high": 0, "medium": 1, "low": 2}[r["priority"]], -(r["age_days"] or 0), r["document"]))
    return {"tool": "content-refresh", "generated_at": datetime.now(UTC).isoformat(), "target": str(target) if target else "site", "summary": {"documents": len(rows), "high": sum(r["priority"] == "high" for r in rows), "medium": sum(r["priority"] == "medium" for r in rows), "low": sum(r["priority"] == "low" for r in rows)}, "queue": rows[:25], "documents": rows}


def run_editorial_calendar(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    rows = []
    for doc in _target_docs(site, target):
        planned = _meta_date(doc.metadata.get("date") or doc.metadata.get("publish_date"))
<<<<<<< ours
<<<<<<< ours
        cats = doc.metadata.get("categories") if isinstance(doc.metadata.get("categories"), list) else []
=======
        cats = _categories(doc)
>>>>>>> theirs
=======
        cats = _categories(doc)
>>>>>>> theirs
        stage = "published" if doc.status == "publish" else "scheduled" if planned else "unscheduled"
        blockers = []
        if doc.collection == "posts" and not cats:
            blockers.append("category")
<<<<<<< ours
<<<<<<< ours
        if not doc.metadata.get("excerpt") and not doc.metadata.get("meta_description"):
=======
        if not _has_excerpt(doc):
>>>>>>> theirs
=======
        if not _has_excerpt(doc):
>>>>>>> theirs
            blockers.append("excerpt")
        rows.append({"document": doc.key, "title": doc.title, "collection": doc.collection, "status": doc.status, "planned_date": str(planned) if planned else None, "stage": stage, "categories": cats, "blockers": blockers})
    rows.sort(key=lambda r: (r["planned_date"] or "9999-99-99", r["document"]))
    return {"tool": "editorial-calendar", "generated_at": datetime.now(UTC).isoformat(), "target": str(target) if target else "site", "summary": {"documents": len(rows), "scheduled": sum(r["stage"] == "scheduled" for r in rows), "unscheduled": sum(r["stage"] == "unscheduled" for r in rows), "published": sum(r["stage"] == "published" for r in rows), "blocked": sum(bool(r["blockers"]) for r in rows)}, "calendar": rows}

def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts

def _with_docs(runner):
    """Adapt seo_tools runners that need the document list to the ToolSpec signature."""

    def wrapped(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
        docs = _target_docs(site, target)
        return runner(site, target, docs)

    return wrapped


def _with_catalog(runner):
    """Adapt tools that compare a target with the complete site catalog."""

    def wrapped(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
        docs, _issues = load_tool_documents(site)
        return runner(site, target, docs)

    return wrapped


TOOLS = {
    "image-fixer": ToolSpec("image-fixer", "Image Import + SEO Fixer", "Inventory local, remote, and data-uri images so each can be imported to WordPress with filename, metadata, and alt text.", True, run_image_fixer),
    "external-linker": ToolSpec("external-linker", "External Link Assistant", "Find pages/posts that need authoritative outbound links and surface entity/keyword candidates for review.", True, run_external_linker),
    "internal-linker": ToolSpec("internal-linker", "Internal Link Graph Assistant", "Evaluate cross-link coverage and suggest relevant local content to keep the site intertwined.", True, run_internal_linker),
    "site-dashboard": ToolSpec("site-dashboard", "Content Factory Dashboard", "Report whole-site content KPIs, category coverage, post depth, and first-run readiness baselines.", True, run_site_dashboard),
    "content-inventory": ToolSpec("content-inventory", "Content Inventory + Gap Finder", "Inventory titles, slugs, statuses, categories, duplicates, thin content, and missing metadata for editorial planning.", True, run_content_inventory),
    "editorial-calendar": ToolSpec("editorial-calendar", "Editorial Calendar", "Build a schedule view from date/publish_date frontmatter and flag unscheduled or blocked content adventure items.", True, run_editorial_calendar),
    "content-refresh": ToolSpec("content-refresh", "Content Refresh Queue", "Find stale, undated, time-sensitive, or placeholder content that should be refreshed before publication or promotion.", True, run_content_refresh),
    "seo-audit": ToolSpec(
        "seo-audit",
        "On-page SEO Audit",
        "AIOSEO-style checks: title/meta length, focus keyphrase placement, slug quality, H2 structure, featured image, depth, and link hygiene. Scores every post/page 0–100.",
        True,
        _with_docs(run_seo_audit),
    ),
    "readability": ToolSpec(
        "readability",
        "Readability Scorecard",
        "Flesch reading ease, sentence/paragraph length, passive-voice signals, and heading density so content is skimmable for humans and AI overviews.",
        True,
        _with_docs(run_readability),
    ),
    "link-health": ToolSpec(
        "link-health",
        "Link Health Checker",
        "Inventory internal/external links and live-check HTTP URLs for broken, redirected, or timed-out destinations (capped for speed).",
        True,
        _with_docs(run_link_health),
    ),
    "schema-suggest": ToolSpec(
        "schema-suggest",
        "Schema / Structured Data Suggester",
        "Detect Article, FAQPage, HowTo, and BreadcrumbList opportunities and emit reviewable JSON-LD drafts from Markdown structure.",
        True,
        _with_docs(run_schema_suggest),
    ),
    "publish-readiness": ToolSpec(
        "publish-readiness",
        "Publish Readiness Queue",
        "Go-live checklist per document: blockers, warnings, SEO floor, placeholders, and a prioritized queue of drafts ready to publish.",
        True,
        _with_docs(run_publish_readiness),
    ),
    "featured-image-fixer": ToolSpec(
        "featured-image-fixer",
        "Featured Image Fixer",
        "Idempotently set featured_image from the first body image, images map, or media file matching the slug; repair YAML so audits keep seeing progress.",
        True,
        run_featured_image_fixer,
    ),
    "content-overlap": ToolSpec(
        "content-overlap",
        "Content Overlap + Cannibalization Map",
        "Detect near-duplicate prose and potential search-intent collisions before manual or generated long-tail pages compete with each other.",
        True,
        _with_catalog(run_content_overlap),
    ),
}

HTML_REPORT_TOOLS = {
    "site-dashboard",
    "seo-audit",
    "readability",
    "link-health",
    "schema-suggest",
    "publish-readiness",
    "featured-image-fixer",
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
    "content-overlap",
=======
    "content-inventory",
    "editorial-calendar",
    "content-refresh",
>>>>>>> theirs
=======
    "content-inventory",
    "editorial-calendar",
    "content-refresh",
>>>>>>> theirs
=======
    "content-inventory",
    "editorial-calendar",
    "content-refresh",
>>>>>>> theirs
=======
    "content-inventory",
    "editorial-calendar",
    "content-refresh",
>>>>>>> theirs
}


def list_tools() -> list[dict[str, Any]]:
    return [{"name": t.name, "title": t.title, "description": t.description, "batch_safe": t.batch_safe} for t in TOOLS.values()]


def run_tool(name: str, site_key: str, target: str | None = None) -> tuple[dict[str, Any], Path]:
    if name not in TOOLS:
        raise KeyError(name)
    site = load_site(site_key, require_credentials=False)
    target_path = Path(target).resolve() if target else None
    payload = TOOLS[name].runner(site, target_path)
    report = write_report(site, f"tool-{name}", payload)
    if name == "site-dashboard":
        write_dashboard_html(site.key, payload, report)
    elif name == "content-overlap":
        write_content_overlap_html(site.key, payload, report)
    elif name in HTML_REPORT_TOOLS - {"site-dashboard"}:
        write_tool_html(site.key, payload, report)
    return payload, report
