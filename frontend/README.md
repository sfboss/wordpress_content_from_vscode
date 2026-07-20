# WordPress Content Factory — Web UI

Local dashboard that mirrors every functional VS Code task in `.vscode/tasks.json` and the `wp_factory` CLI.

- **Websites** appear as project folders under `websites/` (traffic-light red / yellow / green)
- **Ready tab** (default): score + prioritized TODOs to get a site to **Ready**
  - Green / yellow / red KPIs for posts, pages, categories, docs ready, credentials
  - Every deficit has **action buttons** (open file, run fixer, SEO audit, plan/push, …)
  - Per-document fix queue from the publish checklist
- **Workflow**: doctor → lint → plan → push → pull → verify
- **Multi-site**: plan all / push all
- **Tools**: image fixer, linkers, dashboard, SEO suite, content overlap, inventory, calendar, refresh, etc.
- **Content browser** for posts/pages/media
- **Reports** open JSON/HTML artifacts under `reports/<site>/`
- **Console** streams the same CLI the tasks run

Nothing in the core package is replaced. The UI shells:

```text
.venv/bin/python -m wp_factory …
```

## Quick start

From the repository root (with the project venv already set up):

```bash
.venv/bin/python -m pip install -r frontend/requirements.txt
.venv/bin/python frontend/server.py
```

Or use the helper:

```bash
./frontend/run.sh
```

Open **http://127.0.0.1:8765**

Optional environment:

| Variable | Default | Meaning |
|---|---|---|
| `WP_FACTORY_UI_HOST` | `127.0.0.1` | Bind address |
| `WP_FACTORY_UI_PORT` | `8765` | Port |

## VS Code

Run task **Factory: Open Web UI**.

## Safety

- Push, pull, push-all, featured-image fixer, setup, and new-site require an explicit confirm in the UI.
- Credentials from `websites/*/.env` are never sent to the browser.
- The UI is intended for local use only (`127.0.0.1` by default).

## Layout

```text
frontend/
├── README.md
├── requirements.txt
├── run.sh
├── server.py          # FastAPI app + task runner
└── static/
    ├── index.html
    ├── styles.css
    └── app.js
```
