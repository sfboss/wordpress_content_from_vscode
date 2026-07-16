# Website onboarding from the VS Code root

This repository is intended to be the homebase for content work across many WordPress sites. Each website lives in its own folder under `websites/<domain>/`; each folder has non-secret site settings, content folders, and a private `.env` file that is intentionally ignored by Git.

## Current website folders

- `7ohwrecked.me`
- `aivideo.poker`
- `geminiexporter.shop`
- `keywordresearcher.shop`
- `olive-manatee-953565.hostingersite.com`
- `praytoday.shop`
- `salesforcecertready.shop`
- `salesforcetogithub.shop`
- `sfdcboss.com`
- `sfdcmkdocs.shop`
- `sfdcnotebooks.shop`

## Add one or more sites

From VS Code, run **Terminal → Run Task → Factory: Create website folder(s)** and enter one or more domains separated by spaces:

```text
example-one.com example-two.shop blog.example-three.com
```

Equivalent CLI:

```bash
.venv/bin/python -m wp_factory new-site example-one.com example-two.shop blog.example-three.com
```

The command is safe to rerun: existing website folders are reported and left unchanged. New folders are scaffolded from an existing configured site, but `.env`, `.wp-factory/`, and `media_out/` are not copied.

## Connect a new site

For each new `websites/<domain>/` folder:

1. Copy `.env.example` to `.env`.
2. In WordPress, create an Application Password for the content user.
3. Put the username and application password in `.env`.
4. Run **Factory: 2 - Test connection** for that domain.
5. Run **Factory: 3 - Lint Markdown**.
6. Run **Factory: 4 - Preview sync plan** before any push.
7. Run **Factory: 5 - Push site** only after the plan is expected.
8. Run **Factory: Verify live records** after pushing.

## Design notes

- Keep VS Code as the command center: all routine commands are available as tasks from the repository root.
- Treat `site.yaml` and content Markdown as shareable source; treat `.env` and `.wp-factory/` as local/private state.
- Prefer adding content in `content/posts/`, `content/pages/`, `content/categories/`, `content/tags/`, and `content/media/` so the existing lint/plan/push workflow can reason about it.
- Do not put production passwords, cookies, or generated reports in Git.
