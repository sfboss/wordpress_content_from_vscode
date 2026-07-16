from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from dataclasses import asdict
from pathlib import Path

import yaml

from .config import WEBSITES_DIR, list_site_keys, load_site
from .dashboard import dashboard_html_path
from .errors import FactoryError
from .reporting import notify_slack, plan_dict, result_dict, write_report
from .sync import SiteSync
from .tools import HTML_REPORT_TOOLS, TOOLS, list_tools, run_tool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wp-factory", description="Markdown to WordPress content sync")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "lint", "plan", "push", "pull", "verify"):
        command = sub.add_parser(name)
        target = command.add_mutually_exclusive_group(required=True)
        target.add_argument("--site", help="Folder under websites/")
        target.add_argument("--all", action="store_true", help="Run every configured site")
        if name == "push":
            command.add_argument("--force", action="store_true", help="Overwrite a detected edit conflict")
    tools = sub.add_parser("tools", help="List modular content factory tools")
    tools_sub = tools.add_subparsers(dest="tools_command", required=True)
    tools_sub.add_parser("list", help="Show available tools/plugins")
    run = tools_sub.add_parser("run", help="Run one tool against a site or one content path")
    run.add_argument("tool", choices=sorted(TOOLS), help="Tool/plugin to run")
    run.add_argument("--site", required=True, help="Folder under websites/")
    run.add_argument("--target", help="Optional Markdown file or folder to process first")
    run.add_argument(
        "--open",
        action="store_true",
        dest="open_report",
        help="Open the generated HTML report in a browser (site-dashboard, seo-audit, readability, link-health, schema-suggest, publish-readiness)",
    )

    create = sub.add_parser("new-site", help="Create one or more domain scaffolds")
    create.add_argument("domains", nargs="+", help="Domain folder name(s), such as blog.example.com")
    return parser


def _sites(args: argparse.Namespace) -> list[str]:
    keys = list_site_keys() if args.all else [args.site]
    if not keys:
        raise FactoryError("No site.yaml files found under websites/.")
    return keys


def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print("No rows.")
        return
    width = max(len(str(row.get("action", ""))) for row in rows)
    for row in rows:
        marker = "OK" if row.get("ok", True) else "FAIL"
        print(f"{marker:4} {str(row.get('action', '')):<{width}}  {row.get('key', row.get('site', ''))}  {row.get('message', row.get('reason', ''))}")


def _normalize_domain(domain: str) -> str:
    safe = domain.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    if not safe or "/" in safe or ".." in safe or safe.startswith("."):
        raise FactoryError("Use only domain folder names, such as blog.example.com")
    return safe


def _template_site_dir() -> Path:
    preferred = WEBSITES_DIR / "example.com"
    if preferred.exists():
        return preferred
    candidates = [path for path in sorted(WEBSITES_DIR.iterdir()) if (path / "site.yaml").is_file()] if WEBSITES_DIR.exists() else []
    if not candidates:
        raise FactoryError("No site template exists under websites/. Keep at least one configured site folder.")
    return candidates[0]


def _write_scaffold(destination: Path, safe: str, template: Path) -> None:
    destination.mkdir(parents=True)
    for folder in (
        "content/posts",
        "content/pages",
        "content/categories",
        "content/tags",
        "content/media",
        "content/products",
        "content/custom",
    ):
        path = destination / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / "readme.md").write_text(f"# {folder.split('/')[-1]} for {safe}\n\nAdd site-specific content here.\n", encoding="utf-8")

    template_config = template / "site.yaml"
    if template_config.exists():
        config = yaml.safe_load(template_config.read_text(encoding="utf-8")) or {}
    else:
        config = {}
    config.setdefault("site", {})
    config.setdefault("content", {})
    config.setdefault("media", {})
    config.setdefault("seo", {})
    config.setdefault("notifications", {})
    config["site"]["name"] = safe
    config["site"]["url"] = f"https://{safe}"
    config["site"].setdefault("api_path", "/wp-json/wp/v2")
    config["site"].setdefault("default_status", "draft")
    config["site"].setdefault("timeout_seconds", 30)
    config["site"].setdefault("verify_public_urls", True)
    config["content"].setdefault("strict_alt_text", True)
    config["content"].setdefault("delete_remote", False)
    config["media"].setdefault("max_width", 1920)
    config["media"].setdefault("jpeg_quality", 85)
    config["media"].setdefault("convert_to_webp", False)
    config["seo"].setdefault("plugin_adapter", "none")
    config["notifications"].setdefault("slack", "optional")
    (destination / "site.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    env_template = template / ".env.example"
    if env_template.exists():
        env_text = env_template.read_text(encoding="utf-8")
        env_text = env_text.replace("https://example.com", f"https://{safe}")
        env_text = env_text.replace("https://olive-manatee-953565.hostingersite.com", f"https://{safe}")
    else:
        env_text = f"WP_SITE_URL=https://{safe}\nWP_USERNAME=your_wordpress_username\nWP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx\nSLACK_WEBHOOK_URL=\n"
    (destination / ".env.example").write_text(env_text, encoding="utf-8")

    (destination / "readme.md").write_text(
        f"""# {safe} content workspace

1. Copy `.env.example` to `.env`.
2. Add the WordPress username and Application Password to `.env`.
3. Run `wp_factory doctor --site {safe}` or the VS Code connection task.
4. Add content under `content/posts/`, `content/pages/`, `content/categories/`, `content/tags/`, and `content/media/`.
5. Run lint, plan, push, and verify from the repository root.

Private files (`.env`, `.wp-factory/`, and `media_out/`) stay local and are ignored by Git.
""",
        encoding="utf-8",
    )


def _new_site(domains: list[str]) -> int:
    created: list[str] = []
    skipped: list[str] = []
    template = _template_site_dir()
    for domain in domains:
        safe = _normalize_domain(domain)
        destination = WEBSITES_DIR / safe
        if destination.exists():
            skipped.append(safe)
            print(f"Exists websites/{safe}; leaving it unchanged.")
            continue
        _write_scaffold(destination, safe, template)
        created.append(safe)
        print(f"Created websites/{safe}. Copy .env.example to .env, add the application password, then run the connection task.")
    if not created and skipped:
        return 0
    return 0


def _run_site(command: str, key: str, args: argparse.Namespace) -> bool:
    require_credentials = command not in {"lint"}
    site = load_site(key, require_credentials=require_credentials)
    sync = SiteSync(site)
    print(f"\n[{site.key}] {command}")
    if command == "doctor":
        data = sync.doctor()
        print(json.dumps(data, indent=2))
        report = write_report(site, command, data)
        return True
    if command == "lint":
        issues = sync.lint()
        failures = [item for item in issues if "warning:" not in item]
        for issue in issues:
            print(("WARN " if "warning:" in issue else "FAIL ") + issue)
        if not issues:
            print("OK Markdown and local image references passed.")
        write_report(site, command, {"issues": issues})
        return not failures
    if command == "plan":
        rows = [plan_dict(item) for item in sync.plan()]
        _print_rows(rows)
        report = write_report(site, command, rows)
        notify_slack(site, command, rows, report)
        return not any(row["action"] == "conflict" for row in rows)
    if command == "push":
        rows = [result_dict(item) for item in sync.push(force=args.force)]
    elif command == "pull":
        rows = [result_dict(item) for item in sync.pull()]
    elif command == "verify":
        rows = [result_dict(item) for item in sync.verify()]
    else:
        raise FactoryError(f"Unknown command: {command}")
    _print_rows(rows)
    report = write_report(site, command, rows)
    print(f"Report: {report.relative_to(Path.cwd()) if Path.cwd() in report.parents else report}")
    notify_slack(site, command, rows, report)
    return all(row["ok"] for row in rows)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "new-site":
            return _new_site(args.domains)
        if args.command == "tools":
            if args.tools_command == "list":
                print(json.dumps(list_tools(), indent=2))
                return 0
            if args.open_report and args.tool not in HTML_REPORT_TOOLS:
                raise FactoryError(
                    f"--open is only available for tools with HTML reports: {', '.join(sorted(HTML_REPORT_TOOLS))}"
                )
            payload, report = run_tool(args.tool, args.site, args.target)
            # Keep terminal output scannable for large SEO reports
            summary = payload.get("summary") or {k: payload[k] for k in list(payload)[:6] if k not in {"documents", "links", "checks"}}
            print(json.dumps({"tool": payload.get("tool", args.tool), "summary": summary}, indent=2, default=str))
            print(f"Report: {report.relative_to(Path.cwd()) if Path.cwd() in report.parents else report}")
            if args.tool in HTML_REPORT_TOOLS:
                html_report = dashboard_html_path(report)
                if html_report.exists():
                    print(f"Dashboard: {html_report.relative_to(Path.cwd()) if Path.cwd() in html_report.parents else html_report}")
                    if args.open_report:
                        webbrowser.open(html_report.resolve().as_uri())
            return 0
        ok = True
        for key in _sites(args):
            try:
                ok = _run_site(args.command, key, args) and ok
            except FactoryError as exc:
                print(f"ERROR [{key}] {exc}", file=sys.stderr)
                ok = False
        return 0 if ok else 1
    except FactoryError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
