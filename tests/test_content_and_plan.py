from pathlib import Path

from wp_factory.config import MediaConfig, SiteConfig, load_site
from wp_factory.content import load_documents
from wp_factory.state import StateStore
from wp_factory.sync import SiteSync


class FakeClient:
    def __init__(self, remote=None):
        self.remote = remote

    def find_by_slug(self, endpoint, slug):
        return self.remote

    def get(self, endpoint, wp_id):
        return self.remote


def make_site(tmp_path: Path) -> SiteConfig:
    directory = tmp_path / "websites" / "site.test"
    posts = directory / "content/posts"
    posts.mkdir(parents=True)
    (posts / "post.md").write_text(
        "---\ntitle: Test Post\nslug: test-post\nstatus: draft\nexcerpt: Test.\n---\n\nHello **world**.\n",
        encoding="utf-8",
    )
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
        media=MediaConfig(),
        raw={},
    )


def test_minimal_site_lints_without_failures(tmp_path):
    site = make_site(tmp_path)
    issues = SiteSync(site).lint()
    assert not [issue for issue in issues if "warning:" not in issue]


def test_plan_create_then_noop(tmp_path):
    site = make_site(tmp_path)
    sync = SiteSync(site)
    sync.client = FakeClient(None)
    first = sync.plan()
    assert [(item.action, item.document.slug) for item in first] == [("create", "test-post")]

    document = load_documents(site)[0]
    remote = {
        "id": 9,
        "slug": "test-post",
        "modified_gmt": "2026-07-10T12:00:00",
        "link": "https://site.test/test-post/",
    }
    state = StateStore.load(site.state_path)
    state.set_document(
        document.key,
        {"wp_id": 9, "local_hash": document.source_hash, "remote_modified": remote["modified_gmt"]},
    )
    state.save()
    sync = SiteSync(site)
    sync.client = FakeClient(remote)
    assert sync.plan()[0].action == "noop"


def test_plan_detects_two_sided_conflict(tmp_path):
    site = make_site(tmp_path)
    document = load_documents(site)[0]
    state = StateStore.load(site.state_path)
    state.set_document(
        document.key,
        {"wp_id": 9, "local_hash": "old-local", "remote_modified": "old-remote"},
    )
    state.save()
    remote = {
        "id": 9,
        "slug": document.slug,
        "modified_gmt": "new-remote",
        "link": "https://site.test/test-post/",
    }
    sync = SiteSync(site)
    sync.client = FakeClient(remote)
    assert sync.plan()[0].action == "conflict"

