from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import atomic_json_write


@dataclass
class StateStore:
    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "StateStore":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"version": 1, "documents": {}, "media": {}, "terms": {}}
        data.setdefault("version", 1)
        data.setdefault("documents", {})
        data.setdefault("media", {})
        data.setdefault("terms", {})
        return cls(path=path, data=data)

    def document(self, key: str) -> dict[str, Any]:
        return self.data["documents"].get(key, {})

    def set_document(self, key: str, value: dict[str, Any]) -> None:
        self.data["documents"][key] = value

    def media(self, digest: str) -> dict[str, Any]:
        return self.data["media"].get(digest, {})

    def set_media(self, digest: str, value: dict[str, Any]) -> None:
        self.data["media"][digest] = value

    def term(self, taxonomy: str, slug: str) -> dict[str, Any]:
        return self.data["terms"].get(f"{taxonomy}:{slug}", {})

    def set_term(self, taxonomy: str, slug: str, value: dict[str, Any]) -> None:
        self.data["terms"][f"{taxonomy}:{slug}"] = value

    def save(self) -> None:
        atomic_json_write(self.path, self.data)

