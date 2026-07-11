# Safe addon path

Build additions as explicit, testable adapters around the existing lint → plan → push → verify lifecycle.

## Best next additions

1. **Internal link resolver:** resolve `wp://posts/slug` and `wp://pages/slug` through state, then fail lint on missing targets.
2. **SEO adapter:** one adapter per installed plugin/version; discover writable REST schema first, map `seo_title`, `meta_description`, canonical URL, and social fields, then read them back.
3. **Outbound link assistant:** propose links in a report or patch; never silently insert them during push.
4. **Outline generator:** create new draft Markdown from a template while preserving the deterministic frontmatter contract.
5. **Image assistant:** generate filename/alt/title/caption suggestions, but require lint approval before upload.
6. **WooCommerce adapter:** separate namespace and credentials; validate SKU, prices, inventory, categories, variations, and image galleries with dry-run default.
7. **Custom post type adapter:** discover `show_in_rest` post types and their schema; require an explicit per-site mapping.

An addon should never edit themes/plugins, touch Hostinger files, publish without the file's explicit status, send secrets to reports/Slack, or bypass conflict detection.

