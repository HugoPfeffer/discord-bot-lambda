---
paths:
  - ".github/workflows/**/*.yml"
  - ".github/workflows/**/*.yaml"
  - "workflow-templates/**"
---

# Reusable Workflow Pattern for Org-Wide Scanning

## Central engine workflow

Lives in `org/.github` repository with `on: workflow_call:` trigger. Contains all scanning logic. Individual repos call it with ~8 lines of YAML.

## Thin caller workflow (per repo)

```yaml
name: Secret Scan
on:
  push: {}
  pull_request: {}

jobs:
  scan:
    uses: org/.github/.github/workflows/secret-scan.yml@v1.0.0
    secrets: inherit
```

## Key requirements

- The central repo must enable org-wide access: Settings > Actions > General > "Accessible from repositories in the organization"
- Tag the engine workflow with semantic versions so callers can pin to stable releases
- Callers cannot override security controls (permissions, binary version) — only declared `inputs`
- Use `secrets: inherit` to pass repository secrets to the reusable workflow

## Branch protection

After the workflow runs once, require it as a status check:
- Settings > Branches > Branch protection > Require status checks > Add "TruffleHog Secret Scan"
- The context string must exactly match the job name in the Actions UI
