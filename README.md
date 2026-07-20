# WordPress Content Factory

A multi-site, Markdown-first WordPress content workspace. Each domain is one folder. VS Code tasks lint, compare, create/update through the core REST API, upload local images to the Media Library, read the records back, and optionally report the result to Slack.

## Point A → Point B

1. Unzip this folder and open **the unzipped root** in VS Code.
2. Run **Terminal → Run Task → Factory: 1 - Setup Python**.
3. Rename `websites/example.com` to your real domain, then change `site.url` in `site.yaml` and `WP_SITE_URL` in `.env`.
4. In WordPress, open **Users → Profile → Application Passwords**. Create `VS Code WordPress Factory` and copy the password shown once.
5. Put `WP_USERNAME` and `WP_APP_PASSWORD` in that site's `.env`. This is a revocable application password, not your normal wp-admin password.
6. Optional: add a Slack Incoming Webhook URL for `#general` as `SLACK_WEBHOOK_URL`.
7. Run the VS Code tasks in order: **Test connection → Lint Markdown → Preview sync plan → Push site → Verify live records**.
8. Add one or more domains with **Factory: Create website folder(s)**. Repeat only steps 3–7 for each site. See [docs/WEBSITE_ONBOARDING.md](docs/WEBSITE_ONBOARDING.md) for the root-folder operating guide.

WordPress 5.6+ includes Application Passwords and accepts them through HTTPS Basic Authentication. No OAuth/JWT plugin, Hostinger filesystem access, or paid OAuth grant is required.

## Folder shape

```text
wordpress-content-factory/
├── .vscode/tasks.json
├── websites/
│   └── example.com/
│       ├── .env                         # private credentials; Git-ignored
│       ├── site.yaml                    # non-secret behavior
│       ├── readme.md                    # site connection steps
│       ├── content/
│       │   ├── posts/*.md
│       │   ├── pages/*.md
│       │   ├── categories/*.md
│       │   ├── tags/*.md
│       │   ├── media/*                  # reusable original images
│       │   ├── products/                # reserved for WooCommerce adapter
│       │   └── custom/                  # reserved for custom post types
│       ├── media_out/                   # generated image staging; Git-ignored
│       └── .wp-factory/                 # IDs, hashes, conflicts; Git-ignored
└── reports/<domain>/*.{json,html}       # HTML is generated for site dashboards
```

## Daily workflow

Write or vibe-code Markdown, use `⌘K V` for side-by-side preview, then run:

1. **Lint Markdown** — validates frontmatter, duplicate slugs, local images, and meaningful alt text.
2. **Preview sync plan** — shows `create`, `update`, `noop`, `remote-changed`, or `conflict` without writing.
3. **Push site** — upserts categories/tags, uploads and annotates images, submits HTML, and reads each record back.
4. **Verify live records** — confirms title/slug/status through authenticated REST and fetches each published URL.

Push never deletes remote records. If WordPress and the local file both changed, push stops. Run **Pull safe remote changes**. Safe updates enter the normal content folders; conflicts are written under `.wp-factory/incoming/` for manual reconciliation.

## Post/page frontmatter

```yaml
---
title: Required human title
slug: stable-url-slug
status: draft                 # draft, pending, private, publish, or future
excerpt: Core WordPress excerpt and practical fallback meta description
categories: [news, salesforce] # posts only; terms are created if missing
tags: [ai, tutorial]           # posts only
featured_image: ../media/hero.png
images:
  ../media/hero.png:
    alt: Specific description of what matters in the image
    title: Media Library title
    caption: Optional visible caption metadata
    description: Optional Media Library description
date: 2026-07-10T09:00:00
comment_status: closed
---
```

The filename may change without creating a duplicate because `.wp-factory/state.json` retains the WordPress ID. If state is lost, the exact slug is used for safe recovery. Keep slugs unique within posts and within pages.

## Image behavior

- Paste/drop images into Markdown normally. Workspace settings place new images under `images/<document-name>/` beside the Markdown folder.
- You can also use `../media/file.png`, `/media/file.png`, or `@media/file.png`.
- Originals remain unchanged. Raster images are EXIF-oriented, resized to the configured maximum width, optimized into `media_out/`, and then uploaded.
- The submitted HTML uses the returned WordPress Media Library URL.
- Uploaded attachments receive alt text, title, caption, and description. Empty/generic alt text fails lint by default.
- Reusing identical optimized bytes reuses the stored Media Library attachment ID.

## What is intentionally outside v1

- WooCommerce products need `/wc/v3`, consumer credentials, pricing/inventory rules, and product-specific taxonomies. The folder is reserved but cannot accidentally push yet.
- Yoast/Rank Math metadata is plugin-specific. Core SEO fields work now; plugin metadata needs a small adapter or REST-exposed registered meta fields.
- Themes control fonts, widths, colors, and table CSS. The factory preserves semantic structure, not pixel-identical VS Code styling.
- No remote deletion, theme edits, plugin edits, or hosting filesystem access.

See [summary.md](summary.md) for the exact Markdown compatibility matrix and [docs/addons.md](docs/addons.md) for safe expansion points. See [docs/tools.md](docs/tools.md) for the modular tools/plugins architecture and VS Code menu options.

## Command-center SEO tools

Beyond lint/plan/push, the factory ships report-first SEO jobs you can run from **Terminal → Run Task** or CLI (openable HTML dashboards):

| Tool                     | What it does                                                                            |
| ------------------------ | --------------------------------------------------------------------------------------- |
| `featured-image-fixer` | Idempotently set`featured_image` (first body image → images map → media slug match) |
| `seo-audit`            | On-page SEO score (title/meta/slug/keyphrase/H2/featured image/depth/links)             |
| `readability`          | Flesch ease, long sentences, passive signals, heading density                           |
| `link-health`          | Live-check outbound URLs for broken/redirect/timeout (capped)                           |
| `schema-suggest`       | BlogPosting / FAQ / HowTo / Breadcrumb JSON-LD drafts from structure                    |
| `publish-readiness`    | Go-live checklist + queue of drafts ready / almost / blocked                            |

```bash
.venv/bin/python -m wp_factory tools run featured-image-fixer --site your-domain.com --open
.venv/bin/python -m wp_factory tools run seo-audit --site your-domain.com --open
.venv/bin/python -m wp_factory tools run publish-readiness --site your-domain.com --open
```

VS Code task **Factory Tools: Featured images then SEO audit** runs the fixer and immediately opens the audit for acceptance.

Optional frontmatter that improves scores: `excerpt` (120–165 chars), `focus_keyword`, `featured_image`.

## Direct CLI equivalents

```bash
.venv/bin/python -m wp_factory doctor --site example.com
.venv/bin/python -m wp_factory lint --site example.com
.venv/bin/python -m wp_factory plan --site example.com
.venv/bin/python -m wp_factory push --site example.com
.venv/bin/python -m wp_factory pull --site example.com
.venv/bin/python -m wp_factory verify --site example.com
.venv/bin/python -m wp_factory plan --all
.venv/bin/python -m wp_factory new-site example-one.com example-two.shop
```

## Web UI (optional)

A local dashboard under `frontend/` exposes the same VS Code tasks as a site-folder UI (pick a website, run doctor/lint/plan/push/tools, browse content, open reports):

```bash
./frontend/run.sh
# → http://127.0.0.1:8765
```

Or **Terminal → Run Task → Factory: Open Web UI**. Details: [frontend/README.md](frontend/README.md).

## Troubleshooting

- **401/403:** regenerate the Application Password, check the exact username, remove copied spaces only if your password manager added them, and confirm the user can edit/publish the intended content.
- **Application Passwords missing:** confirm HTTPS and WordPress 5.6+; security plugins can disable the feature.
- **REST route blocked:** open `https://your-domain/wp-json/`; security/cache rules must allow authenticated `/wp-json/wp/v2/*` requests.
- **Image upload rejected:** use JPG/PNG/WebP/GIF. WordPress blocks SVG by default.
- **SEO plugin field absent:** do not send guessed private field names. Add a tested adapter only after the plugin exposes writable REST fields.

## Official behavior references

- [WordPress REST authentication and Application Passwords](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/)
- [WordPress Application Password security/usage guide](https://developer.wordpress.org/advanced-administration/security/application-passwords/)
- [WordPress REST posts](https://developer.wordpress.org/rest-api/reference/posts/) and [media](https://developer.wordpress.org/rest-api/reference/media/) endpoints
- [WordPress REST categories](https://developer.wordpress.org/rest-api/reference/categories/) and [tags](https://developer.wordpress.org/rest-api/reference/tags/) endpoints
- [VS Code Markdown editing, pasted images, and `markdown.copyFiles.destination`](https://code.visualstudio.com/docs/languages/markdown)
