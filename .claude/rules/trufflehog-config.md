---
paths:
  - ".trufflehog/**"
---

# TruffleHog Configuration

## config.yaml structure

Place config at `.trufflehog/config.yaml`. Key sections:

- `detectors` — custom regex detector definitions with keywords, regex, entropy, and exclusions
- `exclude_detectors` — comma-separated built-in detector names to disable
- `include_detectors` — comma-separated built-in detector names to enable (disables all others)

## Custom detector fields

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | Yes | Display name in output |
| `keywords` | Yes | Aho-Corasick pre-filter strings (must appear in content for regex to run) |
| `regex` | Yes | Named capture groups (`token: 'pattern'`) |
| `entropy` | No | Minimum Shannon entropy (3.0-4.0 typical), filters placeholders |
| `exclude_words` | No | Exact strings to suppress (e.g., `example`, `placeholder`) |
| `exclude_regexes_capture` | No | Regex on captured value to suppress |
| `exclude_regexes_match` | No | Regex on full match context to suppress |

## exclude-paths.txt

Place at `.trufflehog/exclude-paths.txt`. One regex per line. Lines starting with `#` are comments.

Standard exclusions:

```
^\.git/
^vendor/
^node_modules/
^test/fixtures/
.*\.lock$
```

Use both files together:

```bash
trufflehog git file://. \
  --config .trufflehog/config.yaml \
  --exclude-paths .trufflehog/exclude-paths.txt \
  --results=verified --fail
```

## False positive suppression (ordered by precision)

1. `trufflehog:ignore` — inline comment on the exact line
2. `--exclude-paths` — exclude entire directories/file patterns
3. `--results=verified` — only report confirmed-active credentials
4. `--exclude-detectors` — disable specific noisy built-in detectors
5. `--force-skip-binaries` — skip binary files producing false matches
