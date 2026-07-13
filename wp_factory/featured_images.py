"""Featured image fixer — mutate Markdown frontmatter safely and idempotently.

Workflow fit:
- Reads posts/pages the same way other tools do.
- Repairs common YAML breakage (unquoted scalars containing colons) so later
  lint/seo-audit/push see the same documents.
- Chooses the first usable local image (body → images map → media matching slug).
- Writes `featured_image` + `images` alt/title metadata without clobbering
  existing good values.
- Skips documents that already have a resolvable featured image (idempotent).
- Emits a structured report so runs leave a clear audit trail of what changed.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter

from .config import SiteConfig
from .content import LOCAL_IMAGE_RE, resolve_local_image
from .utils import slugify, title_from_filename

# Frontmatter keys whose values often contain ":" and break unquoted YAML
_QUOTE_KEYS = {
    "title",
    "excerpt",
    "meta_description",
    "seo_description",
    "description",
    "caption",
    "alt",
    "seo_title",
    "focus_keyword",
    "focus_keyphrase",
    "primary_keyword",
    "keyword",
}

_MD_IMAGE_ALT_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"']([^\"']*)[\"'])?\)")


def repair_frontmatter_yaml(raw: str) -> tuple[str, bool]:
    """Quote common unquoted scalars that contain ':' so frontmatter can parse."""
    if not raw.startswith("---"):
        return raw, False
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return raw, False
    fm_block = parts[1]
    body = parts[2]
    changed = False
    out_lines: list[str] = []
    for line in fm_block.splitlines():
        # Match "  key: value" or "key: value" (not nested list items only)
        m = re.match(r"^([ \t]*)([A-Za-z0-9_]+):\s+(.*)$", line)
        if not m:
            out_lines.append(line)
            continue
        indent, key, value = m.group(1), m.group(2), m.group(3)
        if key not in _QUOTE_KEYS:
            out_lines.append(line)
            continue
        stripped = value.strip()
        if not stripped or stripped in {"|", ">", ">-", "|-"}:
            out_lines.append(line)
            continue
        if stripped[0] in {'"', "'", "[", "{", "|", ">"}:
            out_lines.append(line)
            continue
        # Needs quoting if colon/hash would confuse YAML, or leading special chars
        if ":" in stripped or stripped.startswith(("#", "*", "&", "!", "%", "@", "`")):
            escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
            out_lines.append(f'{indent}{key}: "{escaped}"')
            changed = True
        else:
            out_lines.append(line)
    if not changed:
        return raw, False
    repaired = "---\n" + "\n".join(out_lines) + "\n---" + body
    return repaired, True


def load_markdown_document(path: Path) -> tuple[frontmatter.Post, str, bool]:
    """Load a Markdown file, repairing YAML if needed. Returns (post, raw_text, repaired)."""
    raw = path.read_text(encoding="utf-8")
    repaired = False
    try:
        post = frontmatter.loads(raw)
        return post, raw, False
    except Exception:
        fixed, repaired = repair_frontmatter_yaml(raw)
        post = frontmatter.loads(fixed)
        return post, fixed if repaired else raw, repaired


def _media_rel_from_doc(doc_path: Path, media_file: Path, site: SiteConfig) -> str:
    """Prefer ../media/name for posts/pages under content/."""
    try:
        rel = Path(media_file).resolve().relative_to((site.content_dir / "media").resolve())
        # From content/posts or content/pages → ../media/<file>
        return f"../media/{rel.as_posix()}"
    except ValueError:
        try:
            return Path(os_path_rel(doc_path.parent, media_file))
        except Exception:
            return media_file.name


def os_path_rel(start: Path, target: Path) -> str:
    return Path(target).resolve().relative_to(start.resolve()).as_posix()


def _body_images(markdown: str) -> list[tuple[str, str, str]]:
    """Return list of (alt, src, title) from Markdown image syntax, in order."""
    found: list[tuple[str, str, str]] = []
    for m in _MD_IMAGE_ALT_RE.finditer(markdown):
        found.append((m.group(1) or "", m.group(2).strip(), m.group(3) or ""))
    # Fallback to simple src finder if alt regex misses any
    for src in LOCAL_IMAGE_RE.findall(markdown):
        if not any(src == item[1] for item in found):
            found.append(("", src, ""))
    return found


def _candidate_paths(
    site: SiteConfig,
    doc_path: Path,
    post: frontmatter.Post,
) -> list[dict[str, Any]]:
    """Ordered candidates: body images, images map, media files matching slug."""
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(src: str, alt: str = "", title: str = "", caption: str = "", source: str = "") -> None:
        local = resolve_local_image(src, doc_path, site)
        if local is None or not local.exists() or not local.is_file():
            return
        key = str(local.resolve())
        if key in seen:
            return
        seen.add(key)
        rel = _media_rel_from_doc(doc_path, local, site)
        candidates.append(
            {
                "src": rel,
                "absolute": local,
                "alt": alt.strip(),
                "title": title.strip(),
                "caption": caption.strip(),
                "source": source,
            }
        )

    for alt, src, title in _body_images(post.content):
        if src.startswith(("http://", "https://", "data:", "//")):
            continue
        add(src, alt=alt, title=title, source="body")

    images_meta = post.metadata.get("images")
    if isinstance(images_meta, dict):
        # Prefer -01 / first insertion order; python 3.7+ dicts preserve order
        for src, details in images_meta.items():
            if not isinstance(src, str):
                continue
            alt = title = caption = ""
            if isinstance(details, str):
                alt = details
            elif isinstance(details, dict):
                alt = str(details.get("alt") or "")
                title = str(details.get("title") or "")
                caption = str(details.get("caption") or "")
            add(src, alt=alt, title=title, caption=caption, source="images-map")

    # Media library files named like <slug>-01.jpg
    slug = slugify(str(post.metadata.get("slug") or doc_path.stem))
    media_dir = site.content_dir / "media"
    if media_dir.exists():
        # Prefer -01, then -02, etc., then bare slug match
        ranked: list[Path] = []
        for path in sorted(media_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                continue
            stem = path.stem.lower()
            if stem == slug or stem.startswith(slug + "-") or stem.startswith(slug.replace("-", "_") + "-"):
                ranked.append(path)
        ranked.sort(key=lambda p: (0 if re.search(r"-0*1$", p.stem) else 1, p.name))
        for path in ranked:
            rel = f"../media/{path.name}"
            add(rel, alt=title_from_filename(path), title=title_from_filename(path), source="media-slug-match")

    return candidates


def _ensure_images_meta(post: frontmatter.Post, src: str, alt: str, title: str, caption: str) -> None:
    images = post.metadata.get("images")
    if not isinstance(images, dict):
        images = {}
    existing = images.get(src)
    if isinstance(existing, dict):
        block = dict(existing)
    elif isinstance(existing, str) and existing.strip():
        block = {"alt": existing}
    else:
        block = {}
    if not str(block.get("alt") or "").strip():
        block["alt"] = alt or title or "Featured image"
    if title and not str(block.get("title") or "").strip():
        block["title"] = title
    if caption and not str(block.get("caption") or "").strip():
        block["caption"] = caption
    images[src] = block
    post.metadata["images"] = images


def write_post(path: Path, post: frontmatter.Post) -> None:
    """Serialize frontmatter with safe YAML for long strings."""
    # Prefer block/literal for long excerpts via yaml dump through frontmatter
    handler = frontmatter.YAMLHandler()
    # Ensure multi-line safety: frontmatter dumps with default yaml
    text = frontmatter.dumps(post, handler=handler, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def fix_featured_images(
    site: SiteConfig,
    target: Path | None = None,
    *,
    apply: bool = True,
    collections: tuple[str, ...] = ("posts", "pages"),
) -> dict[str, Any]:
    """Set missing featured_image fields. apply=False is dry-run only."""
    rows: list[dict[str, Any]] = []
    roots: list[Path] = []
    for name in collections:
        directory = site.content_dir / name
        if directory.exists():
            roots.append(directory)

    files: list[Path] = []
    if target:
        target = target.resolve()
        if target.is_file() and target.suffix == ".md":
            files = [target]
        elif target.is_dir():
            files = sorted(p for p in target.rglob("*.md") if p.name.lower() != "readme.md")
        else:
            files = []
    else:
        for root in roots:
            files.extend(sorted(p for p in root.rglob("*.md") if p.name.lower() != "readme.md"))

    counts = {
        "scanned": 0,
        "already_ok": 0,
        "updated": 0,
        "would_update": 0,
        "yaml_repaired": 0,
        "no_candidate": 0,
        "parse_error": 0,
        "skipped": 0,
    }

    for path in files:
        counts["scanned"] += 1
        rel = path.relative_to(site.directory).as_posix()
        try:
            post, _raw, repaired = load_markdown_document(path)
        except Exception as exc:  # noqa: BLE001
            counts["parse_error"] += 1
            rows.append(
                {
                    "document": rel,
                    "action": "parse-error",
                    "message": str(exc)[:200],
                }
            )
            continue

        if repaired:
            counts["yaml_repaired"] += 1
            if apply:
                # Persist repaired YAML even if featured already set so tools can load the file.
                write_post(path, post)
                # Reload cleanly
                post, _, _ = load_markdown_document(path)

        existing = post.metadata.get("featured_image")
        if existing:
            local = resolve_local_image(str(existing), path, site)
            if local and local.exists():
                # Ensure alt metadata exists for lint/SEO
                images = post.metadata.get("images") if isinstance(post.metadata.get("images"), dict) else {}
                details = images.get(str(existing)) if isinstance(images, dict) else None
                alt_ok = False
                if isinstance(details, str) and details.strip():
                    alt_ok = True
                elif isinstance(details, dict) and str(details.get("alt") or "").strip():
                    alt_ok = True
                if alt_ok and not repaired:
                    counts["already_ok"] += 1
                    rows.append(
                        {
                            "document": rel,
                            "action": "already-ok",
                            "featured_image": str(existing),
                            "source": "existing",
                        }
                    )
                    continue
                # Fill missing alt only
                if not alt_ok:
                    _ensure_images_meta(
                        post,
                        str(existing),
                        alt=title_from_filename(local),
                        title=title_from_filename(local),
                        caption="",
                    )
                    if apply:
                        write_post(path, post)
                        counts["updated"] += 1
                        action = "updated-alt"
                    else:
                        counts["would_update"] += 1
                        action = "would-update-alt"
                    rows.append(
                        {
                            "document": rel,
                            "action": action,
                            "featured_image": str(existing),
                            "source": "existing",
                            "yaml_repaired": repaired,
                        }
                    )
                    continue
                if repaired:
                    counts["already_ok"] += 1
                    rows.append(
                        {
                            "document": rel,
                            "action": "yaml-repaired-already-ok",
                            "featured_image": str(existing),
                            "yaml_repaired": True,
                        }
                    )
                    continue
            # Existing path broken — fall through to pick a new candidate

        candidates = _candidate_paths(site, path, post)
        if not candidates:
            counts["no_candidate"] += 1
            rows.append(
                {
                    "document": rel,
                    "action": "no-candidate",
                    "message": "No local body image, images map entry, or media file matching slug.",
                    "yaml_repaired": repaired,
                }
            )
            continue

        pick = candidates[0]
        post.metadata["featured_image"] = pick["src"]
        _ensure_images_meta(
            post,
            pick["src"],
            alt=pick["alt"] or title_from_filename(pick["absolute"]),
            title=pick["title"] or title_from_filename(pick["absolute"]),
            caption=pick["caption"],
        )
        if apply:
            write_post(path, post)
            counts["updated"] += 1
            action = "set-featured-image"
        else:
            counts["would_update"] += 1
            action = "would-set-featured-image"
        rows.append(
            {
                "document": rel,
                "action": action,
                "featured_image": pick["src"],
                "source": pick["source"],
                "alt": pick["alt"] or title_from_filename(pick["absolute"]),
                "yaml_repaired": repaired,
                "candidates_considered": len(candidates),
            }
        )

    return {
        "tool": "featured-image-fixer",
        "generated_at": datetime.now(UTC).isoformat(),
        "apply": apply,
        "target": str(target) if target else "site",
        "summary": counts,
        "documents": rows,
        "workflow_notes": [
            "Idempotent: documents with a valid featured_image are left alone (or only get missing alt).",
            "Selection order: first body image → first images-map local file → media file matching slug-01.",
            "YAML scalars containing colons are auto-quoted so seo-audit/lint/push can load the file.",
            "Push still uploads featured_image through the existing markdown_engine path.",
            "Re-run seo-audit / publish-readiness after this tool to confirm featured-image checks pass.",
        ],
    }


def run_featured_image_fixer(site: SiteConfig, target: Path | None = None) -> dict[str, Any]:
    """Tool entrypoint — always applies fixes (command-center default)."""
    return fix_featured_images(site, target, apply=True)
