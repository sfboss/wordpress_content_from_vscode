from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import frontmatter

from .config import SiteConfig
from .errors import ValidationError
from .models import Document
from .utils import sha256_bytes, slugify, stable_hash, title_from_filename


COLLECTIONS = {
    "posts": {"directory": "posts", "endpoint": "posts"},
    "pages": {"directory": "pages", "endpoint": "pages"},
}

LOCAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")


def resolve_local_image(src: str, markdown_path: Path, site: SiteConfig) -> Path | None:
    src = src.strip().strip("<>")
    if src.startswith(("http://", "https://", "data:", "//")):
        return None
    src = src.split("#", 1)[0].split("?", 1)[0]
    if src.startswith("@media/"):
        return site.content_dir / "media" / src.removeprefix("@media/")
    if src.startswith("/media/"):
        return site.content_dir / "media" / src.removeprefix("/media/")
    return (markdown_path.parent / src).resolve()


def _source_hash(path: Path, markdown: str, site: SiteConfig) -> str:
    images: list[dict[str, str]] = []
    for src in LOCAL_IMAGE_RE.findall(markdown):
        local = resolve_local_image(src, path, site)
        if local and local.exists() and local.is_file():
            images.append({"path": str(local), "sha256": sha256_bytes(local.read_bytes())})
        elif local:
            images.append({"path": str(local), "sha256": "MISSING"})
    return stable_hash({"source": path.read_text(encoding="utf-8"), "images": images})


def load_documents(site: SiteConfig) -> list[Document]:
    documents: list[Document] = []
    seen_slugs: set[tuple[str, str]] = set()
    for collection, spec in COLLECTIONS.items():
        directory = site.content_dir / spec["directory"]
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            post = frontmatter.load(path)
            metadata = dict(post.metadata)
            title = str(metadata.get("title") or title_from_filename(path)).strip()
            slug = slugify(str(metadata.get("slug") or path.stem))
            status = str(metadata.get("status") or site.default_status)
            if status not in {"draft", "pending", "private", "publish", "future"}:
                raise ValidationError(f"{path}: unsupported status '{status}'")
            if not title or not slug:
                raise ValidationError(f"{path}: title and slug cannot be empty")
            identity = (collection, slug)
            if identity in seen_slugs:
                raise ValidationError(f"Duplicate {collection} slug '{slug}'")
            seen_slugs.add(identity)
            key = path.relative_to(site.directory).as_posix()
            documents.append(
                Document(
                    key=key,
                    collection=collection,
                    endpoint=spec["endpoint"],
                    path=path,
                    metadata=metadata,
                    markdown=post.content,
                    title=title,
                    slug=slug,
                    status=status,
                    source_hash=_source_hash(path, post.content, site),
                )
            )
    return documents


def load_term_files(site: SiteConfig, taxonomy: str) -> list[dict[str, Any]]:
    directory = site.content_dir / taxonomy
    terms: list[dict[str, Any]] = []
    if not directory.exists():
        return terms
    for path in sorted(directory.rglob("*.md")):
        post = frontmatter.load(path)
        name = str(post.metadata.get("name") or post.metadata.get("title") or title_from_filename(path))
        slug = slugify(str(post.metadata.get("slug") or path.stem))
        terms.append(
            {
                "name": name,
                "slug": slug,
                "description_markdown": post.content.strip(),
                "parent": post.metadata.get("parent"),
                "path": path,
            }
        )
    return terms

