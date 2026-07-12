---
categories:
- implementation
excerpt: A development-org pilot lets the team learn repository structure, authorization,
  retrieval behavior, and workflow failures before production access is involved.
slug: salesforce-github-dev-org-first
status: publish
tags:
- dev-org
- github-repository
- pilot
- salesforce-cli
title: Why the first Salesforce-to-GitHub connection should be a dev org
wp_id: 23
---

The first goal is not to prove that a script can reach production. The goal is to prove that the team understands the repository, the authorization path, the metadata scope, and the workflow output.

## What the pilot should demonstrate

- A private repository with clear ownership
- A repeatable authorization method
- A successful metadata retrieval
- A scheduled workflow that creates a useful commit
- A failure path the team can diagnose
- A documented way to revoke access

## Why this reduces resistance

Admins and managers can inspect a real result without accepting production risk. Developers can refine the project structure and automation. Security stakeholders can review the exact credentials and permissions before the production decision.
