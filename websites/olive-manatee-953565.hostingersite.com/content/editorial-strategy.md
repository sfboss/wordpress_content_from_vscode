# Salesforce and GitHub editorial strategy

This file is an editorial map and is not synchronized as a WordPress post or page.

## Taxonomy

- **Salesforce Source Control** is the parent topic and the plain-language entry point.
  - **Metadata Resilience** covers backup boundaries, snapshots, drift, history, and recovery.
  - **GitHub Automation** covers scheduled workflows, repository plumbing, and operational visibility.
  - **Release Governance** covers pull requests, reviews, ownership, validation, and deployment evidence.
  - **Security and Access** covers credentials, permissions, secret storage, record-data boundaries, and production readiness.

## Keyword and intent map

### Cluster A — foundation (existing)

| Article | Primary keyword | Search intent | Funnel role |
| --- | --- | --- | --- |
| Salesforce source control: a practical GitHub foundation | salesforce source control | Understand the model and business value | Pillar / discovery |
| Salesforce metadata backup to GitHub: what it protects | salesforce metadata backup | Compare metadata history with backup expectations | Education / qualification |
| Salesforce GitHub integration with Actions | salesforce github integration | Learn the implementation architecture | Technical consideration |
| Salesforce org drift detection with Git | salesforce org drift detection | Detect and investigate untracked org changes | Operational problem-solving |
| Restore Salesforce metadata from GitHub | restore salesforce metadata from github | Plan and execute a controlled recovery | High-intent problem-solving |
| Secure GitHub Actions for Salesforce | github actions salesforce security | Harden credentials, workflow permissions, and production access | Risk / decision support |
| Salesforce deployment validation with GitHub Actions | salesforce deployment validation | Validate metadata, tests, and deployment readiness before production | Technical implementation |
| Salesforce metadata repository structure | salesforce metadata repository structure | Organize source, manifests, packages, automation, and ownership | Technical implementation |

### Cluster B — expansion (this batch)

| Article | Primary keyword | Search intent | Funnel role | Category |
| --- | --- | --- | --- | --- |
| Salesforce change sets vs GitHub | salesforce change sets vs github | Compare legacy packaging with source control | Discovery / comparison | salesforce-source-control |
| Salesforce CI/CD with GitHub Actions | salesforce ci cd github actions | Design an automated delivery pipeline | Technical implementation | github-automation |
| Salesforce pull request metadata review | salesforce pull request review | Review config and code changes in GitHub | Operational enablement | release-governance |
| Salesforce package.xml manifest strategy | salesforce package.xml | Scope retrieval and deployment with manifests | Technical implementation | salesforce-source-control |
| Salesforce git branching strategy | salesforce git branching strategy | Choose a branch model that fits Salesforce delivery | Technical consideration | release-governance |
| Connect Salesforce sandbox to GitHub | connect salesforce sandbox to github | Stand up a safe non-production pilot | Onboarding / pilot | github-automation |
| Salesforce JWT authentication for GitHub Actions | salesforce jwt authentication github actions | Authenticate automation without interactive login | Security / implementation | security-access |
| Salesforce metadata vs data backup | salesforce metadata vs data backup | Separate configuration history from record recovery | Education / qualification | metadata-resilience |
| Salesforce release management with GitHub | salesforce release management github | Govern releases with evidence and ownership | Decision support | release-governance |
| Monitor Salesforce GitHub Actions workflows | monitor salesforce github actions | Keep snapshots and pipelines reliable in production | Operational reliability | github-automation |

## Editorial rules for this cluster

- Keep one primary keyword per article; use close variants only where they read naturally.
- Explain that metadata versioning is not a complete record-data backup service.
- Prefer a development org or sandbox for the first proof of value.
- Link to official Salesforce and GitHub documentation when a reader needs command or platform behavior details.
- Treat brackets beginning with `IMAGE PROMPT` as editorial placeholders, not published images.
- Add internal links after the final WordPress URLs are known. Suggested anchors are called out in each draft.
- Target roughly 2,400–2,800 words for long-form cluster articles.
- Open with the primary keyword in the first paragraph in natural prose.
- Status for new drafts is `draft` until human review and image generation are complete.
