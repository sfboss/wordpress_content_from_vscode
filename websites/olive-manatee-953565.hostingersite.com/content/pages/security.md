---
excerpt: Baseline principles Begin with a development org or sandbox. Use a private
  repository with named owners. Keep credentials in an approved secret store, never
  in committed files. Use minimum required […]
slug: security
status: publish
title: Security
wp_id: 9
---

## Baseline principles

- Begin with a development org or sandbox.
- Use a private repository with named owners.
- Keep credentials in an approved secret store, never in committed files.
- Use minimum required workflow and repository permissions.
- Default to metadata-only retrieval.
- Do not write production data to GitHub.
- Define retention, access, notification, and credential rotation before production.

## Authorization paths

The simplest pilot may use an approved Salesforce CLI authorization artifact stored as a repository or environment secret. Organizations with stronger controls can scope a dedicated OAuth client and certificate-based flow. The final method depends on the company’s security requirements and current Salesforce platform capabilities.

## What the implementation does not claim

This service does not make a company compliant by itself, replace counsel or security review, or provide a managed backup service-level agreement. It creates an inspectable technical baseline that can be hardened to the requirements the company defines.

## Data handling

Metadata source belongs in the repository. Salesforce record data is handled separately and only sent to an approved destination after access, retention, encryption, and recovery expectations are documented.
