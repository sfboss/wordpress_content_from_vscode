# Media source files

Put reusable source images here and reference them from Markdown as either:

```markdown
![Specific useful alt text](../media/file.png)
![Specific useful alt text](/media/file.png)
![Specific useful alt text](@media/file.png)
```

Images may also sit beside a Markdown file. During push, local images are resized/optimized into `media_out/`, uploaded to the WordPress Media Library, assigned alt/title/caption metadata, and their local `src` values are replaced with WordPress URLs in the submitted HTML. Originals are never modified.

