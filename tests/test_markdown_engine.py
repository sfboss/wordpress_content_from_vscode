from pathlib import Path

from PIL import Image

from wp_factory.config import MediaConfig, SiteConfig
from wp_factory.markdown_engine import render_document, render_markdown
from wp_factory.models import Document
from wp_factory.state import StateStore
from wp_factory.utils import stable_hash


class FakeClient:
    def __init__(self):
        self.uploaded = []

    def upload_media(self, path, filename):
        self.uploaded.append((path, filename))
        return {"id": 55, "source_url": f"https://site.test/uploads/{filename}"}

    def update_media(self, media_id, payload):
        return {
            "id": media_id,
            "source_url": f"https://site.test/uploads/{self.uploaded[-1][0].name}",
            **payload,
        }

    def get(self, endpoint, wp_id):
        return {"id": wp_id, "source_url": "https://site.test/uploads/cached.png"}


def make_site(tmp_path: Path) -> SiteConfig:
    directory = tmp_path / "websites" / "site.test"
    (directory / "content/posts").mkdir(parents=True)
    return SiteConfig(
        key="site.test",
        directory=directory,
        site_url="https://site.test",
        api_base="https://site.test/wp-json/wp/v2",
        username="user",
        app_password="pass",
        slack_webhook_url="",
        default_status="draft",
        timeout=10,
        verify_public_urls=False,
        media=MediaConfig(max_width=600, strict_alt_text=True),
        raw={},
    )


def test_markdown_features_render_to_semantic_html():
    value = """# Heading

| A | B |
|---|---|
| 1 | 2 |

- [x] Done

Term
: Definition

Footnote.[^1]

[^1]: Detail
"""
    html = render_markdown(value)
    assert "<h1>Heading</h1>" in html
    assert "<table>" in html
    assert 'type="checkbox"' in html
    assert "<dl>" in html
    assert "footnote" in html


def test_local_image_is_staged_uploaded_and_rewritten(tmp_path):
    site = make_site(tmp_path)
    post_path = site.content_dir / "posts/post.md"
    image_path = site.content_dir / "posts/hero.png"
    Image.new("RGB", (1200, 400), "blue").save(image_path)
    document = Document(
        key="content/posts/post.md",
        collection="posts",
        endpoint="posts",
        path=post_path,
        metadata={"images": {"hero.png": {"alt": "Blue test banner", "title": "Test banner"}}},
        markdown="![Blue test banner](hero.png)",
        title="Post",
        slug="post",
        status="draft",
        source_hash=stable_hash("post"),
    )
    state = StateStore.load(site.state_path)
    client = FakeClient()
    rendered = render_document(document, client, state, site)
    assert "https://site.test/uploads/" in rendered.html
    assert 'alt="Blue test banner"' in rendered.html
    assert rendered.media_ids == [55]
    staged = client.uploaded[0][0]
    with Image.open(staged) as image:
        assert image.width == 600

