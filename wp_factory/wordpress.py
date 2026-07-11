from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import SiteConfig
from .errors import WordPressError


class WordPressClient:
    def __init__(self, site: SiteConfig):
        self.site = site
        self.session = requests.Session()
        self.session.auth = (site.username, site.app_password)
        self.session.headers.update({"User-Agent": "WordPress-Content-Factory/0.1"})

    def _url(self, endpoint: str) -> str:
        return f"{self.site.api_base}/{endpoint.strip('/')}"

    def request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.site.timeout)
        try:
            response = self.session.request(method, self._url(endpoint), **kwargs)
        except requests.RequestException as exc:
            raise WordPressError(f"{method} {endpoint} failed: {exc}") from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                detail = payload.get("message") or payload.get("code") or str(payload)
            except ValueError:
                detail = response.text[:500]
            raise WordPressError(f"{method} {endpoint}: HTTP {response.status_code}: {detail}")
        return response

    def discover(self) -> dict[str, Any]:
        url = f"{self.site.site_url}/wp-json/"
        try:
            response = self.session.get(url, timeout=self.site.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise WordPressError(f"WordPress REST discovery failed at {url}: {exc}") from exc

    def current_user(self) -> dict[str, Any]:
        result = self.request("GET", "users/me", params={"context": "edit"}).json()
        return result

    def list_all(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        page = 1
        rows: list[dict[str, Any]] = []
        query = dict(params or {})
        query["per_page"] = 100
        while True:
            query["page"] = page
            response = self.request("GET", endpoint, params=query)
            batch = response.json()
            rows.extend(batch)
            total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
            if page >= total_pages:
                return rows
            page += 1

    def find_by_slug(self, endpoint: str, slug: str, *, context: str = "edit") -> dict[str, Any] | None:
        statuses: list[str | None] = (
            ["publish", "draft", "pending", "private", "future"]
            if endpoint in {"posts", "pages"}
            else [None]
        )
        for status in statuses:
            params: dict[str, Any] = {"slug": slug, "context": context, "per_page": 100}
            if status:
                params["status"] = status
            rows = self.request("GET", endpoint, params=params).json()
            exact = [row for row in rows if row.get("slug") == slug]
            if exact:
                return exact[0]
        return None

    def get(self, endpoint: str, wp_id: int, *, context: str = "edit") -> dict[str, Any]:
        return self.request("GET", f"{endpoint}/{wp_id}", params={"context": context}).json()

    def upsert_term(self, taxonomy: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        existing = self.find_by_slug(taxonomy, payload["slug"])
        if existing:
            return "updated", self.request("POST", f"{taxonomy}/{existing['id']}", json=payload).json()
        return "created", self.request("POST", taxonomy, json=payload).json()

    def upsert_content(
        self, endpoint: str, payload: dict[str, Any], existing: dict[str, Any] | None
    ) -> tuple[str, dict[str, Any]]:
        if existing:
            return "updated", self.request("POST", f"{endpoint}/{existing['id']}", json=payload).json()
        return "created", self.request("POST", endpoint, json=payload).json()

    def upload_media(self, path: Path, filename: str) -> dict[str, Any]:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime,
        }
        return self.request("POST", "media", headers=headers, data=path.read_bytes()).json()

    def update_media(self, media_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"media/{media_id}", json=payload).json()

    def public_head(self, url: str) -> int:
        try:
            response = requests.get(url, timeout=self.site.timeout, allow_redirects=True)
            return response.status_code
        except requests.RequestException:
            return 0


def rendered_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("raw") or value.get("rendered") or "")
    return str(value or "")


def ids(values: Iterable[Any]) -> list[int]:
    return sorted(int(value) for value in values)
