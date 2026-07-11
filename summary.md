# Markdown → WordPress rendering contract

The factory uses the same `markdown-it` family as VS Code and sends semantic HTML through WordPress's core REST API. Ordinary authoring is structurally reliable. The active WordPress theme still decides typography, spacing, colors, responsive table behavior, and code styling.

## Supported and tested

| Markdown feature | Result sent to WordPress | Notes |
| --- | --- | --- |
| Paragraphs | `<p>` | Blank lines separate paragraphs. |
| ATX headings `#`–`######` | `<h1>`–`<h6>` | Prefer one page title in frontmatter and start body sections at `##` if the theme prints the title. |
| Setext headings | `<h1>` / `<h2>` | Supported. |
| Bold / italic | `<strong>` / `<em>` | Nested emphasis supported. |
| Strikethrough | `<s>` | GFM-style extension enabled. |
| Inline code | `<code>` | Escaped safely. |
| Fenced / indented code | `<pre><code>` | Language class retained on fenced blocks; theme controls highlighting. |
| Blockquotes | `<blockquote>` | Nested blocks supported. |
| Ordered/unordered lists | `<ol>` / `<ul>` | Nested lists supported. |
| Task lists | Checkbox list HTML | WordPress/theme may style disabled checkboxes differently. |
| Links | `<a href>` | HTTP(S), mailto, anchors, and ordinary relative links render. Internal `.md` links are not yet rewritten to WordPress permalinks. |
| Local images | WordPress `<img>` URL | Uploaded first; `src`, alt, and title rewritten. |
| External images | Original `<img>` URL | Not copied; empty alt produces a warning. HTTPS is recommended. |
| Tables | `<table><thead><tbody>` | A 2×2 table and larger standard pipe tables work. Theme CSS controls appearance/overflow. |
| Horizontal rules | `<hr>` | Supported. |
| Hard line breaks | `<br>` | Use two trailing spaces or an explicit `<br>`. Workspace settings preserve Markdown trailing spaces. |
| Escapes / entities | HTML-safe text | CommonMark escaping supported. |
| Autolinks | `<a>` | Linkify is enabled for URLs plus CommonMark angle-bracket autolinks. |
| Footnotes | Footnote section HTML | Enabled through a markdown-it plugin. |
| Definition lists | `<dl><dt><dd>` | Enabled through a markdown-it plugin. |
| Attribute syntax | Classes/attributes where supported | WordPress sanitization may remove attributes not allowed for the author role. |
| Raw HTML | Passed to WordPress | WordPress KSES/capabilities can strip scripts, event handlers, iframes, styles, or unsafe tags. |

## Preview differences that are deliberate

| VS Code preview feature | v1 behavior | Correct approach |
| --- | --- | --- |
| Mermaid fenced blocks | Delivered as a code block, not a rendered diagram | Export a diagram to PNG/WebP and reference it as an image, or add a deliberately chosen WordPress Mermaid plugin later. |
| KaTeX `$...$` / `$$...$$` | No math rendering guarantee | Pre-render to an image or add a tested site-side math renderer. |
| Theme-specific callouts/admonitions | No assumed styling | Use blockquotes now; add a tested HTML/component convention later. |
| Local `.md` page links | Remain local paths | Use the final site URL now; a future internal-link adapter can resolve slugs from state. |
| Embedded scripts | Expected to be stripped/blocked | Add behavior in the theme/plugin, never inside post Markdown. |
| Pixel-perfect preview parity | Not promised | The semantic HTML is consistent; WordPress theme CSS controls appearance. |

## Frontmatter and SEO contract

- `title`, `slug`, `status`, `excerpt`, taxonomy IDs, publish date, comment/ping status, template, menu order, format, sticky flag, password, and featured media use documented core REST fields.
- Image alt/title/caption/description use documented Media REST fields.
- The post `excerpt` is available to themes and is a reasonable default summary. Whether it becomes an HTML meta description is theme/SEO-plugin behavior.
- `seo_title` and `meta_description` may be kept as editorial intent, but v1 warns and does not pretend to write undocumented plugin fields.
- `rest_meta` is passed only when explicitly present. WordPress accepts only meta keys registered with `show_in_rest`; an unregistered key may be rejected or ignored.

## Reliability rules

1. Lint must pass before push.
2. Exact remote slugs are adopted only when no local state exists.
3. Local and remote modification evidence is compared before updates.
4. A two-sided edit is a conflict and blocks push unless `--force` is deliberately used.
5. Images upload before content, so submitted HTML never contains a local filesystem path.
6. Every written post/page is read back through authenticated REST.
7. Published links receive a public HTTP check during verify.
8. No task deletes WordPress content.

