---
paths:
  - ".github/workflows/**/*.yml"
  - ".github/workflows/**/*.yaml"
  - ".github/dependabot.yml"
  - ".github/CODEOWNERS"
---

# GitHub Actions Security Hardening

## Permissions

- Set `permissions: {}` at the workflow level to deny all by default.
- Grant only the minimum required permission per job (e.g., `contents: read` for scanning).
- TruffleHog only needs `contents: read`. Never grant write permissions for scan-only workflows.

## SHA pinning (supply chain defense)

- Pin all third-party actions to full 40-character commit SHAs, not mutable tags.
- Add a trailing comment with the version for readability: `@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`
- Mutable tags (`@v2`, `@main`) can be silently redirected to malicious commits (see CVE-2025-30066, tj-actions attack affecting 23,000+ repos).

## Dependabot for action updates

Keep SHA pins current with Dependabot:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

## CODEOWNERS

Require security team review for workflow changes:

```
# .github/CODEOWNERS
.github/workflows/ @org/security-team
```

## Checklist for any workflow in production

- `permissions: {}` at workflow level
- `pull_request` trigger (not `pull_request_target`)
- All `uses:` pinned to full 40-character SHA
- `fetch-depth: 0` on checkout (required for TruffleHog history scanning)
- `persist-credentials: false` on checkout
- CODEOWNERS protecting `.github/workflows/`
- Dependabot configured for weekly action updates
