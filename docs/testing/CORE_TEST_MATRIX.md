# Core Test Matrix

Inventory date: 2026-07-13.

Summary:
- Core capabilities discovered: 23
- Functional VS Code tasks: 25
- Task aliases/compositions: 2 (`Plan all sites`, `Push all sites`; plus the composed featured-image + SEO audit task)
- Existing meaningful coverage before this pass: content loading/planning, Markdown rendering, SEO tools
- Gaps closed in this pass: conflict-marker repair, expanded tool registry coverage, VS Code core test gate validation

| ID | Core capability | User entry point | VS Code task(s) | Production path | Realistic setup | Action | Required observable result | Important failure/risk | Automated test(s) | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| CAP-001 | Setup editable Python environment | shell task | Factory: 1 - Setup Python | pyproject.toml | repository root | create venv and install dev deps | importable package and pytest runner | broken dependency metadata | CI install step | covered |
| CAP-002 | Doctor WordPress connection | `wp_factory doctor --site` | Factory: 2 - Test connection | wp_factory/cli.py, wp_factory/sync.py | fake site config | inspect authenticated REST state | JSON/report output | real credentials must not be required in default tests | CLI smoke/help plus config tests | planned |
| CAP-003 | Lint Markdown content | `wp_factory lint --site` | Factory: 3 - Lint Markdown | wp_factory/sync.py, wp_factory/content.py | temp site with post | run lint | no failure issues for valid content | bad frontmatter/images | `tests/test_content_and_plan.py::test_minimal_site_lints_without_failures` | covered |
| CAP-004 | Preview sync plan | `wp_factory plan --site` | Factory: 4 - Preview sync plan | wp_factory/sync.py | local post and fake remote | plan create/noop/conflict | meaningful action rows | two-sided edits | `tests/test_content_and_plan.py::test_plan_create_then_noop`, `test_plan_detects_two_sided_conflict` | covered |
| CAP-005 | Push site | `wp_factory push --site` | Factory: 5 - Push site | wp_factory/sync.py, wp_factory/wordpress.py | fake WordPress boundary | render and upsert | media/content payloads | unintended live mutation | covered indirectly by render tests; contract expansion planned | planned |
| CAP-006 | Pull safe remote changes | `wp_factory pull --site` | Factory: Pull safe remote changes | wp_factory/sync.py | fake remote | pull changed records | content or incoming conflict files | overwriting local edits | planned | planned |
| CAP-007 | Verify live records | `wp_factory verify --site` | Factory: Verify live records | wp_factory/sync.py | fake remote/public URL disabled | verify state | ok/fail rows | false live success | planned | planned |
| CAP-008 | Plan all sites | `wp_factory plan --all` | Factory: Plan all sites | wp_factory/cli.py | multiple site configs | enumerate sites | all site plans run | missing site discovery | planned | planned |
| CAP-009 | Push all sites | `wp_factory push --all` | Factory: Push all sites | wp_factory/cli.py | multiple fake sites | enumerate pushes | aggregate exit code | partial failure handling | planned | planned |
| CAP-010 | List tool menu | `wp_factory tools list` | Factory Tools: List menu | wp_factory/tools.py | importable registry | list JSON specs | all expected tools present | orphaned task/tool mismatch | `tests/test_tools.py::test_tool_registry_lists_expected_tools` | covered |
| CAP-011 | Image import fixer inventory | `tools run image-fixer` | Factory Tools: Image fixer (site) | wp_factory/tools.py | post with local image | scan images | ready/missing status rows | unsafe data URI/local paths | `tests/test_tools.py::test_image_fixer_can_target_one_document` | covered |
| CAP-012 | External linker | `tools run external-linker` | Factory Tools: External linker (site) | wp_factory/tools.py | post text/links | scan outbound links | candidate entities/status | thin assertions | registry/task validation | planned |
| CAP-013 | Internal linker | `tools run internal-linker` | Factory Tools: Internal linker (site) | wp_factory/tools.py | related content catalog | scan one target | suggestions from catalog | target scoping | `tests/test_tools.py::test_internal_linker_suggests_from_catalog` | covered |
| CAP-014 | Site dashboard | `tools run site-dashboard --open` | Factory Tools: Site dashboard | wp_factory/tools.py, wp_factory/dashboard.py | temp site | produce JSON/HTML | totals and escaped dashboard | XSS in reports | `test_site_dashboard_reports_baselines`, `test_dashboard_html_is_self_contained_and_escapes_content` | covered |
| CAP-015 | Featured image fixer | `tools run featured-image-fixer` | Featured images fix, Featured images then SEO audit | wp_factory/featured_images.py | post with body image | apply twice | featured image metadata; idempotent second run | YAML colon parsing | `test_featured_image_fixer_sets_first_image_and_is_idempotent`, `test_featured_image_fixer_repairs_yaml_colons` | covered |
| CAP-016 | SEO audit | `tools run seo-audit` | SEO audit, Featured images then SEO audit | wp_factory/seo_tools.py | rich post fixture | score docs | score/focus keyword/checks | overbroad report output | `test_seo_audit_scores_documents`, `test_tool_html_escapes_payload` | covered |
| CAP-017 | Readability | `tools run readability` | Factory Tools: Readability | wp_factory/seo_tools.py | content fixture | analyze prose | summary and rows | unstable text stats | `test_readability_reports_flesch` | covered |
| CAP-018 | Link health | `tools run link-health` | Factory Tools: Link health | wp_factory/seo_tools.py | link fixture | check capped URLs | statuses | live network in default tests | registry/task validation; detailed fake transport planned | planned |
| CAP-019 | Schema suggest | `tools run schema-suggest` | Factory Tools: Schema suggest | wp_factory/seo_tools.py | FAQ post | infer schema | BlogPosting/FAQPage types | invalid JSON-LD | `test_schema_suggest_detects_faq` | covered |
| CAP-020 | Publish readiness | `tools run publish-readiness` | Factory Tools: Publish readiness | wp_factory/seo_tools.py | draft fixture | queue docs | ready/blocker summary | missed blockers | `test_publish_readiness_queues_drafts` | covered |
| CAP-021 | Content overlap map | `tools run content-overlap` | Content overlap map, Check selected draft for overlap | wp_factory/content_overlap.py | duplicate posts | scope target | near-duplicate and review queue | cannibalization false negative | `test_content_overlap_finds_near_duplicate_and_scopes_target`, `test_content_overlap_html_is_self_contained_and_escapes_content` | covered |
| CAP-022 | Run selected file with chosen tool | `tools run <tool> --target` | Factory Tools: Run selected file with tool | wp_factory/cli.py, wp_factory/tools.py | active Markdown path | resolve target | selected-file results | quoting/invalid tool | task validation + targeted tool tests | covered |
| CAP-023 | Create another site scaffold | `wp_factory new-site` | Factory: Create another site folder | wp_factory/cli.py | example site scaffold | copy and rewrite config | new folder with safe domain | path traversal/overwrite | planned | planned |
| CAP-024 | Markdown rendering/media upload | internal push boundary | none direct | wp_factory/markdown_engine.py | local image fixture | render document | semantic HTML, staged image, media id | alt metadata loss | `tests/test_markdown_engine.py` | covered |
| CAP-025 | Core stability suite task | VS Code task | Tests: Run Core Stability Suite | .vscode/tasks.json | repository root | run pytest/cov command | nonzero on failure | stale test task | `tests/test_vscode_tasks.py` | covered |

Developer-only/non-core tasks: the setup task is a bootstrap helper, not a product capability; it is still represented in CI installation.
