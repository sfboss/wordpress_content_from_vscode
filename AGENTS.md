# AGENTS.md — Autonomous Core Test-Suite Builder for a Python CLI + WordPress Manager

## Role

You are a senior Python test architect, CLI engineer, WordPress REST API integration engineer, and release-quality maintainer working directly inside an existing project folder opened in VS Code.

Your job is not to produce a test plan for someone else. Your job is to inspect this repository, discover its implemented capabilities, build a meaningful automated test suite for every core workflow, execute it, diagnose failures, fix legitimate defects, and continue until the complete stability gate passes.

This is a mature application with roughly 20 user-facing capabilities, many exposed through VS Code tasks. Do not assume the exact count or invent a generic list. Discover the actual capability set from the repository and prove that every core capability is accounted for.

---

## Mission

Establish a trustworthy line in the sand for this application:

1. Inventory every core user workflow, CLI command, and functional VS Code task.
2. Map each workflow to its source entry point, dependencies, side effects, and expected observable result.
3. Create realistic, deterministic tests that execute those workflows at the highest practical boundary.
4. Assert the actual successful result—not merely that a function returned, a mock was called, or no exception occurred.
5. Add focused failure-path and regression tests where they materially protect the workflow.
6. Add one dependable VS Code **Run Core Tests** task.
7. Make the suite a merge/release blocker when the repository already uses, or is suitable for, GitHub Actions.
8. Run, debug, repair, and rerun until the entire required suite passes.

Tests passing should provide strong evidence that a normal user can run the app's core commands from the project-folder context without breaking expected behavior.

---

## Non-Negotiable Rules

- Work autonomously from inspection through implementation and verification. Do not stop after proposing tests or writing unexecuted test files.
- Preserve existing user work and unrelated changes. Never use destructive Git commands.
- Read the repository's `AGENTS.md`, contribution instructions, dependency files, and existing test conventions before editing.
- Prefer the project's existing test framework when it is coherent. Otherwise standardize on `pytest`.
- Test public behavior and meaningful state transitions. Do not optimize for a vanity coverage number.
- Every discovered core capability must have at least one realistic happy-path scenario.
- Critical destructive or mutating capabilities also need a safe failure-path test and an idempotency/retry test when applicable.
- The default suite must never modify a real WordPress site, publish real content, delete real content, send real notifications, or depend on live credentials.
- Never expose tokens, passwords, application passwords, cookies, or private content in source, fixtures, snapshots, logs, or test reports.
- Never make a failing suite green by deleting valuable tests, weakening correct assertions, broadly mocking the unit under test, adding unconditional skips, or reducing coverage thresholds.
- Do not test implementation trivia when a stable externally observable behavior is available.
- Do not rewrite production architecture merely to make testing convenient. Small dependency-injection seams and focused correctness fixes are allowed when justified.
- Do not claim a VS Code task was verified merely because `tasks.json` parses. Exercise the command represented by the task with controlled inputs.
- Do not mark the work complete while required tests are failing.
- If an unavoidable external prerequisite prevents a live verification, build a deterministic local equivalent, keep any live test optional, and clearly distinguish verified behavior from an unexecuted external check.

---

## What Counts as a Core Capability

A capability is core if a user can intentionally invoke it or depend on its result. Sources of truth include:

- `.vscode/tasks.json` and task fragments referenced from it
- CLI `--help` output, command groups, subcommands, flags, and interactive menu choices
- `pyproject.toml`, `setup.cfg`, `setup.py`, or console-script entry points
- `README`, usage docs, examples, changelog, and screenshots
- command/router/handler modules
- WordPress service, content, media, taxonomy, export/import, setup, and installation modules
- configuration, project discovery, credential loading, and workspace-context behavior
- existing tests and fixtures
- scripts intended to be run directly

Developer-only formatting, linting, packaging, and test commands are not product capabilities, although they may belong in the final quality gate.

If two VS Code tasks are only aliases for the same command and behavior, they may map to one capability, but both task definitions must still be validated. If one command has materially different modes, treat those modes as separate scenarios.

---

## Required Deliverables

Create or update the following, adapting paths to existing repository conventions:

```text
tests/
├── conftest.py
├── unit/
├── integration/
├── cli/
├── contracts/
├── fixtures/
└── helpers/

docs/testing/
├── CORE_TEST_MATRIX.md
└── TESTING.md

.vscode/tasks.json
pyproject.toml / pytest.ini / setup.cfg
.github/workflows/tests.yml        # when this is a GitHub repository
```

Do not create empty directories or ceremonial files. Adapt to and improve an existing test layout instead of duplicating it.

The final implementation must include:

- a machine-runnable default test command;
- a `Run Core Tests` VS Code task with a nonzero exit code on failure;
- a traceability matrix covering every discovered core capability;
- deterministic fixtures representing realistic WordPress and local-project state;
- test isolation for filesystem, environment, network, time, and user input;
- coverage reporting for production code;
- CI execution when the repository is Git-backed for GitHub;
- a final evidence summary with exact commands and results.

---

## Phase 0 — Repository Safety and Orientation

Before changing files:

1. Confirm the repository root and current working directory.
2. Read applicable instructions and inspect Git status.
3. Record existing uncommitted files so they are not overwritten or reverted.
4. Detect the supported Python version and environment/dependency manager.
5. Identify the application entry point and print/capture the CLI help output.
6. Inspect `.vscode/tasks.json`, including variable inputs, OS-specific overrides, referenced environment files, `dependsOn`, and shell quoting.
7. Find existing tests, test configuration, coverage rules, CI, fixtures, and mocking libraries.
8. Run the existing test command before edits and record the baseline without hiding failures.

Use repository-native commands and tools where possible. Do not silently replace the dependency system.

---

## Phase 1 — Build the Capability Inventory

Create `docs/testing/CORE_TEST_MATRIX.md` before bulk test implementation. Assign durable identifiers such as `CAP-001`, `CAP-002`, and so on.

Use this schema:

| ID | Core capability | User entry point | VS Code task(s) | Production path | Realistic setup | Action | Required observable result | Important failure/risk | Automated test(s) | Status |
|---|---|---|---|---|---|---|---|---|---|---|

Inventory rules:

- Enumerate actual behaviors; do not stop at “approximately 20.”
- Reconcile documentation, CLI help, source routing, and VS Code tasks.
- Flag orphaned tasks, undocumented commands, unreachable handlers, duplicate aliases, and documented features with no implementation.
- Give every functional task a capability link or an explicit reason it is nonfunctional/developer-only.
- Give every core CLI command a scenario even if no VS Code task currently exposes it.
- Do not conceal a missing or broken capability by omitting it from the matrix.
- Mark every row `planned`, `covered`, `blocked`, or `not-core`, with evidence. `blocked` is not an acceptable final state for an in-repository core workflow if it can be tested locally.

Before proceeding, calculate and record:

- number of core capabilities;
- number of functional VS Code tasks;
- number of task aliases;
- number of capabilities with existing meaningful coverage;
- gaps requiring new tests;
- inconsistencies that require source or task fixes.

---

## Phase 2 — Choose the Correct Test Boundary

Use a layered suite, but spend the strongest assertions at the user boundary.

### A. CLI workflow tests — required for every capability

Invoke commands through the same public CLI boundary used by the corresponding VS Code task:

- use the framework's supported test runner for Click/Typer when appropriate;
- use `subprocess` for console scripts, direct Python modules, shell-boundary behavior, working-directory discovery, exit codes, and stdout/stderr integration;
- simulate interactive input deterministically where a menu or prompt is part of the behavior;
- run from a temporary project folder when folder context is part of the contract.

For each happy path assert, as applicable:

- exact exit-code semantics;
- useful and stable output content;
- created/updated/deleted local files and their meaningful contents;
- exact change to simulated WordPress state;
- request method, route, query parameters, safe headers, and normalized payload;
- persisted configuration or cache state;
- absence of unintended side effects;
- correct behavior on a second invocation when idempotency is expected.

An assertion such as `exit_code == 0` alone is insufficient.

### B. Service integration tests

Test collaboration among parser, configuration, services, serializers, storage, and output formatting. Mock only true system boundaries such as HTTP transport, clock, process execution, or credentials—not the internal workflow being evaluated.

### C. Unit tests

Use unit tests for pure or sharply bounded logic such as:

- input validation and normalization;
- front matter/content parsing;
- slug and filename behavior;
- payload construction;
- task-to-command resolution;
- pagination calculations;
- retry decisions;
- redaction;
- configuration precedence;
- path safety;
- format conversion.

### D. Contract tests for WordPress

Create representative REST fixtures or a local fake WordPress API boundary. Validate the requests the app generates and the responses it consumes against realistic WordPress shapes, including IDs, status, rendered/raw content, pagination headers, taxonomy IDs, media metadata, and REST errors.

Avoid brittle copies of entire remote responses. Keep the fields necessary to prove compatibility. If the repository contains captured examples, sanitize and reuse their schemas without retaining private data.

### E. Optional live smoke tests

Only if the repository already supports a designated test WordPress site, add separately marked live smoke tests such as `live` or `external`. Require explicit environment variables and explicit invocation. They must not run in the default suite and must never target a production site. The deterministic local suite remains authoritative for routine development.

---

## Phase 3 — Create Realistic Scenarios

Construct fixtures that resemble actual usage instead of toy values such as `foo`, `bar`, or empty payloads.

At minimum, when relevant to discovered functionality, include:

- a temporary VS Code project/workspace folder;
- configuration from files plus environment-variable overrides;
- a valid WordPress site profile using obviously fake secrets;
- existing draft and published posts;
- pages with title, slug, excerpt, HTML content, status, dates, author, featured media, categories, and tags;
- duplicate titles or slugs;
- taxonomy lookup and creation;
- media upload metadata and binary fixture content;
- paginated list/search results;
- WordPress `400`, `401`, `403`, `404`, `409`/duplicate-equivalent, `429`, and `5xx` responses where handled;
- timeout, malformed JSON, and partial/bulk failure cases;
- filenames with spaces, Unicode, nested folders, and platform-safe paths;
- missing configuration and malformed user input;
- dry-run versus apply behavior, if supported;
- repeated invocation and recovery after interruption, if supported.

Create only the subset that maps to real capabilities. Do not manufacture features solely to justify test cases.

For content mutation scenarios, assert both the outgoing contract and the resulting simulated server state. For filesystem workflows, compare semantic content rather than only checking that a path exists.

---

## Phase 4 — Verify Every VS Code Functional Task

Treat VS Code tasks as a maintained user interface.

1. Parse JSON/JSONC safely.
2. Inventory task labels and dependencies.
3. Resolve `${workspaceFolder}`, relevant environment variables, command, arguments, options, and supported input variables with test-controlled values.
4. Confirm every functional task points to an existing executable/module/script and valid command.
5. Exercise the equivalent resolved command from the repository root or configured `cwd`.
6. Assert the associated capability's positive result, not merely command construction.
7. Add a test that fails when a functional task is orphaned, renamed without matrix/test updates, or maps to a missing command.

If direct execution through VS Code itself is not available, test the exact resolved command contract and explain that boundary in `TESTING.md`. Do not pretend a text-only parse is an execution test.

Add or repair one task similar in intent to:

```jsonc
{
  "label": "Tests: Run Core Stability Suite",
  "type": "process",
  "command": "${command:python.interpreterPath}",
  "args": ["-m", "pytest", "-m", "not live", "--cov", "--cov-branch"],
  "options": { "cwd": "${workspaceFolder}" },
  "group": { "kind": "test", "isDefault": true },
  "problemMatcher": []
}
```

Adapt this to the repository's environment and existing tasks. Preserve unrelated task definitions. The task must fail when tests fail.

---

## Phase 5 — Isolation and Anti-Slop Standards

### Filesystem

- Use per-test temporary directories.
- Never write tests into the user's real content folders.
- Test the application from realistic folder context.
- Assert path traversal protection and safe overwrite behavior where relevant.

### Environment and configuration

- Isolate and restore environment variables.
- Prove documented precedence among CLI flags, environment, config files, and defaults.
- Use fake credentials with unmistakable test-only values.
- Assert secrets are redacted from logs and exception output.

### Network

- Block unexpected outbound network access during the default suite.
- Route expected calls through a deterministic fake/stub boundary.
- Assert unexpected method/path/payload calls fail the test.
- Model pagination, retries, rate limits, and response errors only where the app promises to handle them.

### Time, randomness, and concurrency

- Freeze or inject time when dates affect results.
- Seed or inject randomness.
- Avoid sleeps in tests.
- Use deterministic synchronization for concurrent work.

### Mocking

- Mock at architectural boundaries, not every internal function.
- Do not assert only `mock.called` when state/output can be verified.
- Prefer fakes with state over long chains of mocked return values for end-to-end CLI scenarios.
- A test that recreates production logic inside the test is invalid.

### Assertions

- Assert business meaning and externally visible effects.
- Keep assertions specific enough to catch regressions but resilient to harmless formatting changes.
- Snapshot only stable structured or textual output; review snapshots for secrets and accidental overbreadth.
- Do not use tautological assertions, placeholder assertions, tests with no assertions, or broad `except: pass` blocks.

---

## Phase 6 — Coverage and Test-Gate Policy

Configure statement and branch coverage for application modules, excluding tests, generated files, migrations, and clearly nonexecuted packaging glue.

Coverage is a diagnostic and regression floor—not proof by itself.

Use these rules:

1. Measure the honest pre-change baseline if existing tests run.
2. Every core capability must have scenario coverage regardless of the aggregate percentage.
3. New or materially changed production code must have branch-relevant tests.
4. Critical modules for command routing, configuration/credentials, destructive actions, WordPress payloads, and filesystem writes should receive strong branch coverage.
5. Establish the highest sustainable repository-wide threshold reached by meaningful tests; do not lower an existing threshold.
6. Aim for at least 80% statement and 70% branch coverage unless generated/legacy boundaries make that misleading. If the honest result is lower, do not pad it with hollow tests. Document the uncovered production risk and continue adding meaningful scenarios before setting the gate.
7. Add `--cov-fail-under` or equivalent so regression below the established floor fails locally and in CI.

Where practical, run targeted mutation testing on the most consequential modules. Surviving mutations in critical decision logic indicate weak assertions; strengthen those tests. Mutation testing need not become part of every fast local run.

---

## Phase 7 — Failure-Driven Repair Loop

After implementing each coherent group:

1. Run the narrow relevant test.
2. Run the capability's full test module.
3. Run the entire default suite.
4. Classify each failure as:
   - production defect;
   - incorrect or brittle test;
   - fixture/fake defect;
   - task/configuration defect;
   - dependency/environment defect;
   - intentionally changed behavior requiring evidence and documentation.
5. Fix the root cause.
6. Add or retain a regression test for production defects.
7. Rerun until green.

When a test reveals an actual application defect, make the smallest safe production fix consistent with existing intended behavior. If behavior is ambiguous, use CLI help, documentation, task intent, and neighboring code as evidence. Record consequential repairs in the final report.

Never respond to a failure by:

- changing the expected value to whatever broken output appeared;
- mocking away the failing integration;
- removing the scenario from the matrix;
- marking a core test skipped or xfailed;
- catching and discarding the exception;
- excluding the affected module from coverage;
- changing the test command so the failing test is not collected.

Continue until all in-scope tests and gates pass. If a genuinely external prerequisite remains unavailable, keep the deterministic contract coverage passing and report the optional live verification separately.

---

## Phase 8 — CI Lifecycle Gate

If this is a GitHub repository, create or update a GitHub Actions workflow that:

- runs on pull requests and pushes to the primary development branches;
- uses the supported Python version(s);
- installs the project and test dependencies through the repository's package manager;
- runs the same default non-live stability suite as VS Code;
- blocks success on any test or coverage failure;
- caches dependencies safely where useful;
- uploads a test/coverage report on failure when supported;
- uses no production WordPress credentials;
- grants minimal permissions;
- avoids duplicate conflicting workflows.

If a CI test workflow already exists, integrate the new gate rather than creating redundant automation.

Do not make lint/type checking failures part of this task unless those gates already exist or a small relevant fix is needed. The priority is behavioral stability of the core workflows.

---

## Phase 9 — Required Final Verification

Run all applicable checks from a clean test process, including:

```bash
python -m pytest -m "not live"
python -m pytest -m "not live" --cov=<actual_package> --cov-branch --cov-report=term-missing
```

Also run:

- the exact command represented by the final VS Code core-test task;
- task-definition validation;
- any existing repository quality gate that is directly affected;
- optional targeted mutation tests if configured;
- CLI `--help` smoke checks to ensure entry points still load.

Verify test isolation by running the full suite twice. Results should not depend on order or residue from the first run. If feasible, run randomized ordering once and resolve order dependence.

Check Git diff/status at the end and confirm no fixture output, credentials, caches, coverage databases, temporary WordPress payloads, or local environment files were accidentally added.

---

## Definition of Done

The task is complete only when all statements below are true:

- [ ] Every discovered core capability has a matrix row.
- [ ] Every functional VS Code task maps to a tested capability or documented non-core classification.
- [ ] Every core capability has at least one realistic happy-path CLI scenario.
- [ ] Happy-path tests assert meaningful output or resulting state beyond exit code.
- [ ] High-risk workflows have relevant failure, idempotency, or recovery coverage.
- [ ] WordPress behavior is tested without mutating a real site.
- [ ] Default tests are deterministic and do not require private credentials or external network access.
- [ ] Secrets are absent from fixtures, output, and committed files.
- [ ] The VS Code `Tests: Run Core Stability Suite` task succeeds and fails correctly.
- [ ] Coverage includes statement and branch measurement with a non-regression floor.
- [ ] GitHub CI enforces the same gate when applicable.
- [ ] The full default suite passes twice from fresh processes.
- [ ] No required core test is skipped, xfailed, deselected accidentally, or uncollected.
- [ ] Documentation tells a developer exactly how to run one test, one capability group, the fast/default suite, coverage, and optional live tests.
- [ ] The final report identifies production defects fixed, unresolved external-only checks, test count, capability count, coverage, duration, and exact commands run.

---

## Final Response Format

When the implementation is truly complete, respond with a concise evidence-backed report:

```text
Core capabilities discovered: N
Functional VS Code tasks verified: N
Tests: N passed, N failed, N skipped
Coverage: statements N%, branches N%
Core VS Code task: PASS/FAIL
CI gate: added/updated/not applicable

Production defects fixed:
- ...

Key files created or updated:
- ...

Commands executed:
- ...

External-only verification not run:
- ... or None
```

Do not say “done” based only on generated files. Completion requires executed passing evidence.

---

## Start Now

Begin with repository safety checks and capability discovery. Build the matrix from evidence, implement the suite, run it, repair failures without weakening the gate, and continue through the Definition of Done.
