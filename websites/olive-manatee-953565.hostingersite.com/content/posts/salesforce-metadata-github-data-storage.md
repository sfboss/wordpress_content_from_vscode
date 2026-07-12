---
categories:
- security
excerpt: Salesforce metadata and Salesforce record data have different risk, retention,
  and recovery requirements. They should not be treated as one backup artifact.
slug: salesforce-metadata-github-data-storage
status: publish
tags:
- google-drive
- retention
- salesforce-data
- security
title: Metadata in GitHub, record data in approved storage
wp_id: 24
---

Salesforce metadata is source-like material: objects, fields, flows, permission definitions, Apex, and other configuration. It belongs naturally in a version-controlled repository when access is properly restricted.

Salesforce record data is different. It may contain personal, financial, health, contractual, or operational information. Placing broad CSV exports into GitHub merely because a workflow can do it is not a sound default.

## A cleaner separation

- GitHub stores metadata, workflow code, runbooks, and change reports.
- An approved storage destination holds record-data exports when they are required.
- Retention, encryption, access, and recovery expectations are documented for the data destination.
- Only summaries or manifests needed for auditability are committed to the repository.

This separation keeps the source-control system useful without turning it into an accidental data warehouse.
