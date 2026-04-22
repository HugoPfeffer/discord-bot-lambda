---
paths:
  - ".github/workflows/**/*.yml"
  - ".github/workflows/**/*.yaml"
---

# TruffleHog Secret Scanning Workflows

When creating or modifying TruffleHog scan workflows:

- `fetch-depth: 0` is mandatory on checkout. Without it, TruffleHog cannot scan git history.
- Use `--results=verified,unknown` as the default `extra_args`. Use `--results=verified` for lowest noise.
- The official action always injects `--fail`, `--no-update`, and `--github-actions`. Do not duplicate them in `extra_args`.
- TruffleHog exits `183` when findings match the `--results` filter. The official action handles this automatically.

## Required workflow structure

```yaml
permissions: {}

jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: trufflesecurity/trufflehog@v3.93.4
        with:
          extra_args: --results=verified,unknown
```

See `github-actions-security.md` for SHA pinning and permissions rationale.

## Triggers

- Use `pull_request` (safe, read-only token). Never use `pull_request_target` — it grants write access and secret access to fork PRs.
- Push scanning: `push: branches: [main]`.
- Full-history audits: `schedule` with `workflow_dispatch` as fallback.

## extra_args reference

| Goal | extra_args |
|------|-----------|
| Only verified (active) credentials | `--results=verified` |
| Verified + unverifiable | `--results=verified,unknown` |
| All results | `--results=verified,unverified,unknown` |
| Custom config | `--config .trufflehog/config.yaml` |
| Skip binary files | `--force-skip-binaries` |
| Limit archive size | `--archive-max-size=5MB` |
