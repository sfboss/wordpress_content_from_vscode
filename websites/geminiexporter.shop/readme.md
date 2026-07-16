# geminiexporter.shop content workspace

1. Copy `.env.example` to `.env`.
2. Add the WordPress username and Application Password to `.env`.
3. Run `wp_factory doctor --site geminiexporter.shop` or the VS Code connection task.
4. Add content under `content/posts/`, `content/pages/`, `content/categories/`, `content/tags/`, and `content/media/`.
5. Run lint, plan, push, and verify from the repository root.

Private files (`.env`, `.wp-factory/`, and `media_out/`) stay local and are ignored by Git.
