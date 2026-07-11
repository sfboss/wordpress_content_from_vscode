---
title: Hello from the Content Factory
slug: hello-from-content-factory
status: draft
excerpt: A small post used to prove Markdown, media, taxonomy, and REST syncing.
categories:
  - factory-news
tags:
  - markdown
  - vscode
featured_image: ../media/content-workflow.png
images:
  ../media/content-workflow.png:
    alt: Diagram showing Markdown moving from VS Code into WordPress
    title: VS Code to WordPress content workflow
    caption: One folder, one preview, one controlled sync.
---

# Markdown becomes WordPress content

This paragraph includes **bold**, *italic*, ~~strikethrough~~, `inline code`, and a [link to WordPress](https://wordpress.org/).

> The local Markdown file remains the source used for intentional updates.

## A two-by-two table

| Local | WordPress |
| --- | --- |
| Markdown | HTML |
| Relative image | Media Library URL |

## Lists

- A normal bullet
- A second bullet
  - A nested bullet

1. Lint
2. Preview
3. Push
4. Verify

- [x] CommonMark content
- [ ] Publish when ready

## Image

![Diagram showing Markdown moving from VS Code into WordPress](../media/content-workflow.png "VS Code to WordPress")

## Code

```python
print("WordPress content, without opening wp-admin")
```

Term with a definition
: Definition lists are supported by the renderer.

Footnotes work too.[^1]

[^1]: The generated HTML is sent through the core REST API.

