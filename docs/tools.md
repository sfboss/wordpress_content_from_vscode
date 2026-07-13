# Content Factory tools/plugins architecture

Tools are small, API-first jobs that can run against one Markdown file, one folder, one site, or eventually every site. The first implementation is intentionally read-only and report-driven so each capability can be tested on a single post/page before it is allowed to patch content or batch across the whole `websites/` tree.

## Menu options now available

Run **Terminal → Run Task** and choose:

- **Factory Tools: List menu** — show registered tools/plugins.
- **Factory Tools: Image fixer (site)** — inventory every image reference and classify it as local, remote, data URI, ready for upload, or needing import.
- **Factory Tools: External linker (site)** — identify documents that need authoritative outbound links and candidate entities/keywords.
- **Factory Tools: Internal linker (site)** — evaluate internal links and suggest relevant posts/pages from the local content catalog.
- **Factory Tools: Site dashboard** — generate whole-site KPI baselines for first-run content readiness.
- **Factory Tools: Run selected file with tool** — run any tool against the active editor file via VS Code `${file}`.

Direct CLI examples:

```bash
.venv/bin/python -m wp_factory tools list
.venv/bin/python -m wp_factory tools run image-fixer --site example.com --target websites/example.com/content/posts/example.md
.venv/bin/python -m wp_factory tools run site-dashboard --site example.com
```

Every run writes a JSON artifact under `reports/<site>/`, matching the existing lint/plan/push reporting pattern.

## Design rules

1. **Single item first.** A tool accepts `--target` so one post/page can be tested before batch mode.
2. **Batch safe by default.** The same runner accepts no target to process the whole site.
3. **Reports before mutation.** Tools produce findings and next steps first; future patching should be an explicit mode.
4. **Shared content API.** Tools reuse `load_documents`, site config, reports, and image resolution instead of duplicating sync logic.
5. **Composable jobs.** Image import, alt text, internal links, external links, and dashboard KPIs remain separate tasks so failures are isolated.

## Tool contract

A tool is registered in `wp_factory.tools.TOOLS` with a name, title, description, batch-safety flag, and runner. A runner receives `SiteConfig` plus an optional `Path` target and returns JSON-serializable data. This keeps the interface usable from CLI, VS Code tasks, tests, and a future web dashboard.

## Planned mutation path

- Image fixer: download/decode remote or base64 images into `content/media`, generate stable SEO filenames/metadata, then rely on the existing WordPress media upload path during `push`.
- External linker: enrich candidates with search/provider adapters and apply reviewed links as Markdown patches.
- Internal linker: score topical matches across the local catalog, insert reviewed links, and prevent over-linking.
- Dashboard: add HTML output and per-site baseline overrides in `site.yaml`.
