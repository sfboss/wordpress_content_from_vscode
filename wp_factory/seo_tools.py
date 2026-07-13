"""SEO and content-readiness tools for the command center.

These are All-in-One-SEO-inspired, Markdown-first jobs: on-page SEO audit,
readability scoring, outbound/inbound link health, structured-data suggestions,
and a publish-readiness checklist. They are report-first and non-mutating.
"""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import SiteConfig
from .content import LOCAL_IMAGE_RE, resolve_local_image
from .models import Document

# Reuse shared patterns from tools when available via late import to avoid cycles
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
LINK_RE = re.compile(r"(?<![!])\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$", re.MULTILINE)
PARAGRAPH_RE = re.compile(r"\n\s*\n")
STOP = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "this",
    "that", "these", "those", "it", "its", "your", "you", "our", "we", "they", "their",
    "how", "what", "when", "where", "why", "which", "who", "whom", "into", "over",
    "under", "about", "than", "then", "also", "just", "only", "more", "most", "very",
}


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def _word_count(text: str) -> int:
    return len(_words(text))


def _excerpt_of(doc: Document) -> str:
    meta = doc.metadata
    for key in ("meta_description", "seo_description", "description", "excerpt"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _focus_keyword(doc: Document) -> str:
    meta = doc.metadata
    for key in ("focus_keyword", "focus_keyphrase", "primary_keyword", "keyword"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    # Derive a rough keyphrase from the title (drop stopwords, keep 2–5 tokens).
    tokens = [w.lower() for w in _words(doc.title) if w.lower() not in STOP and len(w) > 2]
    if not tokens:
        return doc.slug.replace("-", " ")
    return " ".join(tokens[:5])


def _headings(markdown: str) -> list[tuple[int, str]]:
    return [(len(m.group(1)), m.group(2).strip()) for m in HEADING_LINE_RE.finditer(markdown)]


def _first_paragraph(markdown: str) -> str:
    body = re.sub(r"^---.*?---\s*", "", markdown, count=1, flags=re.S)
    body = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.M)
    chunks = [c.strip() for c in PARAGRAPH_RE.split(body) if c.strip() and not c.strip().startswith("```")]
    return chunks[0] if chunks else ""


def _has_featured(doc: Document) -> bool:
    if doc.metadata.get("featured_image") or doc.metadata.get("featured_media"):
        return True
    images = doc.metadata.get("images")
    return isinstance(images, dict) and bool(images)


def _score_band(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "needs-work"
    return "poor"


# ---------------------------------------------------------------------------
# 1. SEO Audit (AIOSEO-style on-page analyzer)
# ---------------------------------------------------------------------------

def run_seo_audit(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for doc in docs:
        issues: list[dict[str, str]] = []
        checks: list[dict[str, Any]] = []
        score = 100
        focus = _focus_keyword(doc)
        title = doc.title
        slug = doc.slug
        excerpt = _excerpt_of(doc)
        body = doc.markdown
        body_lower = body.lower()
        first = _first_paragraph(body).lower()
        headings = _headings(body)
        h1s = [h for level, h in headings if level == 1]
        h2s = [h for level, h in headings if level == 2]
        words = _word_count(body)
        images = LOCAL_IMAGE_RE.findall(body)
        image_meta = doc.metadata.get("images") if isinstance(doc.metadata.get("images"), dict) else {}

        def check(name: str, ok: bool, weight: int, message: str, fix: str) -> None:
            nonlocal score
            checks.append({"name": name, "ok": ok, "weight": weight, "message": message, "fix": fix})
            if not ok:
                score -= weight
                issues.append({"check": name, "message": message, "fix": fix})

        title_len = len(title)
        check(
            "title-length",
            30 <= title_len <= 60,
            10,
            f"Title is {title_len} characters (aim 30–60).",
            "Shorten or expand the title so it fits common SERP widths without stuffing.",
        )
        check(
            "title-has-focus",
            focus.split()[0] in title.lower() if focus else False,
            12,
            f"Focus keyphrase “{focus}” should appear in the title.",
            "Put the primary keyphrase near the start of the title when it still reads naturally.",
        )

        excerpt_len = len(excerpt)
        check(
            "meta-description",
            120 <= excerpt_len <= 165,
            12,
            f"Excerpt/meta description is {excerpt_len} characters (aim 120–165).",
            "Set frontmatter `excerpt` (or `meta_description`) to a clear SERP summary with the keyphrase.",
        )
        check(
            "excerpt-has-focus",
            bool(excerpt) and focus.split()[0] in excerpt.lower(),
            8,
            "Meta description should include the focus keyphrase.",
            "Rewrite the excerpt so the keyphrase appears once, naturally.",
        )

        slug_len = len(slug)
        check(
            "slug-length",
            3 <= slug_len <= 75 and "-" in slug,
            6,
            f"Slug “{slug}” length {slug_len}; prefer hyphenated, readable slugs under ~75 chars.",
            "Use a short, keyword-bearing slug without stopword spam or dates unless intentional.",
        )
        check(
            "slug-has-focus",
            any(tok in slug for tok in focus.replace(" ", "-").split("-") if len(tok) > 3),
            8,
            "Slug should carry at least one significant focus token.",
            "Align the slug with the primary keyphrase without keyword stuffing.",
        )

        check(
            "focus-in-opening",
            focus.split()[0] in first if focus else False,
            10,
            "Opening paragraph should introduce the focus keyphrase early.",
            "Mention the keyphrase in the first ~100 words without forcing awkward phrasing.",
        )
        check(
            "h2-structure",
            words < 600 or len(h2s) >= 2,
            8,
            f"Longer content needs clear H2 structure ({len(h2s)} found, {words} words).",
            "Add descriptive `##` sections that map to search intent subtopics.",
        )
        check(
            "single-h1-body",
            len(h1s) <= 1,
            6,
            f"Body has {len(h1s)} H1 headings; prefer the frontmatter title as the page H1.",
            "Demote body `#` headings to `##` so the theme title remains the primary H1.",
        )
        check(
            "featured-image",
            _has_featured(doc),
            8,
            "Missing featured image metadata.",
            "Set `featured_image: ../media/...` and provide alt text in the `images` map.",
        )
        check(
            "content-depth",
            words >= (400 if doc.collection == "pages" else 800),
            10,
            f"{words} words; posts ideally ≥800, pages ≥400 for pillar coverage.",
            "Expand with useful sections, examples, FAQs, or procedure detail — not filler.",
        )

        empty_alt = 0
        for src in images:
            conf = image_meta.get(src, {}) if isinstance(image_meta, dict) else {}
            alt = str(conf.get("alt") or "")
            # Markdown alt fallback: ![alt](src)
            md_alt_match = re.search(rf"!\[([^\]]*)\]\({re.escape(src)}", body)
            md_alt = md_alt_match.group(1) if md_alt_match else ""
            if not (alt.strip() or md_alt.strip()):
                empty_alt += 1
        check(
            "image-alt",
            empty_alt == 0,
            6,
            f"{empty_alt} image(s) lack alt text.",
            "Add specific alt in frontmatter `images:` or in the Markdown image alt field.",
        )

        external = [href for _, href in LINK_RE.findall(body) if href.startswith(("http://", "https://")) and site.site_url not in href]
        internal = [
            href
            for _, href in LINK_RE.findall(body)
            if href.startswith(("/", "wp://", "./", "../")) or (site.site_url and site.site_url in href)
        ]
        check(
            "outbound-links",
            len(external) >= 1 or words < 500,
            4,
            f"{len(external)} external links; long posts benefit from 1–3 authoritative sources.",
            "Link to official docs or primary sources where claims depend on platform behavior.",
        )
        check(
            "internal-links",
            len(internal) >= 1 or words < 500,
            4,
            f"{len(internal)} internal links; strengthen topical clusters.",
            "Link to related posts/pages in the same content cluster.",
        )

        score = max(0, min(100, score))
        rows.append(
            {
                "document": doc.key,
                "collection": doc.collection,
                "status": doc.status,
                "title": title,
                "slug": slug,
                "focus_keyword": focus,
                "score": score,
                "band": _score_band(score),
                "words": words,
                "title_length": title_len,
                "excerpt_length": excerpt_len,
                "h1_count": len(h1s),
                "h2_count": len(h2s),
                "images": len(images),
                "external_links": len(external),
                "internal_links": len(internal),
                "featured_image": _has_featured(doc),
                "checks": checks,
                "issues": issues,
                "issue_count": len(issues),
            }
        )

    rows.sort(key=lambda r: (r["score"], r["document"]))
    avg = round(sum(r["score"] for r in rows) / len(rows)) if rows else 0
    return {
        "tool": "seo-audit",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {
            "documents": len(rows),
            "average_score": avg,
            "excellent": sum(1 for r in rows if r["band"] == "excellent"),
            "good": sum(1 for r in rows if r["band"] == "good"),
            "needs_work": sum(1 for r in rows if r["band"] == "needs-work"),
            "poor": sum(1 for r in rows if r["band"] == "poor"),
            "missing_featured_image": sum(1 for r in rows if not r["featured_image"]),
            "weak_meta": sum(1 for r in rows if r["excerpt_length"] < 120 or r["excerpt_length"] > 165),
        },
        "documents": rows,
        "priority_fixes": [
            {"document": r["document"], "score": r["score"], "top_issues": r["issues"][:3]}
            for r in sorted(rows, key=lambda x: x["score"])[:12]
            if r["issues"]
        ],
    }


# ---------------------------------------------------------------------------
# 2. Readability
# ---------------------------------------------------------------------------

def _syllables(word: str) -> int:
    w = word.lower()
    if len(w) <= 3:
        return 1
    w = re.sub(r"[^a-z]", "", w)
    count = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e"):
        count = max(1, count - 1)
    return max(1, count)


def run_readability(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for doc in docs:
        text = re.sub(r"```.*?```", " ", doc.markdown, flags=re.S)
        text = re.sub(r"`[^`]+`", " ", text)
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
        text = re.sub(r"\[[^\]]*\]\([^)]+\)", " ", text)
        text = re.sub(r"[#>*_|-]+", " ", text)
        sentences = [s.strip() for s in SENTENCE_RE.findall(text) if s.strip() and len(_words(s)) > 1]
        words = _words(text)
        word_n = len(words)
        sent_n = max(1, len(sentences))
        syl_n = sum(_syllables(w) for w in words) if words else 1
        # Flesch Reading Ease
        fre = 206.835 - 1.015 * (word_n / sent_n) - 84.6 * (syl_n / max(1, word_n))
        fre = round(max(0.0, min(100.0, fre)), 1)
        avg_sentence = round(word_n / sent_n, 1)
        long_sentences = sum(1 for s in sentences if len(_words(s)) > 25)
        paragraphs = [p for p in PARAGRAPH_RE.split(doc.markdown) if p.strip() and not p.strip().startswith("#")]
        avg_para = round(sum(len(_words(p)) for p in paragraphs) / max(1, len(paragraphs)), 1)
        passive_hits = len(re.findall(r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b", text, re.I))
        headings = _headings(doc.markdown)
        issues = []
        if fre < 50:
            issues.append("Reading ease is hard for general audiences (aim ≥50–60 for marketing/help content).")
        if avg_sentence > 22:
            issues.append(f"Average sentence length is {avg_sentence} words; break up long sentences.")
        if long_sentences >= 5:
            issues.append(f"{long_sentences} sentences exceed 25 words.")
        if word_n > 800 and len(headings) < 3:
            issues.append("Long article with few headings; add H2/H3 signposts.")
        if passive_hits > max(3, word_n // 200):
            issues.append(f"Possible heavy passive voice ({passive_hits} patterns); prefer active verbs.")
        band = "easy" if fre >= 70 else "standard" if fre >= 50 else "difficult"
        rows.append(
            {
                "document": doc.key,
                "collection": doc.collection,
                "words": word_n,
                "sentences": sent_n,
                "flesch_reading_ease": fre,
                "band": band,
                "avg_sentence_words": avg_sentence,
                "long_sentences": long_sentences,
                "avg_paragraph_words": avg_para,
                "passive_patterns": passive_hits,
                "headings": len(headings),
                "issues": issues,
                "status": "ok" if not issues else "needs-work",
            }
        )
    rows.sort(key=lambda r: r["flesch_reading_ease"])
    return {
        "tool": "readability",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {
            "documents": len(rows),
            "average_flesch": round(sum(r["flesch_reading_ease"] for r in rows) / len(rows), 1) if rows else 0,
            "difficult": sum(1 for r in rows if r["band"] == "difficult"),
            "standard": sum(1 for r in rows if r["band"] == "standard"),
            "easy": sum(1 for r in rows if r["band"] == "easy"),
        },
        "documents": rows,
    }


# ---------------------------------------------------------------------------
# 3. Link health (broken / redirect / timeout)
# ---------------------------------------------------------------------------

def _check_url(url: str, timeout: float = 6.0) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"url": url, "status": "skipped", "code": None, "detail": "non-http scheme"}
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "WordPress-Content-Factory/1.0 (+local link-health tool)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            final = resp.geturl()
            return {
                "url": url,
                "status": "ok" if 200 <= int(code) < 400 else "broken",
                "code": int(code),
                "final_url": final,
                "redirected": final.rstrip("/") != url.rstrip("/"),
            }
    except urllib.error.HTTPError as exc:
        # Some hosts reject HEAD; retry GET
        if exc.code in {405, 403, 501}:
            try:
                greq = urllib.request.Request(
                    url,
                    method="GET",
                    headers={"User-Agent": "WordPress-Content-Factory/1.0 (+local link-health tool)"},
                )
                with urllib.request.urlopen(greq, timeout=timeout) as resp:
                    code = getattr(resp, "status", None) or resp.getcode()
                    return {"url": url, "status": "ok" if 200 <= int(code) < 400 else "broken", "code": int(code), "final_url": resp.geturl()}
            except Exception as retry_exc:  # noqa: BLE001
                return {"url": url, "status": "broken", "code": getattr(exc, "code", None), "detail": str(retry_exc)[:160]}
        return {"url": url, "status": "broken", "code": exc.code, "detail": str(exc.reason)[:160]}
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return {"url": url, "status": "timeout" if "timed out" in str(exc).lower() else "error", "code": None, "detail": str(exc)[:160]}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": "error", "code": None, "detail": str(exc)[:160]}


def run_link_health(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    # Dedupe network checks across the site for speed
    url_docs: dict[str, list[str]] = {}
    rows: list[dict[str, Any]] = []
    for doc in docs:
        for text, href in LINK_RE.findall(doc.markdown):
            href = href.strip()
            kind = (
                "external"
                if href.startswith(("http://", "https://")) and site.site_url not in href
                else "site"
                if site.site_url and site.site_url in href
                else "anchor"
                if href.startswith("#")
                else "mailto"
                if href.startswith("mailto:")
                else "relative"
                if not href.startswith(("http://", "https://"))
                else "external"
            )
            entry = {"document": doc.key, "text": text[:80], "href": href, "kind": kind}
            rows.append(entry)
            if kind in {"external", "site"} and href.startswith(("http://", "https://")):
                url_docs.setdefault(href, []).append(doc.key)

    # Cap live checks to keep the command center snappy
    unique_urls = list(url_docs.keys())[:80]
    results: dict[str, dict[str, Any]] = {}
    for url in unique_urls:
        results[url] = _check_url(url)

    for row in rows:
        href = row["href"]
        if href in results:
            row.update({k: v for k, v in results[href].items() if k != "url"})
        elif row["kind"] in {"anchor", "mailto"}:
            row["status"] = "skipped"
        elif row["kind"] == "relative":
            # Local path existence for media/content-style links
            if href.startswith(("../media/", "./", "/media/")):
                local = resolve_local_image(href, Path(site.directory / row["document"]), site)
                row["status"] = "ok" if local and local.exists() else "missing-local"
            else:
                row["status"] = "unchecked-relative"
        else:
            row["status"] = "unchecked"

    counts = Counter(str(r.get("status", "unknown")) for r in rows)
    broken = [r for r in rows if r.get("status") in {"broken", "timeout", "error", "missing-local"}]
    return {
        "tool": "link-health",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {
            "links_found": len(rows),
            "unique_http_checked": len(unique_urls),
            "broken": counts.get("broken", 0),
            "timeout": counts.get("timeout", 0),
            "error": counts.get("error", 0),
            "ok": counts.get("ok", 0),
            "redirected": sum(1 for r in rows if r.get("redirected")),
            "skipped": counts.get("skipped", 0) + counts.get("unchecked", 0) + counts.get("unchecked-relative", 0),
        },
        "counts": dict(counts),
        "broken_links": broken[:50],
        "links": rows,
        "note": "HTTP checks use HEAD then GET fallback, max 80 unique URLs per run, 6s timeout.",
    }


# ---------------------------------------------------------------------------
# 4. Schema / structured data suggestions
# ---------------------------------------------------------------------------

def run_schema_suggest(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for doc in docs:
        suggestions: list[dict[str, Any]] = []
        headings = _headings(doc.markdown)
        h2_titles = [h for level, h in headings if level == 2]
        h3_titles = [h for level, h in headings if level == 3]

        # Article / BlogPosting baseline for posts
        if doc.collection == "posts":
            article = {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": doc.title,
                "description": _excerpt_of(doc) or doc.title,
                "mainEntityOfPage": f"{site.site_url.rstrip('/')}/{doc.slug}/",
            }
            suggestions.append(
                {
                    "type": "BlogPosting",
                    "reason": "Posts should expose Article/BlogPosting JSON-LD for rich results eligibility.",
                    "json_ld": article,
                }
            )
        else:
            suggestions.append(
                {
                    "type": "WebPage",
                    "reason": "Static pages benefit from WebPage + optional AboutPage/ContactPage subtypes.",
                    "json_ld": {
                        "@context": "https://schema.org",
                        "@type": "WebPage",
                        "name": doc.title,
                        "description": _excerpt_of(doc) or doc.title,
                        "url": f"{site.site_url.rstrip('/')}/{doc.slug}/",
                    },
                }
            )

        # FAQ detection
        faq_idx = next((i for i, t in enumerate(h2_titles) if re.search(r"faq|frequently asked", t, re.I)), None)
        if faq_idx is not None or any(re.search(r"\?", t) for t in h3_titles):
            questions = [t for t in h3_titles if t.endswith("?")] or [t for t in h3_titles[:6]]
            if questions:
                faq = {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [
                        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": f"See the “{q}” section in {doc.title}."}}
                        for q in questions[:8]
                    ],
                }
                suggestions.append(
                    {
                        "type": "FAQPage",
                        "reason": f"Detected FAQ-style headings ({len(questions)} questions). FAQ schema can unlock rich results.",
                        "json_ld": faq,
                    }
                )

        # HowTo detection
        numbered = re.findall(r"^\s*\d+\.\s+.+$", doc.markdown, re.M)
        if len(numbered) >= 3 or any(re.search(r"how to|step-by-step|checklist", t, re.I) for t in h2_titles):
            steps = [re.sub(r"^\s*\d+\.\s+", "", s).strip() for s in numbered[:12]]
            if steps:
                howto = {
                    "@context": "https://schema.org",
                    "@type": "HowTo",
                    "name": doc.title,
                    "step": [{"@type": "HowToStep", "position": i + 1, "text": step} for i, step in enumerate(steps)],
                }
                suggestions.append(
                    {
                        "type": "HowTo",
                        "reason": f"Detected ordered procedure ({len(steps)} steps). HowTo schema may apply if the page is truly instructional.",
                        "json_ld": howto,
                    }
                )

        cats = doc.metadata.get("categories") if isinstance(doc.metadata.get("categories"), list) else []
        if cats:
            crumbs = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": site.site_url},
                    {"@type": "ListItem", "position": 2, "name": str(cats[0]), "item": f"{site.site_url.rstrip('/')}/category/{cats[0]}/"},
                    {"@type": "ListItem", "position": 3, "name": doc.title, "item": f"{site.site_url.rstrip('/')}/{doc.slug}/"},
                ],
            }
            suggestions.append(
                {
                    "type": "BreadcrumbList",
                    "reason": "Category assignment allows breadcrumb structured data for SERP trails.",
                    "json_ld": crumbs,
                }
            )

        rows.append(
            {
                "document": doc.key,
                "collection": doc.collection,
                "title": doc.title,
                "suggestion_count": len(suggestions),
                "types": [s["type"] for s in suggestions],
                "suggestions": suggestions,
            }
        )

    type_counts: Counter[str] = Counter()
    for row in rows:
        type_counts.update(row["types"])
    return {
        "tool": "schema-suggest",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {"documents": len(rows), "types": dict(type_counts)},
        "documents": rows,
        "implementation_note": (
            "Suggestions are editorial. Inject JSON-LD via theme, SEO plugin REST meta, or a "
            "reviewed Markdown HTML block only after confirming the schema matches page content."
        ),
    }


# ---------------------------------------------------------------------------
# 5. Publish readiness (go-live checklist)
# ---------------------------------------------------------------------------

def run_publish_readiness(site: SiteConfig, target: Path | None, docs: list[Document]) -> dict[str, Any]:
    seo = run_seo_audit(site, target, docs)
    seo_by_doc = {r["document"]: r for r in seo["documents"]}
    rows: list[dict[str, Any]] = []

    for doc in docs:
        blockers: list[str] = []
        warnings: list[str] = []
        checklist: list[dict[str, Any]] = []
        seo_row = seo_by_doc.get(doc.key, {})
        words = _word_count(doc.markdown)
        excerpt = _excerpt_of(doc)
        external = [h for _, h in LINK_RE.findall(doc.markdown) if h.startswith(("http://", "https://")) and site.site_url not in h]
        internal = [
            h
            for _, h in LINK_RE.findall(doc.markdown)
            if h.startswith(("/", "wp://", "./", "../")) or (site.site_url and site.site_url in h)
        ]
        images = LOCAL_IMAGE_RE.findall(doc.markdown)

        def item(name: str, ok: bool, level: str, message: str) -> None:
            checklist.append({"name": name, "ok": ok, "level": level, "message": message})
            if not ok and level == "blocker":
                blockers.append(message)
            elif not ok:
                warnings.append(message)

        item("has-title", bool(doc.title and len(doc.title) >= 8), "blocker", "Title missing or too short")
        item("has-slug", bool(doc.slug), "blocker", "Slug missing")
        item("has-excerpt", 120 <= len(excerpt) <= 165, "blocker" if doc.collection == "posts" else "warning", f"Excerpt length {len(excerpt)} (want 120–165)")
        item("featured-image", _has_featured(doc), "warning", "No featured_image set")
        min_words = 800 if doc.collection == "posts" else 300
        item("word-count", words >= min_words, "blocker" if doc.collection == "posts" else "warning", f"{words} words (min {min_words})")
        item("seo-score", seo_row.get("score", 0) >= 70, "warning", f"SEO score {seo_row.get('score', 0)} (want ≥70)")
        item("has-image-in-body", len(images) >= 1 or doc.collection == "pages", "warning", "No body images")
        item("has-internal-link", len(internal) >= 1 or words < 500, "warning", "No internal links")
        item("has-external-link", len(external) >= 1 or words < 500, "warning", "No external/authority links")
        item("not-placeholder", "lorem ipsum" not in doc.markdown.lower() and "[IMAGE PROMPT" not in doc.markdown, "blocker", "Placeholder or IMAGE PROMPT still present")
        item("categories", bool(doc.metadata.get("categories")) or doc.collection != "posts", "warning", "Post has no categories")

        if blockers:
            readiness = "blocked"
        elif warnings:
            readiness = "almost"
        else:
            readiness = "ready"

        rows.append(
            {
                "document": doc.key,
                "collection": doc.collection,
                "status": doc.status,
                "title": doc.title,
                "readiness": readiness,
                "seo_score": seo_row.get("score"),
                "words": words,
                "blockers": blockers,
                "warnings": warnings,
                "checklist": checklist,
                "recommended_action": (
                    "Publish candidate — review once more then set status: publish"
                    if readiness == "ready" and doc.status in {"draft", "pending"}
                    else "Fix blockers before publish"
                    if readiness == "blocked"
                    else "Tighten warnings, then publish"
                    if readiness == "almost"
                    else "Already published — monitor and refresh"
                ),
            }
        )

    ready = [r for r in rows if r["readiness"] == "ready"]
    almost = [r for r in rows if r["readiness"] == "almost"]
    blocked = [r for r in rows if r["readiness"] == "blocked"]
    draft_ready = [r for r in ready if r["status"] in {"draft", "pending"}]
    return {
        "tool": "publish-readiness",
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(target) if target else "site",
        "summary": {
            "documents": len(rows),
            "ready": len(ready),
            "almost": len(almost),
            "blocked": len(blocked),
            "drafts_ready_to_publish": len(draft_ready),
            "published": sum(1 for r in rows if r["status"] == "publish"),
            "drafts": sum(1 for r in rows if r["status"] == "draft"),
        },
        "queue": {
            "publish_next": [{"document": r["document"], "title": r["title"], "seo_score": r["seo_score"]} for r in draft_ready[:15]],
            "almost": [{"document": r["document"], "warnings": r["warnings"][:3]} for r in almost[:15]],
            "blocked": [{"document": r["document"], "blockers": r["blockers"][:3]} for r in blocked[:15]],
        },
        "documents": rows,
        "seo_summary": seo["summary"],
    }


# ---------------------------------------------------------------------------
# Lightweight HTML reports (openable from CLI --open)
# ---------------------------------------------------------------------------

def write_tool_html(site_key: str, payload: dict[str, Any], report_path: Path) -> Path:
    output = report_path.with_suffix(".html")
    tool = payload.get("tool", "report")
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    safe = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    safe_site = json.dumps(site_key, ensure_ascii=False).replace("<", "\\u003c")
    title = {
        "seo-audit": "SEO Audit",
        "readability": "Readability",
        "link-health": "Link Health",
        "schema-suggest": "Schema Suggestions",
        "publish-readiness": "Publish Readiness",
        "featured-image-fixer": "Featured Image Fixer",
        "content-inventory": "Content Inventory",
        "editorial-calendar": "Editorial Calendar",
        "content-refresh": "Content Refresh",
    }.get(tool, tool)
    output.write_text(
        _HTML_SHELL.replace("__TITLE__", title).replace("__SITE__", safe_site).replace("__DATA__", safe).replace("__TOOL__", tool),
        encoding="utf-8",
    )
    return output


_HTML_SHELL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · Content Factory</title>
<style>
:root{--ink:#152019;--muted:#667269;--paper:#f3f6f2;--card:#fff;--line:#dce3dc;--green:#1d6b50;--amber:#d49a2a;--red:#c24b45;--blue:#3f6fbf}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif}
.shell{max-width:1200px;margin:auto;padding:28px}h1{font-size:clamp(26px,4vw,40px);letter-spacing:-.04em;margin:6px 0}
.eyebrow{font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--green)}
.sub{color:var(--muted)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:0 10px 28px rgba(20,40,30,.06)}
.kpi b{display:block;font-size:28px;letter-spacing:-.03em}.kpi span{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;border-top:1px solid var(--line);text-align:left;font-size:13px}
th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;background:#e8f2ec}
.pill.poor,.pill.blocked,.pill.difficult,.pill.broken{background:#fde8e6;color:var(--red)}
.pill.good,.pill.almost,.pill.standard,.pill.needs-work{background:#fff3db;color:#8a6200}
.pill.excellent,.pill.ready,.pill.easy,.pill.ok{background:#e5f6ea;color:var(--green)}
.muted{color:var(--muted);font-size:12px} code{font-size:12px}
</style>
</head>
<body>
<main class="shell">
  <div class="eyebrow">WordPress Content Factory</div>
  <h1 id="title">__TITLE__</h1>
  <div class="sub" id="sub"></div>
  <section class="kpis" id="kpis"></section>
  <section class="card" style="overflow:auto"><table><thead id="head"></thead><tbody id="body"></tbody></table>
  <div class="muted" id="foot" style="padding-top:10px"></div></section>
</main>
<script id="report" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('report').textContent), SITE=__SITE__, TOOL='__TOOL__';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.getElementById('sub').textContent=SITE+' · '+new Date(D.generated_at||Date.now()).toLocaleString();
const S=D.summary||{};
const kpiEntries=Object.entries(S).slice(0,8);
document.getElementById('kpis').innerHTML=kpiEntries.map(([k,v])=>`<div class="card kpi"><b>${esc(v)}</b><span>${esc(k.replaceAll('_',' '))}</span></div>`).join('')||'';
const docs=D.documents||D.links||D.broken_links||[];
function band(v){return `<span class="pill ${esc(String(v).toLowerCase())}">${esc(v)}</span>`}
let head='', rows='';
if(TOOL==='seo-audit'){
  head='<tr><th>Document</th><th>Score</th><th>Band</th><th>Focus</th><th>Issues</th><th>Words</th></tr>';
  rows=(D.documents||[]).slice().sort((a,b)=>a.score-b.score).map(d=>`<tr><td>${esc(d.document)}<div class="muted">${esc(d.title)}</div></td><td><b>${d.score}</b></td><td>${band(d.band)}</td><td>${esc(d.focus_keyword)}</td><td>${d.issue_count}</td><td>${d.words}</td></tr>`).join('');
}else if(TOOL==='readability'){
  head='<tr><th>Document</th><th>Flesch</th><th>Band</th><th>Avg sentence</th><th>Issues</th></tr>';
  rows=(D.documents||[]).map(d=>`<tr><td>${esc(d.document)}</td><td><b>${d.flesch_reading_ease}</b></td><td>${band(d.band)}</td><td>${d.avg_sentence_words}</td><td>${(d.issues||[]).map(esc).join('; ')||'—'}</td></tr>`).join('');
}else if(TOOL==='link-health'){
  head='<tr><th>Status</th><th>Code</th><th>Document</th><th>URL</th></tr>';
  const list=(D.broken_links&&D.broken_links.length?D.broken_links:D.links||[]).slice(0,200);
  rows=list.map(d=>`<tr><td>${band(d.status||'')}</td><td>${esc(d.code??'—')}</td><td>${esc(d.document)}</td><td><code>${esc(d.href||d.url||'')}</code></td></tr>`).join('');
}else if(TOOL==='schema-suggest'){
  head='<tr><th>Document</th><th>Types</th><th>Count</th></tr>';
  rows=(D.documents||[]).map(d=>`<tr><td>${esc(d.document)}</td><td>${(d.types||[]).map(t=>band(t)).join(' ')}</td><td>${d.suggestion_count}</td></tr>`).join('');
}else if(TOOL==='publish-readiness'){
  head='<tr><th>Document</th><th>Readiness</th><th>Status</th><th>SEO</th><th>Action</th></tr>';
  rows=(D.documents||[]).map(d=>`<tr><td>${esc(d.document)}<div class="muted">${esc(d.title)}</div></td><td>${band(d.readiness)}</td><td>${esc(d.status)}</td><td>${esc(d.seo_score)}</td><td>${esc(d.recommended_action)}</td></tr>`).join('');
}else if(TOOL==='featured-image-fixer'){
  head='<tr><th>Document</th><th>Action</th><th>Featured image</th><th>Source</th></tr>';
  rows=(D.documents||[]).map(d=>`<tr><td>${esc(d.document)}</td><td>${band(d.action||'')}</td><td><code>${esc(d.featured_image||d.message||'')}</code></td><td>${esc(d.source||'')}</td></tr>`).join('');
}else{
  head='<tr><th>Key</th><th>Value</th></tr>';
  rows=`<tr><td colspan="2"><pre style="white-space:pre-wrap">${esc(JSON.stringify(D,null,2).slice(0,5000))}</pre></td></tr>`;
}
document.getElementById('head').innerHTML=head;
document.getElementById('body').innerHTML=rows||'<tr><td colspan="6" class="muted">No rows</td></tr>';
document.getElementById('foot').textContent='Report tool: '+TOOL+' · '+(docs.length||0)+' primary rows';
</script>
</body>
</html>
"""
