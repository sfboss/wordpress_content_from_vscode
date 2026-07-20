"""
WordPress Content Factory — local web UI.

Additive dashboard that mirrors .vscode/tasks.json and the wp_factory CLI.
Does not modify production sync behavior; it shells the same CLI entry points.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncIterator

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Repository root (parent of frontend/)
ROOT = Path(__file__).resolve().parents[1]
WEBSITES_DIR = ROOT / "websites"
REPORTS_DIR = ROOT / "reports"
STATIC_DIR = Path(__file__).resolve().parent / "static"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$", re.I)
SAFE_REL_PATH = re.compile(r"^[a-zA-Z0-9._\-/ ]+$")

# Catalog mirrors .vscode/tasks.json functional tasks (plus tool menu items).
TASK_CATALOG: list[dict[str, Any]] = [
    {
        "id": "setup-python",
        "label": "Factory: 1 - Setup Python",
        "group": "bootstrap",
        "description": "Create .venv and install the package with dev extras.",
        "scope": "workspace",
        "mutating": True,
        "confirm": True,
        "command": "setup",
    },
    {
        "id": "doctor",
        "label": "Factory: 2 - Test connection",
        "group": "sync",
        "description": "Authenticated REST doctor check for the selected site.",
        "scope": "site",
        "mutating": False,
        "command": "doctor",
    },
    {
        "id": "lint",
        "label": "Factory: 3 - Lint Markdown",
        "group": "sync",
        "description": "Validate frontmatter, slugs, images, and alt text.",
        "scope": "site",
        "mutating": False,
        "command": "lint",
    },
    {
        "id": "plan",
        "label": "Factory: 4 - Preview sync plan",
        "group": "sync",
        "description": "Dry-run create/update/noop/conflict plan without writing remote.",
        "scope": "site",
        "mutating": False,
        "command": "plan",
    },
    {
        "id": "push",
        "label": "Factory: 5 - Push site",
        "group": "sync",
        "description": "Upsert content and media to WordPress through the REST API.",
        "scope": "site",
        "mutating": True,
        "confirm": True,
        "command": "push",
    },
    {
        "id": "pull",
        "label": "Factory: Pull safe remote changes",
        "group": "sync",
        "description": "Pull safe remote edits; conflicts go under .wp-factory/incoming/.",
        "scope": "site",
        "mutating": True,
        "confirm": True,
        "command": "pull",
    },
    {
        "id": "verify",
        "label": "Factory: Verify live records",
        "group": "sync",
        "description": "Confirm title/slug/status via REST and optional public URLs.",
        "scope": "site",
        "mutating": False,
        "command": "verify",
    },
    {
        "id": "plan-all",
        "label": "Factory: Plan all sites",
        "group": "multi-site",
        "description": "Preview sync plan for every configured website folder.",
        "scope": "all",
        "mutating": False,
        "command": "plan",
        "all_sites": True,
    },
    {
        "id": "push-all",
        "label": "Factory: Push all sites",
        "group": "multi-site",
        "description": "Push every configured website folder.",
        "scope": "all",
        "mutating": True,
        "confirm": True,
        "command": "push",
        "all_sites": True,
    },
    {
        "id": "tools-list",
        "label": "Factory Tools: List menu",
        "group": "tools",
        "description": "Show registered tools/plugins as JSON.",
        "scope": "workspace",
        "mutating": False,
        "command": "tools-list",
    },
    {
        "id": "tool-image-fixer",
        "label": "Factory Tools: Image fixer (site)",
        "group": "tools",
        "description": "Inventory local/remote/data-uri images and upload readiness.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "image-fixer",
        "open_report": False,
    },
    {
        "id": "tool-external-linker",
        "label": "Factory Tools: External linker (site)",
        "group": "tools",
        "description": "Find documents needing authoritative outbound links.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "external-linker",
        "open_report": False,
    },
    {
        "id": "tool-internal-linker",
        "label": "Factory Tools: Internal linker (site)",
        "group": "tools",
        "description": "Suggest internal links from the local content catalog.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "internal-linker",
        "open_report": False,
    },
    {
        "id": "tool-site-dashboard",
        "label": "Factory Tools: Site dashboard",
        "group": "tools",
        "description": "Whole-site KPI baselines with HTML dashboard.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "site-dashboard",
        "open_report": True,
    },
    {
        "id": "tool-featured-image-fixer",
        "label": "Factory Tools: Featured images fix (site)",
        "group": "tools",
        "description": "Idempotently set featured_image metadata in Markdown.",
        "scope": "site",
        "mutating": True,
        "confirm": True,
        "command": "tool",
        "tool": "featured-image-fixer",
        "open_report": True,
    },
    {
        "id": "tool-featured-then-seo",
        "label": "Factory Tools: Featured images then SEO audit",
        "group": "tools",
        "description": "Run featured-image-fixer, then seo-audit (composed task).",
        "scope": "site",
        "mutating": True,
        "confirm": True,
        "command": "tool-chain",
        "tools": ["featured-image-fixer", "seo-audit"],
        "open_report": True,
    },
    {
        "id": "tool-seo-audit",
        "label": "Factory Tools: SEO audit (site)",
        "group": "tools",
        "description": "On-page SEO scores for every post/page.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "seo-audit",
        "open_report": True,
    },
    {
        "id": "tool-readability",
        "label": "Factory Tools: Readability (site)",
        "group": "tools",
        "description": "Flesch ease, long sentences, passive signals, heading density.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "readability",
        "open_report": True,
    },
    {
        "id": "tool-link-health",
        "label": "Factory Tools: Link health (site)",
        "group": "tools",
        "description": "Live-check outbound URLs (capped) for broken/redirect/timeout.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "link-health",
        "open_report": True,
    },
    {
        "id": "tool-schema-suggest",
        "label": "Factory Tools: Schema suggest (site)",
        "group": "tools",
        "description": "BlogPosting / FAQ / HowTo / Breadcrumb JSON-LD drafts.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "schema-suggest",
        "open_report": True,
    },
    {
        "id": "tool-publish-readiness",
        "label": "Factory Tools: Publish readiness (site)",
        "group": "tools",
        "description": "Go-live checklist and draft queue.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "publish-readiness",
        "open_report": True,
    },
    {
        "id": "tool-content-overlap",
        "label": "Factory Tools: Content overlap map (site)",
        "group": "tools",
        "description": "Near-duplicate and search-intent collision map.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "content-overlap",
        "open_report": True,
    },
    {
        "id": "tool-content-overlap-target",
        "label": "Factory Tools: Check selected draft for overlap",
        "group": "tools",
        "description": "Compare one Markdown file against the full site catalog.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "content-overlap",
        "open_report": True,
        "needs_target": True,
    },
    {
        "id": "tool-run-selected",
        "label": "Factory Tools: Run selected file with tool",
        "group": "tools",
        "description": "Run any registered tool against one content path.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "needs_tool": True,
        "needs_target": True,
        "open_report": False,
    },
    {
        "id": "tool-content-inventory",
        "label": "Factory Tools: Content inventory",
        "group": "tools",
        "description": "Statuses, categories, duplicates, thin content, missing metadata.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "content-inventory",
        "open_report": True,
    },
    {
        "id": "tool-editorial-calendar",
        "label": "Factory Tools: Editorial calendar",
        "group": "tools",
        "description": "Date-driven schedule and unscheduled/blocked items.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "editorial-calendar",
        "open_report": True,
    },
    {
        "id": "tool-content-refresh",
        "label": "Factory Tools: Content refresh",
        "group": "tools",
        "description": "Queue stale, undated, placeholder, or time-sensitive content.",
        "scope": "site",
        "mutating": False,
        "command": "tool",
        "tool": "content-refresh",
        "open_report": True,
    },
    {
        "id": "new-site",
        "label": "Factory: Create website folder(s)",
        "group": "bootstrap",
        "description": "Scaffold one or more domain folders under websites/.",
        "scope": "workspace",
        "mutating": True,
        "confirm": True,
        "command": "new-site",
        "needs_domains": True,
    },
    {
        "id": "core-tests",
        "label": "Tests: Run Core Stability Suite",
        "group": "dev",
        "description": "pytest non-live suite with coverage floor (developer gate).",
        "scope": "workspace",
        "mutating": False,
        "command": "tests",
    },
]

TASK_BY_ID = {t["id"]: t for t in TASK_CATALOG}


@dataclass
class Job:
    id: str
    label: str
    argv: list[str]
    cwd: Path
    status: str = "queued"  # queued | running | succeeded | failed
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    lines: list[str] = field(default_factory=list)
    subscribers: list[asyncio.Queue[str | None]] = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None


JOBS: dict[str, Job] = {}
JOB_LOCK = asyncio.Lock()

app = FastAPI(title="WordPress Content Factory UI", version="0.1.0")


def _python() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def _env_has_credentials(site_dir: Path) -> bool:
    env_path = site_dir / ".env"
    if not env_path.exists():
        return False
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    has_user = bool(re.search(r"^WP_USERNAME=\s*\S+", text, re.M))
    has_pass = bool(re.search(r"^WP_APP_PASSWORD=\s*\S+", text, re.M))
    # Treat placeholder-looking passwords as incomplete
    if re.search(r"WP_APP_PASSWORD=\s*xxxx", text, re.I | re.M):
        has_pass = False
    if re.search(r"WP_USERNAME=\s*your_wordpress", text, re.I | re.M):
        has_user = False
    return has_user and has_pass


def _count_content(site_dir: Path) -> dict[str, int]:
    content = site_dir / "content"
    counts: dict[str, int] = {}
    for collection in ("posts", "pages", "categories", "tags", "media", "products", "custom"):
        folder = content / collection
        if not folder.is_dir():
            counts[collection] = 0
            continue
        if collection == "media":
            counts[collection] = sum(
                1
                for p in folder.rglob("*")
                if p.is_file() and p.name.lower() != "readme.md" and not p.name.startswith(".")
            )
        else:
            counts[collection] = sum(
                1
                for p in folder.rglob("*.md")
                if p.is_file() and p.name.lower() != "readme.md"
            )
    return counts


def _load_site_yaml(site_dir: Path) -> dict[str, Any]:
    path = site_dir / "site.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _list_sites() -> list[dict[str, Any]]:
    if not WEBSITES_DIR.exists():
        return []
    sites: list[dict[str, Any]] = []
    for path in sorted(WEBSITES_DIR.iterdir()):
        if not path.is_dir() or not (path / "site.yaml").is_file():
            continue
        raw = _load_site_yaml(path)
        site_cfg = raw.get("site") or {}
        counts = _count_content(path)
        reports_dir = REPORTS_DIR / path.name
        report_count = 0
        if reports_dir.is_dir():
            report_count = sum(1 for p in reports_dir.iterdir() if p.is_file())
        has_creds = _env_has_credentials(path)
        from readiness import quick_site_tone

        tone_info = quick_site_tone(path.name, has_creds, counts)
        sites.append(
            {
                "key": path.name,
                "name": str(site_cfg.get("name") or path.name),
                "url": str(site_cfg.get("url") or f"https://{path.name}"),
                "default_status": str(site_cfg.get("default_status") or "draft"),
                "has_credentials": has_creds,
                "has_env_example": (path / ".env.example").exists(),
                "counts": counts,
                "document_total": counts.get("posts", 0) + counts.get("pages", 0),
                "report_count": report_count,
                "path": f"websites/{path.name}",
                "tone": tone_info["tone"],
            }
        )
    return sites


def _site_or_404(key: str) -> Path:
    if not key or ".." in key or "/" in key or "\\" in key:
        raise HTTPException(400, "Invalid site key")
    directory = (WEBSITES_DIR / key).resolve()
    websites = WEBSITES_DIR.resolve()
    if directory.parent != websites or not directory.is_dir():
        raise HTTPException(404, f"Site not found: {key}")
    if not (directory / "site.yaml").is_file():
        raise HTTPException(404, f"Site missing site.yaml: {key}")
    return directory


def _safe_content_path(site_dir: Path, rel: str) -> Path:
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise HTTPException(400, "Invalid path")
    target = (site_dir / rel).resolve()
    if site_dir.resolve() not in target.parents and target != site_dir.resolve():
        raise HTTPException(400, "Path escapes site directory")
    return target


def _build_argv(task: dict[str, Any], body: "RunRequest") -> list[str]:
    py = _python()
    cmd = task["command"]

    if cmd == "setup":
        return [
            py,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "&&_not_used",  # replaced below for shell-less: run multi via chain
        ]

    if cmd == "tests":
        return [
            py,
            "-m",
            "pytest",
            "-m",
            "not live",
            "--cov=wp_factory",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-fail-under=30",
        ]

    if cmd == "new-site":
        domains = body.domains or []
        if not domains:
            raise HTTPException(400, "Provide one or more domain names")
        for d in domains:
            safe = d.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
            if not DOMAIN_RE.match(safe) or ".." in safe:
                raise HTTPException(400, f"Invalid domain: {d}")
        return [py, "-m", "wp_factory", "new-site", *[d.strip() for d in domains]]

    if cmd == "tools-list":
        return [py, "-m", "wp_factory", "tools", "list"]

    if cmd == "tool-chain":
        # Handled specially in runner as sequential processes
        return []

    if cmd == "tool":
        tool = body.tool or task.get("tool")
        if not tool:
            raise HTTPException(400, "Tool name required")
        if not re.match(r"^[a-z0-9-]+$", tool):
            raise HTTPException(400, "Invalid tool name")
        argv = [py, "-m", "wp_factory", "tools", "run", tool]
        site = body.site
        if not site:
            raise HTTPException(400, "Site is required for this tool")
        argv += ["--site", site]
        target = body.target
        if task.get("needs_target") and not target:
            raise HTTPException(400, "A content file target is required")
        if target:
            # Accept relative path under websites/ or absolute under site
            site_dir = _site_or_404(site)
            if Path(target).is_absolute():
                tpath = Path(target).resolve()
            else:
                candidate = (ROOT / target).resolve()
                if candidate.exists():
                    tpath = candidate
                else:
                    tpath = _safe_content_path(site_dir, target)
            if site_dir.resolve() not in tpath.parents and tpath != site_dir.resolve():
                raise HTTPException(400, "Target must be inside the site folder")
            argv += ["--target", str(tpath)]
        if body.open_report if body.open_report is not None else task.get("open_report"):
            argv.append("--open")
        return argv

    # Core site commands
    if cmd in {"doctor", "lint", "plan", "push", "pull", "verify"}:
        argv = [py, "-m", "wp_factory", cmd]
        if task.get("all_sites"):
            argv.append("--all")
        else:
            if not body.site:
                raise HTTPException(400, "Site is required")
            _site_or_404(body.site)
            argv += ["--site", body.site]
        if cmd == "push" and body.force:
            argv.append("--force")
        return argv

    raise HTTPException(400, f"Unsupported command: {cmd}")


class RunRequest(BaseModel):
    task_id: str
    site: str | None = None
    target: str | None = None
    tool: str | None = None
    domains: list[str] | None = None
    force: bool = False
    open_report: bool | None = None
    confirm: bool = False


class NewSiteRequest(BaseModel):
    domains: list[str] = Field(min_length=1)


async def _broadcast(job: Job, line: str | None) -> None:
    if line is not None:
        job.lines.append(line)
        # Cap memory for very long runs
        if len(job.lines) > 8000:
            job.lines = job.lines[-6000:]
    dead: list[asyncio.Queue[str | None]] = []
    for q in job.subscribers:
        try:
            q.put_nowait(line)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        job.subscribers.remove(q)


async def _run_process(job: Job, argv: list[str]) -> int:
    await _broadcast(job, f"$ {' '.join(shlex.quote(a) for a in argv)}\n")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    job.process = process
    assert process.stdout is not None
    while True:
        chunk = await process.stdout.readline()
        if not chunk:
            break
        text = chunk.decode("utf-8", errors="replace")
        await _broadcast(job, text)
    return await process.wait()


async def _execute_job(job: Job, task: dict[str, Any], body: RunRequest) -> None:
    job.status = "running"
    job.started_at = datetime.now(UTC).isoformat()
    try:
        cmd = task["command"]
        if cmd == "setup":
            # Mirror setup task: ensure venv exists then pip install -e .[dev]
            py = _python()
            steps = [
                [sys.executable, "-m", "venv", str(ROOT / ".venv")],
                [str(ROOT / ".venv" / "bin" / "python"), "-m", "pip", "install", "--upgrade", "pip"],
                [str(ROOT / ".venv" / "bin" / "python"), "-m", "pip", "install", "-e", ".[dev]"],
            ]
            # If venv already exists, skip create (still ok to run)
            code = 0
            for step in steps:
                code = await _run_process(job, step)
                if code != 0:
                    break
            job.exit_code = code
        elif cmd == "tool-chain":
            tools = task.get("tools") or []
            site = body.site
            if not site:
                raise HTTPException(400, "Site required")
            code = 0
            for tool in tools:
                argv = [
                    _python(),
                    "-m",
                    "wp_factory",
                    "tools",
                    "run",
                    tool,
                    "--site",
                    site,
                ]
                if body.open_report if body.open_report is not None else task.get("open_report"):
                    argv.append("--open")
                code = await _run_process(job, argv)
                if code != 0:
                    break
            job.exit_code = code
        else:
            argv = job.argv
            job.exit_code = await _run_process(job, argv)
        job.status = "succeeded" if job.exit_code == 0 else "failed"
    except HTTPException as exc:
        await _broadcast(job, f"ERROR {exc.detail}\n")
        job.exit_code = 1
        job.status = "failed"
    except Exception as exc:  # noqa: BLE001 — surface to UI console
        await _broadcast(job, f"ERROR {exc}\n")
        job.exit_code = 1
        job.status = "failed"
    finally:
        job.finished_at = datetime.now(UTC).isoformat()
        await _broadcast(job, None)  # EOF sentinel


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "root": str(ROOT),
        "python": _python(),
        "sites": len(_list_sites()),
    }


@app.get("/api/tasks")
def api_tasks() -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for task in TASK_CATALOG:
        groups.setdefault(task["group"], []).append(task)
    return {"tasks": TASK_CATALOG, "groups": groups}


@app.get("/api/tools")
def api_tools() -> Any:
    # Prefer live registry so UI stays in sync with package
    try:
        sys.path.insert(0, str(ROOT))
        from wp_factory.tools import list_tools  # type: ignore

        return {"tools": list_tools()}
    except Exception as exc:  # noqa: BLE001
        return {"tools": [], "error": str(exc)}


@app.get("/api/sites")
def api_sites() -> dict[str, Any]:
    return {"sites": _list_sites()}


@app.get("/api/sites/{key}/readiness")
def api_site_readiness(key: str) -> dict[str, Any]:
    """Prioritized TODO queue + green/yellow/red targets for getting a site to Ready."""
    _site_or_404(key)
    try:
        from readiness import assess_site

        return assess_site(key)
    except Exception as exc:  # noqa: BLE001 — surface for UI
        raise HTTPException(500, f"Readiness assessment failed: {exc}") from exc


@app.get("/api/sites/{key}")
def api_site_detail(key: str) -> dict[str, Any]:
    directory = _site_or_404(key)
    sites = {s["key"]: s for s in _list_sites()}
    base = sites.get(key) or {}
    raw = _load_site_yaml(directory)
    # Never expose .env secrets
    safe_config = {
        "site": raw.get("site") or {},
        "content": raw.get("content") or {},
        "media": raw.get("media") or {},
        "seo": raw.get("seo") or {},
        "notifications": raw.get("notifications") or {},
    }
    content_tree: list[dict[str, Any]] = []
    content_dir = directory / "content"
    if content_dir.is_dir():
        for collection in ("posts", "pages", "categories", "tags", "media", "products", "custom"):
            folder = content_dir / collection
            files: list[dict[str, Any]] = []
            if folder.is_dir():
                for p in sorted(folder.rglob("*")):
                    if not p.is_file() or p.name.startswith("."):
                        continue
                    if p.name.lower() == "readme.md":
                        continue
                    rel = p.relative_to(directory).as_posix()
                    files.append(
                        {
                            "name": p.name,
                            "path": rel,
                            "size": p.stat().st_size,
                            "suffix": p.suffix.lower(),
                        }
                    )
            content_tree.append({"collection": collection, "files": files, "count": len(files)})
    return {
        **base,
        "config": safe_config,
        "content_tree": content_tree,
        "readme_exists": (directory / "readme.md").exists(),
    }


@app.get("/api/sites/{key}/file")
def api_site_file(key: str, path: str = Query(..., description="Relative path under site")) -> dict[str, Any]:
    directory = _site_or_404(key)
    target = _safe_content_path(directory, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    # Only text-ish files
    if target.suffix.lower() not in {".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".html", ".csv"}:
        raise HTTPException(400, "Only text content files can be previewed")
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > 400_000:
        text = text[:400_000] + "\n\n… truncated …"
    return {
        "path": target.relative_to(directory).as_posix(),
        "name": target.name,
        "size": target.stat().st_size,
        "content": text,
    }


@app.get("/api/sites/{key}/reports")
def api_site_reports(key: str) -> dict[str, Any]:
    _site_or_404(key)
    reports_dir = REPORTS_DIR / key
    items: list[dict[str, Any]] = []
    if reports_dir.is_dir():
        for p in sorted(reports_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file():
                continue
            items.append(
                {
                    "name": p.name,
                    "path": f"/api/reports/{key}/{p.name}",
                    "size": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(),
                    "kind": "html" if p.suffix.lower() == ".html" else "json" if p.suffix.lower() == ".json" else "file",
                }
            )
    return {"site": key, "reports": items}


@app.get("/api/reports/{key}/{filename}")
def api_report_file(key: str, filename: str) -> FileResponse:
    _site_or_404(key)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = (REPORTS_DIR / key / filename).resolve()
    if path.parent != (REPORTS_DIR / key).resolve() or not path.is_file():
        raise HTTPException(404, "Report not found")
    media = "text/html" if path.suffix.lower() == ".html" else "application/json" if path.suffix.lower() == ".json" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=filename)


@app.post("/api/sites")
def api_create_sites(body: NewSiteRequest) -> dict[str, Any]:
    """Create site scaffolds via the same CLI as the VS Code task."""
    domains: list[str] = []
    for d in body.domains:
        for part in re.split(r"[\s,]+", d.strip()):
            if part:
                domains.append(part)
    if not domains:
        raise HTTPException(400, "No domains provided")
    # Run synchronously for immediate feedback
    import subprocess

    result = subprocess.run(
        [_python(), "-m", "wp_factory", "new-site", *domains],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "sites": _list_sites(),
    }


@app.post("/api/run")
async def api_run(body: RunRequest) -> dict[str, Any]:
    task = TASK_BY_ID.get(body.task_id)
    if not task:
        raise HTTPException(404, f"Unknown task_id: {body.task_id}")
    if task.get("confirm") and not body.confirm:
        raise HTTPException(
            400,
            "This action can change local or remote state. Set confirm=true after reviewing.",
        )
    if task["scope"] == "site" and not body.site and not task.get("all_sites"):
        raise HTTPException(400, "site is required")

    # Pre-build argv for simple commands; chains build later
    argv: list[str] = []
    if task["command"] not in {"setup", "tool-chain"}:
        argv = _build_argv(task, body)

    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id, label=task["label"], argv=argv, cwd=ROOT)
    async with JOB_LOCK:
        JOBS[job_id] = job
        # Prune old finished jobs
        if len(JOBS) > 40:
            finished = [j for j in JOBS.values() if j.status in {"succeeded", "failed"}]
            finished.sort(key=lambda j: j.finished_at or "")
            for old in finished[: max(0, len(finished) - 20)]:
                JOBS.pop(old.id, None)

    asyncio.create_task(_execute_job(job, task, body))
    return {
        "job_id": job_id,
        "label": task["label"],
        "stream_url": f"/api/run/{job_id}/stream",
        "status_url": f"/api/run/{job_id}",
    }


@app.get("/api/run/{job_id}")
def api_job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "label": job.label,
        "status": job.status,
        "exit_code": job.exit_code,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "line_count": len(job.lines),
        "output": "".join(job.lines[-400:]),
    }


@app.get("/api/run/{job_id}/stream")
async def api_job_stream(job_id: str) -> StreamingResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=2000)
    job.subscribers.append(queue)

    async def event_gen() -> AsyncIterator[str]:
        # Replay buffered lines first
        for line in list(job.lines):
            yield f"data: {json.dumps({'type': 'line', 'text': line})}\n\n"
        if job.status in {"succeeded", "failed"}:
            yield f"data: {json.dumps({'type': 'done', 'status': job.status, 'exit_code': job.exit_code})}\n\n"
            return
        try:
            while True:
                item = await queue.get()
                if item is None:
                    yield f"data: {json.dumps({'type': 'done', 'status': job.status, 'exit_code': job.exit_code})}\n\n"
                    break
                yield f"data: {json.dumps({'type': 'line', 'text': item})}\n\n"
        finally:
            if queue in job.subscribers:
                job.subscribers.remove(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Frontend static/index.html missing</h1>", status_code=500)
    return FileResponse(index_path)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import uvicorn

    host = os.environ.get("WP_FACTORY_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("WP_FACTORY_UI_PORT", "8765"))
    print(f"WordPress Content Factory UI → http://{host}:{port}")
    print(f"Repository root: {ROOT}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
