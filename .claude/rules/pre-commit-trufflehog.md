---
paths:
  - ".pre-commit-config.yaml"
  - ".pre-commit-config.yml"
---

# TruffleHog Pre-commit Hook

## Setup

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/trufflesecurity/trufflehog
    rev: v3.93.4
    hooks:
      - id: trufflehog
```

Install with: `pre-commit install`

## What the hook runs

```bash
trufflehog git file://. --since-commit HEAD --results=verified --fail --trust-local-git-config
```

- Only scans staged changes (not full history)
- Only fails on verified (active) credentials
- Can be bypassed with `git commit --no-verify` — CI is the enforcement layer

## Stricter alternative

To also catch unverifiable secrets:

```yaml
hooks:
  - id: trufflehog
    args: [--results=verified,unknown]
```

## Version pinning

Always pin `rev:` to a specific version tag. Update with `pre-commit autoupdate`.
