from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from dotenv import dotenv_values

from .errors import ValidationError
from .utils import clean_secret


ROOT = Path(__file__).resolve().parents[1]
WEBSITES_DIR = ROOT / "websites"


@dataclass(frozen=True)
class MediaConfig:
    max_width: int = 1920
    jpeg_quality: int = 85
    strict_alt_text: bool = True
    convert_to_webp: bool = False


@dataclass(frozen=True)
class SiteConfig:
    key: str
    directory: Path
    site_url: str
    api_base: str
    username: str
    app_password: str
    slack_webhook_url: str
    default_status: str
    timeout: int
    verify_public_urls: bool
    media: MediaConfig
    raw: dict[str, Any]

    @property
    def content_dir(self) -> Path:
        return self.directory / "content"

    @property
    def state_path(self) -> Path:
        return self.directory / ".wp-factory" / "state.json"

    @property
    def incoming_dir(self) -> Path:
        return self.directory / ".wp-factory" / "incoming"

    @property
    def media_out_dir(self) -> Path:
        return self.directory / "media_out"


def list_site_keys() -> list[str]:
    if not WEBSITES_DIR.exists():
        return []
    return sorted(p.name for p in WEBSITES_DIR.iterdir() if (p / "site.yaml").is_file())


def _site_directory(site: str) -> Path:
    requested = Path(site)
    directory = requested if requested.is_absolute() else WEBSITES_DIR / requested
    directory = directory.resolve()
    websites = WEBSITES_DIR.resolve()
    if websites not in directory.parents:
        raise ValidationError("Site must be a direct folder inside websites/.")
    return directory


def load_site(site: str, *, require_credentials: bool = True) -> SiteConfig:
    directory = _site_directory(site)
    config_path = directory / "site.yaml"
    if not config_path.exists():
        raise ValidationError(f"Missing site config: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    env_file = {k: v for k, v in dotenv_values(directory / ".env").items() if v is not None}
    env = {**env_file, **{k: v for k, v in os.environ.items() if k.startswith(("WP_", "SLACK_"))}}

    site_cfg = raw.get("site", {})
    content_cfg = raw.get("content", {})
    media_cfg = raw.get("media", {})
    site_url = str(env.get("WP_SITE_URL") or site_cfg.get("url") or "").rstrip("/")
    if not site_url:
        raise ValidationError("Set site.url in site.yaml or WP_SITE_URL in the site .env file.")
    parsed = urlparse(site_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError("WP_SITE_URL must be a complete HTTPS URL.")

    username = str(env.get("WP_USERNAME") or "").strip()
    app_password = clean_secret(str(env.get("WP_APP_PASSWORD") or ""))
    if require_credentials and (not username or not app_password):
        raise ValidationError(
            f"Add WP_USERNAME and WP_APP_PASSWORD to {directory / '.env'} before connecting."
        )

    api_path = str(site_cfg.get("api_path", "/wp-json/wp/v2")).strip()
    api_base = f"{site_url}/{api_path.strip('/')}"
    default_status = str(site_cfg.get("default_status", "draft"))
    if default_status not in {"draft", "pending", "private", "publish", "future"}:
        raise ValidationError(f"Unsupported default_status: {default_status}")
    if bool(content_cfg.get("delete_remote", False)):
        raise ValidationError("Remote deletion is intentionally unsupported; keep delete_remote: false.")

    return SiteConfig(
        key=directory.name,
        directory=directory,
        site_url=site_url,
        api_base=api_base,
        username=username,
        app_password=app_password,
        slack_webhook_url=str(env.get("SLACK_WEBHOOK_URL") or "").strip(),
        default_status=default_status,
        timeout=int(site_cfg.get("timeout_seconds", 30)),
        verify_public_urls=bool(site_cfg.get("verify_public_urls", True)),
        media=MediaConfig(
            max_width=int(media_cfg.get("max_width", 1920)),
            jpeg_quality=int(media_cfg.get("jpeg_quality", 85)),
            strict_alt_text=bool(content_cfg.get("strict_alt_text", True)),
            convert_to_webp=bool(media_cfg.get("convert_to_webp", False)),
        ),
        raw=raw,
    )

