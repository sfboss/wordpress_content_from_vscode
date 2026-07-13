from pathlib import Path

from wp_factory.config import MediaConfig, SiteConfig
from wp_factory.tools import list_tools, run_image_fixer, run_internal_linker, run_site_dashboard


def make_tool_site(tmp_path: Path) -> SiteConfig:
    directory = tmp_path / "websites" / "site.test"
    posts = directory / "content" / "posts"
    pages = directory / "content" / "pages"
    media = directory / "content" / "media"
    posts.mkdir(parents=True)
    pages.mkdir(parents=True)
    media.mkdir(parents=True)
    (media / "hero.jpg").write_bytes(b"fake")
    (posts / "alpha.md").write_text(
        "---\ntitle: Alpha Guide\nslug: alpha-guide\nstatus: draft\ncategories: [guides]\nimages:\n  ../media/hero.jpg:\n    alt: Helpful hero\n---\n\n# Alpha\n\nSee [Beta](/beta/). ![Hero](../media/hero.jpg)\n",
        encoding="utf-8",
    )
    (posts / "beta.md").write_text(
        "---\ntitle: Beta Tutorial\nslug: beta-tutorial\nstatus: draft\n---\n\nBeta tutorial mentions Alpha Guide and external research.\n",
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
    assert {"image-fixer", "external-linker", "internal-linker", "site-dashboard"} <= names


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
    assert payload["totals"]["posts"] == 2
    assert payload["baselines"]["minimum_posts"] == 25
