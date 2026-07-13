from pathlib import Path

from wp_factory.config import MediaConfig, SiteConfig
from wp_factory.content_overlap import run_content_overlap, write_content_overlap_html
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
    run_content_inventory,
    run_content_refresh,
    run_editorial_calendar,
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
    (posts / "gamma.md").write_text(
        "---\n"
        "title: Gamma Scheduled Tutorial\n"
        "slug: gamma-scheduled-tutorial\n"
        "status: draft\n"
        "date: 2026-08-01\n"
        "categories: guides, updates\n"
        "seo_description: Gamma scheduled tutorial has a complete metadata description for calendar testing.\n"
        "---\n\n"
        + ("Gamma content for planned editorial coverage. " * 25),
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
        "content-overlap",
    } <= names
    assert "seo-audit" in HTML_REPORT_TOOLS
    assert "featured-image-fixer" in HTML_REPORT_TOOLS
    assert "content-overlap" in HTML_REPORT_TOOLS



def test_content_inventory_flags_editorial_gaps(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_inventory(site)
    assert payload["summary"]["documents"] == 3
    beta = next(d for d in payload["documents"] if d["document"].endswith("beta.md"))
    assert "thin-content" in beta["flags"]
    assert "missing-excerpt" in beta["flags"]


def test_editorial_calendar_reports_unscheduled_blockers(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_editorial_calendar(site)
    assert payload["summary"]["unscheduled"] == 3
    beta = next(d for d in payload["calendar"] if d["document"].endswith("beta.md"))
    assert "category" in beta["blockers"]
 
        "content-inventory",
        "editorial-calendar",
        "content-refresh",
    } <= names
    assert "seo-audit" in HTML_REPORT_TOOLS
    assert "featured-image-fixer" in HTML_REPORT_TOOLS
    assert "content-inventory" in HTML_REPORT_TOOLS
 

def test_content_refresh_prioritizes_missing_review_dates(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_refresh(site)
    assert payload["summary"]["high"] == 3
    assert payload["queue"][0]["priority"] == "high"
 

def test_content_inventory_flags_editorial_gaps(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_inventory(site)
    assert payload["summary"]["documents"] == 4
    beta = next(d for d in payload["documents"] if d["document"].endswith("beta.md"))
    assert "thin-content" in beta["flags"]
    assert "missing-excerpt" in beta["flags"]
    gamma = next(d for d in payload["documents"] if d["document"].endswith("gamma.md"))
    assert gamma["categories"] == ["guides", "updates"]
    assert "missing-excerpt" not in gamma["flags"]


def test_editorial_calendar_reports_unscheduled_blockers(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_editorial_calendar(site)
    assert payload["summary"]["unscheduled"] == 3
    assert payload["summary"]["scheduled"] == 1
    beta = next(d for d in payload["calendar"] if d["document"].endswith("beta.md"))
    assert "category" in beta["blockers"]


def test_content_refresh_prioritizes_missing_review_dates(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_refresh(site)
    assert payload["summary"]["high"] == 3
    assert payload["queue"][0]["priority"] == "high"

def test_content_inventory_flags_editorial_gaps(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_inventory(site)
    assert payload["summary"]["documents"] == 3
    beta = next(d for d in payload["documents"] if d["document"].endswith("beta.md"))
    assert "thin-content" in beta["flags"]
    assert "missing-excerpt" in beta["flags"]


def test_editorial_calendar_reports_unscheduled_blockers(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_editorial_calendar(site)
    assert payload["summary"]["unscheduled"] == 3
    beta = next(d for d in payload["calendar"] if d["document"].endswith("beta.md"))
    assert "category" in beta["blockers"]
        "content-inventory",
        "editorial-calendar",
        "content-refresh",
    } <= names
    assert "seo-audit" in HTML_REPORT_TOOLS
    assert "featured-image-fixer" in HTML_REPORT_TOOLS
    assert "content-inventory" in HTML_REPORT_TOOLS

def test_content_inventory_flags_editorial_gaps(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_inventory(site)
    assert payload["summary"]["documents"] == 4
    beta = next(d for d in payload["documents"] if d["document"].endswith("beta.md"))
    assert "thin-content" in beta["flags"]
    assert "missing-excerpt" in beta["flags"]
    gamma = next(d for d in payload["documents"] if d["document"].endswith("gamma.md"))
    assert gamma["categories"] == ["guides", "updates"]
    assert "missing-excerpt" not in gamma["flags"]


def test_editorial_calendar_reports_unscheduled_blockers(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_editorial_calendar(site)
    assert payload["summary"]["unscheduled"] == 3
    assert payload["summary"]["scheduled"] == 1
    beta = next(d for d in payload["calendar"] if d["document"].endswith("beta.md"))
    assert "category" in beta["blockers"]


def test_content_refresh_prioritizes_missing_review_dates(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_refresh(site)
    assert payload["summary"]["high"] == 3
    assert payload["queue"][0]["priority"] == "high"

def test_content_refresh_prioritizes_missing_review_dates(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_refresh(site)
    assert payload["summary"]["high"] == 3
    assert payload["queue"][0]["priority"] == "high"

def test_image_fixer_can_target_one_document(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_image_fixer(site, site.directory / "content" / "posts" / "alpha.md")
    assert payload["counts"] == {"ready-for-upload": 1}
    assert payload["images"][0]["document"] == "content/posts/alpha.md"


def test_internal_linker_suggests_from_catalog(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_internal_linker(site, site.directory / "content" / "posts" / "beta.md")
    assert payload["documents"][0]["suggestions"]


def test_site_dashboard_reports_baselines(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_site_dashboard(site)
    assert payload["totals"]["posts"] == 3
    assert payload["baselines"]["minimum_posts"] == 25


def test_dashboard_html_is_self_contained_and_escapes_content(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_site_dashboard(site)
    payload["documents"][0]["document"] = "</script><script>alert(1)</script>"
    report = tmp_path / "dashboard.json"
    output = write_dashboard_html(site.key, payload, report)
    html = output.read_text(encoding="utf-8")
    assert output == tmp_path / "dashboard.html"
    assert "Content depth" in html
    assert "https://" not in html
    assert "</script><script>alert(1)</script>" not in html


def test_seo_audit_scores_documents(tmp_path):
    site = make_tool_site(tmp_path)
    docs = _target_docs(site, None)
    payload = run_seo_audit(site, None, docs)
    assert payload["summary"]["documents"] == 4
    alpha = next(d for d in payload["documents"] if d["document"].endswith("alpha.md"))
    assert alpha["score"] >= 70
    assert alpha["focus_keyword"]


def test_readability_reports_flesch(tmp_path):
    site = make_tool_site(tmp_path)
    docs = _target_docs(site, None)
    payload = run_readability(site, None, docs)
    assert "average_flesch" in payload["summary"]
    assert payload["documents"]


def test_schema_suggest_detects_faq(tmp_path):
    site = make_tool_site(tmp_path)
    docs = _target_docs(site, site.directory / "content" / "posts" / "alpha.md")
    payload = run_schema_suggest(site, None, docs)
    types = payload["documents"][0]["types"]
    assert "BlogPosting" in types
    assert "FAQPage" in types


def test_publish_readiness_queues_drafts(tmp_path):
    site = make_tool_site(tmp_path)
    docs = _target_docs(site, None)
    payload = run_publish_readiness(site, None, docs)
    assert payload["summary"]["documents"] == 4
    assert "ready" in payload["summary"]
    assert payload["queue"]


def test_featured_image_fixer_sets_first_image_and_is_idempotent(tmp_path):
    from wp_factory.featured_images import fix_featured_images, load_markdown_document
    from wp_factory.seo_tools import run_seo_audit

    site = make_tool_site(tmp_path)
    # Add a post with body image but no featured_image
    post_path = site.directory / "content" / "posts" / "needs-hero.md"
    (site.directory / "content" / "media" / "needs-hero-01.jpg").write_bytes(b"fake-jpg")
    post_path.write_text(
        "---\n"
        "title: Needs Hero Post For Featured Image\n"
        "slug: needs-hero-post-for-featured-image\n"
        "status: draft\n"
        "excerpt: Needs Hero Post For Featured Image explains how featured images get set automatically from the first local image candidate for SEO.\n"
        "categories: [guides]\n"
        "---\n\n"
        "## Intro\n\n"
        + ("Word content for depth. " * 80)
        + "\n\n![Hero shot](../media/needs-hero-01.jpg)\n",
        encoding="utf-8",
    )

    first = fix_featured_images(site, post_path, apply=True)
    assert first["summary"]["updated"] == 1
    post, _, _ = load_markdown_document(post_path)
    assert post.metadata.get("featured_image") == "../media/needs-hero-01.jpg"
    assert isinstance(post.metadata.get("images"), dict)
    assert post.metadata["images"]["../media/needs-hero-01.jpg"]["alt"]

    second = fix_featured_images(site, post_path, apply=True)
    assert second["summary"]["already_ok"] == 1
    assert second["summary"]["updated"] == 0

    docs = _target_docs(site, post_path)
    audit = run_seo_audit(site, post_path, docs)
    row = audit["documents"][0]
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


def test_content_overlap_finds_near_duplicate_and_scopes_target(tmp_path):
    site = make_tool_site(tmp_path)
    source = site.content_dir / "posts" / "alpha.md"
    duplicate = site.content_dir / "posts" / "alpha-copy.md"
    duplicate.write_text(
        source.read_text(encoding="utf-8")
        .replace("Salesforce source control Alpha Guide", "Salesforce source control Complete Guide")
        .replace("salesforce-source-control-alpha-guide", "salesforce-source-control-complete-guide"),
        encoding="utf-8",
    )
    docs = _target_docs(site, None)
    payload = run_content_overlap(site, duplicate, docs)
    assert payload["summary"]["critical"] >= 1
    assert payload["overlaps"][0]["kind"] == "near-duplicate"
    assert all(duplicate.relative_to(site.directory).as_posix() in {row["left"], row["right"]} for row in payload["overlaps"])
    assert payload["task_queue"]["manual_review"]


def test_content_overlap_html_is_self_contained_and_escapes_content(tmp_path):
    site = make_tool_site(tmp_path)
    payload = run_content_overlap(site, None, _target_docs(site, None))
    payload["documents"][0]["title"] = "</script><script>alert(1)</script>"
    output = write_content_overlap_html(site.key, payload, tmp_path / "overlap.json")
    html = output.read_text(encoding="utf-8")
    assert output == tmp_path / "overlap.html"
    assert "Search-intent neighborhood" in html
    assert "</script><script>alert(1)</script>" not in html
