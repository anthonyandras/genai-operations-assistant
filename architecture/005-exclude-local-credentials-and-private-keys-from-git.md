# ADR 005: Exclude local credentials and private keys from Git

- Status: Accepted
- Decision date: 2026-11-22
- Source commit: `8ec8f7c` — Ignore local environment files, AWS credentials, and private keys
- Related: [ADR 004](004-provide-a-streaming-api-with-selectable-http-protocols.md), which initially excludes `.certs/`

## Context

Local development may create environment files, AWS credential directories, and
TLS or SSH private keys. The source commit records a preventive repository
hygiene change; it does not report an actual credential disclosure.

## Decision

Extend `.gitignore` to exclude `.env`, `.env.*`, `.aws/`, PEM/key files, PKCS#12
bundles, and common SSH private-key filenames. Preserve exceptions for
`.env.example` and `.env.*.example` so placeholder configuration can be shared.
Continue excluding the local `.certs/` directory.

## Consequences

Common local credential artifacts are less likely to be staged accidentally.
Contributors can still check in sanitized environment templates.

Ignore rules do not remove previously tracked files or Git history, prevent
forced additions, detect secrets embedded in source, or restrict filesystem
access. Example files still require review to ensure they contain placeholders.
This decision does not add API authentication or alter AWS IAM permissions.
