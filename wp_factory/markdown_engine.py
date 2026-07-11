from __future__ import annotations

import html
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from PIL import Image, ImageOps

from .config import SiteConfig
from .content import resolve_local_image
from .errors import ValidationError
from .models import Document
from .state import StateStore
from .utils import sha256_bytes, title_from_filename
from .wordpress import WordPressClient


def markdown_renderer() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"html": True, "linkify": True})
        .enable("table")
        .enable("strikethrough")
        .use(footnote_plugin)
        .use(tasklists_plugin, enabled=True, label=True)
        .use(deflist_plugin)
        .use(attrs_plugin)
    )


def render_markdown(value: str) -> str:
    return markdown_renderer().render(value)


@dataclass
class RenderedDocument:
    html: str
    featured_media: int = 0
    media_ids: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _metadata_for_image(document: Document, src: str, path: Path) -> dict[str, Any]:
    configured = document.metadata.get("images") or {}
    if not isinstance(configured, dict):
        raise ValidationError(f"{document.path}: frontmatter 'images' must be a mapping")
    for key in (src, unquote(src), path.name, path.stem):
        value = configured.get(key)
        if isinstance(value, str):
            return {"alt": value}
        if isinstance(value, dict):
            return dict(value)
    return {}


def _stage_image(path: Path, site: SiteConfig) -> tuple[Path, str]:
    if not path.exists() or not path.is_file():
        raise ValidationError(f"Referenced image does not exist: {path}")
    digest = sha256_bytes(path.read_bytes())
    site.media_out_dir.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    raster = suffix in {".jpg", ".jpeg", ".png", ".webp"}
    if not raster:
        output = site.media_out_dir / f"{path.stem}-{digest[:10]}{suffix}"
        if not output.exists():
            shutil.copy2(path, output)
        return output, digest

    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.width > site.media.max_width:
            ratio = site.media.max_width / image.width
            image = image.resize((site.media.max_width, round(image.height * ratio)), Image.Resampling.LANCZOS)
        if site.media.convert_to_webp:
            output_suffix = ".webp"
        else:
            output_suffix = ".jpg" if suffix == ".jpeg" else suffix
        output = site.media_out_dir / f"{path.stem}-{digest[:10]}{output_suffix}"
        if not output.exists():
            if output_suffix in {".jpg", ".jpeg"}:
                if image.mode not in {"RGB", "L"}:
                    background = Image.new("RGB", image.size, "white")
                    if "A" in image.getbands():
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image)
                    image = background
                image.save(output, quality=site.media.jpeg_quality, optimize=True)
            elif output_suffix == ".webp":
                image.save(output, quality=site.media.jpeg_quality, method=6)
            else:
                image.save(output, optimize=True)
    staged_digest = sha256_bytes(output.read_bytes())
    return output, staged_digest


def _upload_or_reuse(
    client: WordPressClient,
    state: StateStore,
    site: SiteConfig,
    document: Document,
    src: str,
    alt_from_markup: str,
) -> dict[str, Any]:
    local = resolve_local_image(unquote(src), document.path, site)
    if local is None:
        return {"external": True, "source_url": src, "alt": alt_from_markup}
    staged, digest = _stage_image(local, site)
    metadata = _metadata_for_image(document, src, local)
    alt = str(metadata.get("alt") or alt_from_markup or "").strip()
    if not alt or alt.lower() in {"image", "photo", "picture", "screenshot"}:
        message = f"{document.path}: image '{src}' needs specific alt text"
        if site.media.strict_alt_text:
            raise ValidationError(message)
        alt = title_from_filename(local)
    title = str(metadata.get("title") or title_from_filename(local)).strip()
    caption = str(metadata.get("caption") or "").strip()
    description = str(metadata.get("description") or "").strip()

    cached = state.media(digest)
    remote: dict[str, Any] | None = None
    if cached.get("wp_id"):
        try:
            remote = client.get("media", int(cached["wp_id"]))
        except Exception:
            remote = None
    if remote is None:
        remote = client.upload_media(staged, staged.name)
    remote = client.update_media(
        int(remote["id"]),
        {"alt_text": alt, "title": title, "caption": caption, "description": description},
    )
    result = {
        "wp_id": int(remote["id"]),
        "source_url": str(remote["source_url"]),
        "alt": alt,
        "title": title,
        "caption": caption,
        "local": str(local.relative_to(site.directory)) if site.directory in local.parents else str(local),
    }
    state.set_media(digest, result)
    return result


def render_document(
    document: Document,
    client: WordPressClient,
    state: StateStore,
    site: SiteConfig,
) -> RenderedDocument:
    output = RenderedDocument(html=render_markdown(document.markdown))
    soup = BeautifulSoup(output.html, "html.parser")
    for img in soup.find_all("img"):
        src = str(img.get("src") or "").strip()
        if not src:
            raise ValidationError(f"{document.path}: image has no src")
        info = _upload_or_reuse(client, state, site, document, src, str(img.get("alt") or ""))
        if info.get("external"):
            if not info.get("alt"):
                output.warnings.append(f"External image has empty alt text: {src}")
            continue
        img["src"] = info["source_url"]
        img["alt"] = info["alt"]
        img["title"] = info["title"]
        output.media_ids.append(int(info["wp_id"]))

    featured = document.metadata.get("featured_image")
    if featured:
        info = _upload_or_reuse(client, state, site, document, str(featured), "")
        if info.get("external"):
            raise ValidationError(f"{document.path}: featured_image must be a local file")
        output.featured_media = int(info["wp_id"])
        if output.featured_media not in output.media_ids:
            output.media_ids.append(output.featured_media)
    output.html = str(soup)
    return output


def html_to_markdown(value: str) -> str:
    from markdownify import markdownify

    return markdownify(value or "", heading_style="ATX", bullets="-").strip() + "\n"

