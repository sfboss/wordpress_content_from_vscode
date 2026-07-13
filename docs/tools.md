# Content Factory tools/plugins architecture

Tools are small, API-first jobs that can run against one Markdown file, one folder, one site, or eventually every site. The first implementation is intentionally read-only and report-driven so each capability can be tested on a single post/page before it is allowed to patch content or batch across the whole `websites/` tree.

## Menu options now available

Run **Terminal → Run Task** and choose:

### Core sync helpers

- **Factory Tools: List menu** — show registered tools/plugins.
- **Factory Tools: Image fixer (site)** — inventory every image reference and classify it as local, remote, data URI, ready for upload, or needing import.
- **Factory Tools: External linker (site)** — identify documents that need authoritative outbound links and candidate entities/keywords.
- **Factory Tools: Internal linker (site)** — evaluate internal links and suggest relevant posts/pages from the local content catalog.
- **Factory Tools: Site dashboard** — generate whole-site KPI baselines and open an interactive visual dashboard.
- **Factory Tools: Content inventory** — inventory statuses, categories, duplicate slugs/titles, thin pages, and missing metadata.
- **Factory Tools: Editorial calendar** — build a date-driven content schedule and flag unscheduled or blocked content items.
- **Factory Tools: Content refresh** — queue stale, undated, placeholder, or time-sensitive content for updates.

### Command-center SEO suite (All-in-One SEO-inspired)

- **Factory Tools: Featured images fix (site)** — idempotently set `featured_image` from first body image / images map / media slug match; repair YAML so later audits see progress.
- **Factory Tools: Featured images then SEO audit** — fix featured images, then open the SEO audit so acceptance is one click.
- **Factory Tools: SEO audit (site)** — on-page SEO scores (title/meta length, focus keyphrase, slug, H2 structure, featured image, depth, links).
- **Factory Tools: Readability (site)** — Flesch reading ease, long sentences, passive-voice signals, heading density.
- **Factory Tools: Link health (site)** — live-check external/site URLs for broken, redirected, or timed-out links (capped for speed).
- **Factory Tools: Schema suggest (site)** — detect BlogPosting, FAQPage, HowTo, and BreadcrumbList opportunities; emit reviewable JSON-LD.
- **Factory Tools: Publish readiness (site)** — go-live checklist + prioritized queue of drafts ready / almost / blocked.
- **Factory Tools: Content overlap map (site)** — visualize topical relationships, near-duplicate prose, and potential search-intent collisions before publishing long-tail content.
- **Factory Tools: Check selected draft for overlap** — compare the active Markdown draft with the complete site catalog without turning the run into an all-or-nothing batch.

- **Factory Tools: Run selected file with tool** — run any tool against the active editor file via VS Code `${file}`.

Direct CLI examples:

```bash
.venv/bin/python -m wp_factory tools list
.venv/bin/python -m wp_factory tools run image-fixer --site example.com --target websites/example.com/content/posts/example.md
.venv/bin/python -m wp_factory tools run site-dashboard --site example.com --open
.venv/bin/python -m wp_factory tools run content-inventory --site example.com --open
.venv/bin/python -m wp_factory tools run editorial-calendar --site example.com --open
.venv/bin/python -m wp_factory tools run content-refresh --site example.com --open
.venv/bin/python -m wp_factory tools run featured-image-fixer --site example.com --open
.venv/bin/python -m wp_factory tools run seo-audit --site example.com --open
.venv/bin/python -m wp_factory tools run readability --site example.com --open
.venv/bin/python -m wp_factory tools run link-health --site example.com --open
.venv/bin/python -m wp_factory tools run schema-suggest --site example.com --open
.venv/bin/python -m wp_factory tools run publish-readiness --site example.com --open
.venv/bin/python -m wp_factory tools run content-overlap --site example.com --open
.venv/bin/python -m wp_factory tools run content-overlap --site example.com --target websites/example.com/content/posts/draft.md --open
```

### Featured image workflow

1. Run **Featured images fix (site)** (or CLI `featured-image-fixer`).
2. It skips docs that already have a valid `featured_image` (idempotent).
3. Otherwise it picks, in order: first Markdown body image → first `images:` map local file → `content/media/<slug>-01.*`.
4. Writes `featured_image` + `images` alt metadata; quotes broken YAML scalars so the file loads for lint/seo/push.
5. Re-run **SEO audit** — `featured_image` checks should pass for every document that had a local candidate.
6. **Push site** still uploads the featured image through the existing `markdown_engine` path.

Every run writes a JSON artifact under `reports/<site>/`, matching the existing lint/plan/push reporting pattern. Tools with HTML UIs also write a same-named, self-contained `.html` file (no CDN).

## Design rules

1. **Single item first.** A tool accepts `--target` so one post/page can be tested before batch mode.
2. **Batch safe by default.** The same runner accepts no target to process the whole site.
3. **Reports before mutation.** Tools produce findings and next steps first; future patching should be an explicit mode.
4. **Shared content API.** Tools reuse `load_documents`, site config, reports, and image resolution instead of duplicating sync logic.
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
5. **Composable jobs.** Image import, alt text, internal links, external links, SEO, readability, overlap detection, schema, and dashboard KPIs remain separate tasks so failures are isolated.
=======
5. **Composable jobs.** Image import, alt text, internal links, external links, SEO, readability, schema, inventory, calendar, refresh planning, and dashboard KPIs remain separate tasks so failures are isolated.
>>>>>>> theirs
=======
5. **Composable jobs.** Image import, alt text, internal links, external links, SEO, readability, schema, inventory, calendar, refresh planning, and dashboard KPIs remain separate tasks so failures are isolated.
>>>>>>> theirs
=======
5. **Composable jobs.** Image import, alt text, internal links, external links, SEO, readability, schema, inventory, calendar, refresh planning, and dashboard KPIs remain separate tasks so failures are isolated.
>>>>>>> theirs
=======
5. **Composable jobs.** Image import, alt text, internal links, external links, SEO, readability, schema, inventory, calendar, refresh planning, and dashboard KPIs remain separate tasks so failures are isolated.
>>>>>>> theirs

## Tool contract

A tool is registered in `wp_factory.tools.TOOLS` with a name, title, description, batch-safety flag, and runner. A runner receives `SiteConfig` plus an optional `Path` target and returns JSON-serializable data. This keeps the interface usable from CLI, VS Code tasks, tests, and a future web dashboard.

SEO-oriented runners live in `wp_factory/seo_tools.py` and are registered from `tools.py`.

## Optional frontmatter for stronger SEO scores

These keys are optional but improve `seo-audit` and `publish-readiness`:

```yaml
excerpt: 120–165 character SERP summary with the keyphrase once
focus_keyword: primary phrase you want the page to rank for
# aliases also recognized: focus_keyphrase, primary_keyword, keyword
# meta_description / seo_description also count as the SERP blurb
featured_image: ../media/hero.jpg
search_intent: informational # informational, commercial, transactional, or navigational
content_role: cluster        # pillar, cluster, support, landing, or reference
```

`content-overlap` derives missing focus phrases from titles, but explicit `focus_keyword`, `search_intent`, and `content_role` make its editorial recommendations clearer. Similarity is a review signal—not a Google ranking verdict and never an automatic reason to delete or redirect a page.

## Planned mutation path

- Image fixer: download/decode remote or base64 images into `content/media`, generate stable SEO filenames/metadata, then rely on the existing WordPress media upload path during `push`.
- External linker: enrich candidates with search/provider adapters and apply reviewed links as Markdown patches.
- Internal linker: score topical matches across the local catalog, insert reviewed links, and prevent over-linking.
- SEO audit: optional autofix mode for excerpt scaffolding and focus keyword frontmatter (never rewrite body prose automatically).
- Schema suggest: optional injection of reviewed JSON-LD via theme/`rest_meta` only after plugin REST fields are confirmed.
- Dashboard: add per-site baseline overrides in `site.yaml` and multi-site comparison views.
