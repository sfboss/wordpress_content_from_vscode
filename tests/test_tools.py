from pathlib import Path

from wp_factory.config import MediaConfig, SiteConfig
from wp_factory.dashboard import write_dashboard_html
from wp_factory.seo_tools import (
    run_publish_readiness,
    run_readability,
    run_schema_suggest,
    run_seo_audit,
    write_tool_html,
)
from wp_factory.tools import (
    HTML_REPORT_TOOLS,
    _target_docs,
    list_tools,
    run_image_fixer,
    run_internal_linker,
    run_site_dashboard,
)


def make_tool_site(tmp_path: Path) -> SiteConfig:
    directory = tmp_path / "websites" / "site.test"
    posts = directory / "content" / "posts"
    pages = directory / "content" / "pages"
    media = directory / "content" / "media"
    posts.mkdir(parents=True)
    pages.mkdir(parents=True)
    media.mkdir(parents=True)
    (media / "hero.jpg").write_bytes(b"fake")
    long_body = (
        "Alpha guide for salesforce source control is the daily practice teams need. "
        "It explains how GitHub keeps configuration visible and reviewable. "
        * 40
    )
    (posts / "alpha.md").write_text(
        "---\n"
        "title: Salesforce source control Alpha Guide\n"
        "slug: salesforce-source-control-alpha-guide\n"
        "status: draft\n"
        "excerpt: Salesforce source control Alpha Guide helps teams version metadata in GitHub with a clear daily practice and recovery path.\n"
        "focus_keyword: salesforce source control\n"
        "categories: [guides]\n"
        "featured_image: ../media/hero.jpg\n"
        "images:\n"
        "  ../media/hero.jpg:\n"
        "    alt: Helpful hero\n"
        "---\n\n"
        "## Why it matters\n\n"
        f"{long_body}\n\n"
        "## How to start\n\n"
        "See [Beta](/beta/) and the [Salesforce CLI docs](https://developer.salesforce.com/docs/). "
        "![Hero](../media/hero.jpg)\n\n"
        "## Frequently asked questions\n\n"
        "### What is source control?\n\n"
        "It is version history for configuration.\n\n"
        "### Why GitHub?\n\n"
        "Because reviews and automation live there.\n",
        encoding="utf-8",
    )
    (posts / "beta.md").write_text(
        "---\ntitle: Beta Tutorial\nslug: beta-tutorial\nstatus: draft\n---\n\nBeta tutorial mentions Salesforce source control and external research.\n",
        encoding="utf-8",
    )
    (pages / "about.md").write_text("---\ntitle: About\nslug: about\n---\n\nAbout us.\n", encoding="utf-8")
    return SiteConfig(
        key="site.test",
        directory=directory,
        site_url="https://site.test",
        api_base="https://site.test/wp-json/wp/v2",
        username="",
        app_password="",
        slack_webhook_url="",
        default_status="draft",
        timeout=10,
        verify_public_urls=False,
        media=MediaConfig(),
        raw={},
    )


def test_tool_registry_lists_expected_tools():
    names = {tool["name"] for tool in list_tools()}
    expected = {
        "image-fixer",
        "external-linker",
        "internal-linker",
        "site-dashboard",
        "seo-audit",
        "readability",
        "link-health",
        "schema-suggest",
        "publish-readiness",
        "featured-image-fixer",
    }
    assert expected <= names
    assert {
        "seo-audit",
        "featured-image-fixer",
        "content-overlap",
    } <= HTML_REPORT_TOOLS
    assert row["featured_image"] is True
    # featured-image check should pass
    feat_check = next(c for c in row["checks"] if c["name"] == "featured-image")
    assert feat_check["ok"] is True


def test_featured_image_fixer_repairs_yaml_colons(tmp_path):
    from wp_factory.featured_images import fix_featured_images, load_markdown_document

    site = make_tool_site(tmp_path)
    path = site.directory / "content" / "posts" / "colon-excerpt.md"
    (site.directory / "content" / "media" / "colon-excerpt-01.jpg").write_bytes(b"x")
    path.write_text(
        "---\n"
        "title: Colon Excerpt Demo\n"
        "slug: colon-excerpt-demo\n"
        "status: draft\n"
        "excerpt: Compare paths: what works and what does not for featured images.\n"
        "---\n\n"
        "Body with image ![x](../media/colon-excerpt-01.jpg)\n",
        encoding="utf-8",
    )
    result = fix_featured_images(site, path, apply=True)
    assert result["summary"]["updated"] >= 1 or result["summary"]["yaml_repaired"] >= 1
    post, _, _ = load_markdown_document(path)
    assert post.metadata.get("featured_image")


def test_tool_html_escapes_payload(tmp_path):
    payload = {
        "tool": "seo-audit",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"documents": 1, "average_score": 10},
        "documents": [
            {
                "document": "</script><script>alert(1)</script>",
                "title": "x",
                "score": 10,
                "band": "poor",
                "focus_keyword": "x",
                "issue_count": 1,
                "words": 12,
            }
        ],
    }
    out = write_tool_html("site.test", payload, tmp_path / "seo.json")
    html = out.read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "SEO Audit" in html
