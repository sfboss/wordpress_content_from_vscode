from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Document:
    key: str
    collection: str
    endpoint: str
    path: Path
    metadata: dict[str, Any]
    markdown: str
    title: str
    slug: str
    status: str
    source_hash: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class PlanItem:
    document: Document
    action: str
    remote: dict[str, Any] | None = None
    reason: str = ""


@dataclass
class SyncResult:
    key: str
    action: str
    ok: bool
    message: str
    wp_id: int | None = None
    url: str | None = None

