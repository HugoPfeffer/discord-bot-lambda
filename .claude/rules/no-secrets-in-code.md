---
paths:
  - "**/*.yml"
  - "**/*.yaml"
  - "**/*.env*"
  - "**/*.json"
  - "**/*.toml"
  - "**/*.cfg"
  - "**/*.conf"
  - "**/*.ini"
  - "**/*.py"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.go"
  - "**/*.rs"
  - "**/*.sh"
---

# Secret Handling

- Never hardcode API keys, tokens, passwords, or credentials. Use environment variables or secrets managers (`${{ secrets.NAME }}` in GitHub Actions).
- If a test needs a credential-shaped string, use an obviously fake value and add `# trufflehog:ignore` on the same line.
- Never echo or log secret values.

## If TruffleHog reports a verified finding

1. **Revoke the credential at the provider first** — do NOT delete from code first
2. Assess blast radius via provider's access logs
3. Replace the hardcoded value with a secrets reference
4. Issue a new credential with least-privilege scope
5. Rotation guides: https://howtorotate.com
