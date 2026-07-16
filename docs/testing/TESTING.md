# Testing Guide

The default local gate is deterministic and must not contact a real WordPress site.

## Commands

Run the fast/default suite:

```bash
python -m pytest -m "not live"
```

Run one capability group:

```bash
python -m pytest tests/test_tools.py -q
```

Run one test:

```bash
python -m pytest tests/test_tools.py::test_tool_registry_lists_expected_tools -q
```

Run the release-style core gate with statement and branch coverage:

```bash
python -m pytest -m "not live" --cov=wp_factory --cov-branch --cov-report=term-missing --cov-fail-under=30
```

VS Code users can run **Tests: Run Core Stability Suite**, which executes the same coverage gate from `${workspaceFolder}` using the selected Python interpreter.

## Isolation policy

- Default tests use temporary content folders and fake WordPress/client boundaries.
- Default tests must not require `WP_USERNAME`, `WP_APP_PASSWORD`, cookies, production URLs, Slack webhooks, or network access.
- Optional live smoke tests, if added later, must be marked `live` and run only by explicit opt-in.

## Current coverage floor

The repository currently enforces a conservative 30% coverage floor while the suite expands. The matrix tracks remaining core workflow gaps so coverage is not treated as a substitute for behavior coverage.

## Website scaffold regression tests

The multi-site onboarding flow is covered by:

```bash
python -m pytest tests/test_new_site_cli.py
```

That test exercises the public CLI boundary used by the VS Code task, verifies multiple website folders can be requested in one command, confirms `.env` is not copied into Git-tracked scaffolds, and proves a second invocation leaves existing folders unchanged.
