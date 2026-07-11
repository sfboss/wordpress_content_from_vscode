from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter
from bs4 import BeautifulSoup

from .config import SiteConfig
from .content import load_documents, load_term_files, resolve_local_image
from .errors import ValidationError, WordPressError
from .markdown_engine import html_to_markdown, render_document, render_markdown
from .models import Document, PlanItem, SyncResult
from .state import StateStore
from .utils import slugify, stable_hash
from .wordpress import WordPressClient, rendered_value


def _normalize_html(value: str) -> str:
    """Normalize harmless serializer differences while preserving structure and code whitespace."""
    return str(BeautifulSoup(value or "", "html.parser")).strip()


class SiteSync:
    def __init__(self, site: SiteConfig):
        self.site = site
        self.client = WordPressClient(site)
        self.state = StateStore.load(site.state_path)

    def doctor(self) -> dict[str, Any]:
        discovery = self.client.discover()
        namespaces = discovery.get("namespaces", [])
        if "wp/v2" not in namespaces:
            raise WordPressError("The site did not advertise the wp/v2 REST namespace.")
        user = self.client.current_user()
        return {
            "site": self.site.site_url,
            "wordpress_name": discovery.get("name"),
            "authenticated_user": user.get("name") or user.get("slug"),
            "user_id": user.get("id"),
            "can_edit": bool(user.get("capabilities", {}).get("edit_posts")),
            "rest_api": self.site.api_base,
        }

    def lint(self) -> list[str]:
        issues: list[str] = []
        documents = load_documents(self.site)
        if not documents:
            issues.append("No Markdown documents found in content/posts or content/pages.")
        for document in documents:
            if not document.markdown.strip():
                issues.append(f"{document.key}: body is empty")
            if not document.metadata.get("excerpt") and document.collection == "posts":
                issues.append(f"{document.key}: warning: excerpt/meta description is empty")
            soup = BeautifulSoup(render_markdown(document.markdown), "html.parser")
            for link in soup.find_all("a"):
                href = str(link.get("href") or "")
                if href.split("#", 1)[0].lower().endswith(".md"):
                    issues.append(
                        f"{document.key}: warning: local Markdown link is not rewritten to a WordPress permalink: {href}"
                    )
            for img in soup.find_all("img"):
                src = str(img.get("src") or "").strip()
                alt = str(img.get("alt") or "").strip()
                local = resolve_local_image(src, document.path, self.site) if src else None
                configured = document.metadata.get("images") or {}
                details = configured.get(src) or (configured.get(local.name) if local else None)
                configured_alt = details if isinstance(details, str) else (details or {}).get("alt", "")
                effective_alt = str(configured_alt or alt).strip()
                if not src:
                    issues.append(f"{document.key}: image has no src")
                elif local and not local.exists():
                    issues.append(f"{document.key}: missing image: {src}")
                if not effective_alt or effective_alt.lower() in {"image", "photo", "picture", "screenshot"}:
                    issues.append(f"{document.key}: image needs specific alt text: {src}")
            featured = document.metadata.get("featured_image")
            if featured:
                local = resolve_local_image(str(featured), document.path, self.site)
                configured = document.metadata.get("images") or {}
                details = configured.get(str(featured)) or (configured.get(local.name) if local else None)
                configured_alt = details if isinstance(details, str) else (details or {}).get("alt", "")
                if local is None or not local.exists():
                    issues.append(f"{document.key}: missing featured image: {featured}")
                if not str(configured_alt).strip():
                    issues.append(f"{document.key}: featured image needs alt text in frontmatter images: {featured}")
            if document.metadata.get("seo_title") or document.metadata.get("meta_description"):
                issues.append(
                    f"{document.key}: warning: plugin SEO fields are documented but not sent without a configured REST adapter"
                )
        return issues

    def plan(self) -> list[PlanItem]:
        plan: list[PlanItem] = []
        for document in load_documents(self.site):
            saved = self.state.document(document.key)
            existing: dict[str, Any] | None = None
            if saved.get("wp_id"):
                try:
                    existing = self.client.get(document.endpoint, int(saved["wp_id"]))
                except WordPressError:
                    existing = None
            if existing is None:
                existing = self.client.find_by_slug(document.endpoint, document.slug)
            if existing is None:
                plan.append(PlanItem(document, "create", None, "slug does not exist remotely"))
                continue
            if not saved:
                plan.append(PlanItem(document, "update", existing, "adopting exact remote slug"))
                continue
            local_changed = saved.get("local_hash") != document.source_hash
            remote_changed = bool(
                saved.get("remote_modified")
                and existing.get("modified_gmt")
                and saved.get("remote_modified") != existing.get("modified_gmt")
            )
            if not local_changed:
                reason = "remote changed; pull before editing" if remote_changed else "unchanged"
                plan.append(PlanItem(document, "remote-changed" if remote_changed else "noop", existing, reason))
            elif remote_changed:
                plan.append(PlanItem(document, "conflict", existing, "both local and remote changed"))
            else:
                plan.append(PlanItem(document, "update", existing, "local source changed"))
        return plan

    def _sync_terms(self) -> dict[str, dict[str, int]]:
        resolved: dict[str, dict[str, int]] = {"categories": {}, "tags": {}}
        definitions = {
            taxonomy: load_term_files(self.site, taxonomy) for taxonomy in ("categories", "tags")
        }
        documents = load_documents(self.site)
        for taxonomy in ("categories", "tags"):
            defined = {term["slug"] for term in definitions[taxonomy]}
            for document in documents:
                if document.collection != "posts":
                    continue
                for raw in document.metadata.get(taxonomy, []) or []:
                    slug = slugify(str(raw))
                    if slug and slug not in defined:
                        definitions[taxonomy].append(
                            {"name": str(raw).replace("-", " ").title(), "slug": slug, "description_markdown": "", "parent": None}
                        )
                        defined.add(slug)

        for taxonomy in ("tags", "categories"):
            pending = list(definitions[taxonomy])
            attempts = 0
            while pending and attempts <= len(pending) + 2:
                attempts += 1
                remaining: list[dict[str, Any]] = []
                for term in pending:
                    parent_slug = slugify(str(term.get("parent") or ""))
                    if taxonomy == "categories" and parent_slug and parent_slug not in resolved[taxonomy]:
                        remaining.append(term)
                        continue
                    payload: dict[str, Any] = {
                        "name": term["name"],
                        "slug": term["slug"],
                        "description": render_markdown(term.get("description_markdown", "")),
                    }
                    if taxonomy == "categories" and parent_slug:
                        payload["parent"] = resolved[taxonomy][parent_slug]
                    _, remote = self.client.upsert_term(taxonomy, payload)
                    resolved[taxonomy][term["slug"]] = int(remote["id"])
                    self.state.set_term(
                        taxonomy,
                        term["slug"],
                        {"wp_id": int(remote["id"]), "modified": datetime.now(UTC).isoformat()},
                    )
                if len(remaining) == len(pending):
                    missing = ", ".join(term["slug"] for term in remaining)
                    raise ValidationError(f"Unresolved category parent cycle or missing parent: {missing}")
                pending = remaining
        return resolved

    def _payload(
        self,
        document: Document,
        html: str,
        featured_media: int,
        terms: dict[str, dict[str, int]],
    ) -> dict[str, Any]:
        metadata = document.metadata
        payload: dict[str, Any] = {
            "title": document.title,
            "slug": document.slug,
            "status": document.status,
            "content": html,
        }
        optional = {
            "excerpt": metadata.get("excerpt"),
            "date": metadata.get("date"),
            "comment_status": metadata.get("comment_status"),
            "ping_status": metadata.get("ping_status"),
            "template": metadata.get("template"),
            "menu_order": metadata.get("menu_order"),
            "format": metadata.get("format"),
            "sticky": metadata.get("sticky"),
            "password": metadata.get("password"),
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        if hasattr(payload.get("date"), "isoformat"):
            payload["date"] = payload["date"].isoformat()
        if featured_media:
            payload["featured_media"] = featured_media
        if document.collection == "posts":
            for taxonomy in ("categories", "tags"):
                requested = [slugify(str(value)) for value in metadata.get(taxonomy, []) or []]
                payload[taxonomy] = [terms[taxonomy][slug] for slug in requested]
        if metadata.get("rest_meta"):
            if not isinstance(metadata["rest_meta"], dict):
                raise ValidationError(f"{document.path}: rest_meta must be a mapping")
            payload["meta"] = metadata["rest_meta"]
        return payload

    def push(self, *, force: bool = False) -> list[SyncResult]:
        issues = [issue for issue in self.lint() if "warning:" not in issue]
        if issues:
            raise ValidationError("Lint failed:\n- " + "\n- ".join(issues))
        plan = self.plan()
        conflicts = [item.document.key for item in plan if item.action == "conflict"]
        if conflicts and not force:
            raise ValidationError(
                "Push stopped because local and WordPress both changed:\n- "
                + "\n- ".join(conflicts)
                + "\nRun Pull safe remote changes, reconcile incoming files, then push."
            )
        terms = self._sync_terms()
        results: list[SyncResult] = []
        for item in plan:
            document = item.document
            if item.action in {"noop", "remote-changed"}:
                results.append(
                    SyncResult(document.key, item.action, True, item.reason, int(item.remote["id"]), item.remote.get("link"))
                )
                continue
            rendered = render_document(document, self.client, self.state, self.site)
            payload = self._payload(document, rendered.html, rendered.featured_media, terms)
            action, remote = self.client.upsert_content(document.endpoint, payload, item.remote)
            confirmed = self.client.get(document.endpoint, int(remote["id"]))
            if confirmed.get("slug") != document.slug:
                raise WordPressError(f"Verification failed for {document.key}: remote slug differs")
            expected_html_hash = stable_hash(_normalize_html(rendered.html))
            remote_html_hash = stable_hash(_normalize_html(rendered_value(confirmed.get("content"))))
            content_match = expected_html_hash == remote_html_hash
            self.state.set_document(
                document.key,
                {
                    "wp_id": int(confirmed["id"]),
                    "endpoint": document.endpoint,
                    "slug": confirmed.get("slug"),
                    "local_hash": document.source_hash,
                    "remote_modified": confirmed.get("modified_gmt"),
                    "status": confirmed.get("status"),
                    "url": confirmed.get("link"),
                    "media_ids": rendered.media_ids,
                    "expected_html_hash": expected_html_hash,
                    "remote_html_hash": remote_html_hash,
                    "content_match": content_match,
                    "synced_at": datetime.now(UTC).isoformat(),
                },
            )
            self.state.save()
            results.append(
                SyncResult(
                    document.key,
                    action,
                    content_match,
                    "REST content read-back confirmed"
                    if content_match
                    else "WordPress changed or sanitized the submitted HTML; inspect the live record",
                    int(confirmed["id"]),
                    confirmed.get("link"),
                )
            )
        self.state.save()
        return results

    def verify(self) -> list[SyncResult]:
        documents = {doc.key: doc for doc in load_documents(self.site)}
        results: list[SyncResult] = []
        for key, saved in sorted(self.state.data["documents"].items()):
            document = documents.get(key)
            if document is None:
                results.append(SyncResult(key, "verify", False, "local Markdown file is missing", saved.get("wp_id"), saved.get("url")))
                continue
            try:
                remote = self.client.get(saved["endpoint"], int(saved["wp_id"]))
                failures: list[str] = []
                if remote.get("slug") != document.slug:
                    failures.append("slug")
                if remote.get("status") != document.status:
                    failures.append("status")
                if rendered_value(remote.get("title")).strip() != document.title:
                    failures.append("title")
                if saved.get("expected_html_hash"):
                    current_html_hash = stable_hash(_normalize_html(rendered_value(remote.get("content"))))
                    if current_html_hash != saved["expected_html_hash"]:
                        failures.append("content HTML")
                status_code = None
                if self.site.verify_public_urls and document.status == "publish" and remote.get("link"):
                    status_code = self.client.public_head(remote["link"])
                    if status_code < 200 or status_code >= 400:
                        failures.append(f"public HTTP {status_code}")
                message = "confirmed" if not failures else "mismatch: " + ", ".join(failures)
                results.append(SyncResult(key, "verify", not failures, message, int(remote["id"]), remote.get("link")))
            except WordPressError as exc:
                results.append(SyncResult(key, "verify", False, str(exc), saved.get("wp_id"), saved.get("url")))
        return results

    def _all_remote(self, endpoint: str) -> list[dict[str, Any]]:
        rows: dict[int, dict[str, Any]] = {}
        for status in ("publish", "draft", "pending", "private", "future"):
            try:
                for row in self.client.list_all(endpoint, {"context": "edit", "status": status, "orderby": "id"}):
                    rows[int(row["id"])] = row
            except WordPressError:
                continue
        return list(rows.values())

    def pull(self) -> list[SyncResult]:
        current = {doc.key: doc for doc in load_documents(self.site)}
        key_by_remote_id = {
            (str(saved.get("endpoint")), int(saved["wp_id"])): key
            for key, saved in self.state.data["documents"].items()
            if saved.get("endpoint") and saved.get("wp_id")
        }
        results: list[SyncResult] = []
        touched: dict[str, dict[str, Any]] = {}
        term_slugs: dict[str, dict[int, str]] = {}
        for taxonomy in ("categories", "tags"):
            term_slugs[taxonomy] = {
                int(term["id"]): str(term["slug"])
                for term in self.client.list_all(taxonomy, {"context": "edit"})
            }
        for collection, endpoint in (("posts", "posts"), ("pages", "pages")):
            for remote in self._all_remote(endpoint):
                slug = str(remote.get("slug") or f"wordpress-{remote['id']}")
                known_key = key_by_remote_id.get((endpoint, int(remote["id"])))
                relative = Path(known_key) if known_key else Path("content") / collection / f"{slug}.md"
                key = relative.as_posix()
                destination = self.site.directory / relative
                metadata: dict[str, Any] = {
                    "title": rendered_value(remote.get("title")),
                    "slug": slug,
                    "status": remote.get("status", "draft"),
                    "wp_id": int(remote["id"]),
                }
                excerpt = rendered_value(remote.get("excerpt")).strip()
                if excerpt:
                    metadata["excerpt"] = BeautifulSoup(excerpt, "html.parser").get_text(" ", strip=True)
                if collection == "posts":
                    metadata["categories"] = [term_slugs["categories"].get(int(value), str(value)) for value in remote.get("categories", [])]
                    metadata["tags"] = [term_slugs["tags"].get(int(value), str(value)) for value in remote.get("tags", [])]
                source = frontmatter.dumps(frontmatter.Post(html_to_markdown(rendered_value(remote.get("content"))), **metadata)) + "\n"

                local = current.get(key)
                saved = self.state.document(key)
                safe = local is None or (saved and saved.get("local_hash") == local.source_hash)
                if safe:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(source, encoding="utf-8")
                    action = "imported" if local is None else "pulled"
                    target_key = key
                else:
                    incoming = self.site.incoming_dir / collection / f"{slug}.md"
                    incoming.parent.mkdir(parents=True, exist_ok=True)
                    incoming.write_text(source, encoding="utf-8")
                    action = "conflict"
                    target_key = incoming.relative_to(self.site.directory).as_posix()
                touched[key] = {"remote": remote, "safe": safe}
                results.append(SyncResult(target_key, action, safe, "remote snapshot written", int(remote["id"]), remote.get("link")))

        refreshed = {doc.key: doc for doc in load_documents(self.site)}
        for key, info in touched.items():
            if not info["safe"] or key not in refreshed:
                continue
            remote = info["remote"]
            self.state.set_document(
                key,
                {
                    "wp_id": int(remote["id"]),
                    "endpoint": "posts" if "/posts/" in f"/{key}" else "pages",
                    "slug": remote.get("slug"),
                    "local_hash": refreshed[key].source_hash,
                    "remote_modified": remote.get("modified_gmt"),
                    "status": remote.get("status"),
                    "url": remote.get("link"),
                    "synced_at": datetime.now(UTC).isoformat(),
                },
            )
        self.state.save()
        return results
