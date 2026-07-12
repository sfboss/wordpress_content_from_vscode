# Salesforce and GitHub editorial strategy

This file is an editorial map and is not synchronized as a WordPress post or page.

## Taxonomy

- **Salesforce Source Control** is the parent topic and the plain-language entry point.
  - **Metadata Resilience** covers backup boundaries, snapshots, drift, history, and recovery.
  - **GitHub Automation** covers scheduled workflows, repository plumbing, and operational visibility.
  - **Release Governance** covers pull requests, reviews, ownership, validation, and deployment evidence.
  - **Security and Access** covers credentials, permissions, secret storage, record-data boundaries, and production readiness.

## Keyword and intent map

| Article | Primary keyword | Search intent | Funnel role |
| --- | --- | --- | --- |
| Salesforce source control: a practical GitHub foundation | salesforce source control | Understand the model and business value | Pillar / discovery |
| Salesforce metadata backup to GitHub: what it protects | salesforce metadata backup | Compare metadata history with backup expectations | Education / qualification |
| Salesforce GitHub integration with Actions | salesforce github integration | Learn the implementation architecture | Technical consideration |
| Salesforce org drift detection with Git | salesforce org drift detection | Detect and investigate untracked org changes | Operational problem-solving |
| Restore Salesforce metadata from GitHub | restore salesforce metadata from github | Plan and execute a controlled recovery | High-intent problem-solving |
| Secure GitHub Actions for Salesforce | github actions salesforce security | Harden credentials, workflow permissions, and production access | Risk / decision support |

## Editorial rules for this cluster

- Keep one primary keyword per article; use close variants only where they read naturally.
- Explain that metadata versioning is not a complete record-data backup service.
- Prefer a development org or sandbox for the first proof of value.
- Link to official Salesforce and GitHub documentation when a reader needs command or platform behavior details.
- Treat brackets beginning with `IMAGE PROMPT` as editorial placeholders, not published images.
- Add internal links after the final WordPress URLs are known. Suggested anchors are called out in each draft.
