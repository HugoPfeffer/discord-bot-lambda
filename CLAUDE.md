# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo layout

The repo has two roots:

- `lambda-bot/` — the actual application (Python Lambda + TypeScript CDK).
- Everything else at `/` — dev/security tooling scaffolding: pre-commit, TruffleHog config, GitHub Actions workflows, OpenSpec spec-driven workflow (`openspec/`), rule docs under `.claude/rules/`, and devcontainer. `README.md` documents the bot itself, not the outer scaffolding.

All `npm`/`cdk`/`python` commands below must be run from `lambda-bot/` unless noted.

## Commands

```sh
# CDK (from lambda-bot/)
npm install                          # install CDK deps
npm run build                        # tsc
npm test                             # jest (currently a placeholder test)
BUILDX_NO_DEFAULT_ATTESTATIONS=1 npx cdk deploy   # deploy; flag is required for Lambda-compatible manifest
npx cdk bootstrap                    # first-time only per account/region
npx cdk synth                        # will FAIL without required .env vars — synth is not a dry run
npm test -- -t "SQS"                 # run a single jest test by name

# Discord command registration (separate from deploy; from lambda-bot/commands/)
pip install -r requirements.txt
python register_commands.py          # bulk PUT; set DISCORD_GUILD_ID for instant guild-scoped updates

# Secret scanning (from repo root)
pre-commit install                   # installs the TruffleHog pre-commit hook
pre-commit run --all-files           # full repo scan
```

Env vars required for `cdk synth`/`deploy`: `DISCORD_PUBLIC_KEY`, `DISCORD_TOKEN`, `FIVEM_CFX_ID`, `FIVEM_PLAYER_ID`, `DISCORD_CHANNEL_ID`. The stack throws synchronously in its constructor if any are missing, so `.env` (loaded by `dotenv` in `lib/discord-bot-lambda-stack.ts`) must be populated before any CDK command.

## Architecture

**Two Lambda handlers, one Docker image.** The Dockerfile at `lambda-bot/src/Dockerfile` is built once; the CDK stack creates two `DockerImageFunction`s from it with different `cmd` overrides:
- `main.handler` — Flask app behind a public Function URL, invoked by Discord's Interactions Endpoint.
- `watcher.handler` — invoked by an EventBridge rule every 1 minute.

**Two DynamoDB tables, different policies by intent.**
- `MapTrackerTable` (guild_id PK) — `PAY_PER_REQUEST`, `RemovalPolicy.RETAIN`. State is user-owned, so stack teardown must not destroy it.
- `WatcherStateTable` (watchId PK) — `PROVISIONED` 1/1, `RemovalPolicy.DESTROY`. Transient state; cheapest provisioning is appropriate because traffic is a fixed 1/min.

**Function URL quirk (Oct 2025).** `lib/discord-bot-lambda-stack.ts` adds an explicit `lambda:InvokeFunction` permission alongside the CDK-managed `lambda:InvokeFunctionUrl`. Both are now required for public Function URLs; do not remove.

**Optimistic concurrency in `src/app/db.py`.** Every mutation reads state, attempts a conditional `put_item` guarded on `updated_at`, and retries twice on `ConditionalCheckFailedException`. Preserve this pattern — Discord interactions can arrive in parallel from different users, and blind overwrites will lose played-map marks. Use `toggle_map` for idempotent component-button flows (handles auto-reset on cycle completion); use `mark_played`/`unmark_map`/`undo_last` for slash commands.

**Discord Components V2.** `src/app/dashboard.py` builds component type 17 (Container) with type 12 (Media Gallery) thumbnails. The flag `IS_COMPONENTS_V2 = 1 << 15` is required on any response whose `data.components` uses V2 types. `response_type` 4 = new message, 7 = in-place update; see `dashboard_response()`.

**Command registration is decoupled from deploy.** `commands/register_commands.py` PUTs the entire command set to Discord's API — it does not run during `cdk deploy`. After editing `commands/discord_commands.yaml`, you must run the script separately. Guild-scoped registration (when `DISCORD_GUILD_ID` is set) propagates instantly; global registration takes up to 1 hour.

**Two files define the map pool and they must stay in sync.**
- `src/config/maps.yaml` — consumed by the Lambda at runtime (slugs, names, thumbnails).
- `commands/discord_commands.yaml` — consumed by `register_commands.py` (slash-command choice lists for `/played` and `/unmark`).

Rotating the Active Duty pool requires editing both, then running `register_commands.py` AND `cdk deploy`.

## Security and CI conventions

Workflow and config files under `.github/workflows/`, `.trufflehog/`, and `.github/dependabot.yml` are governed by the rules in `.claude/rules/*.md` (auto-loaded by path scope). Key non-obvious invariants:

- All third-party Actions pinned to full 40-char SHAs with trailing version comment. Dependabot keeps them current.
- TruffleHog workflow uses `permissions: {}` at the workflow level, `contents: read` per job, `fetch-depth: 0` (required for history scanning), and `persist-credentials: false`.
- TruffleHog CI uses `--results=verified,unknown`; the pre-commit hook uses `--results=verified` (just staged diff). Both paths read `.trufflehog/config.yaml`.
- False-positive suppression order: inline `trufflehog:ignore` comment first, then exclude-paths, never widen by disabling detectors.
- On a verified finding: revoke at provider first, then replace in code. Do not delete from code first — that breaks forensics.

## OpenSpec workflow

`openspec/config.yaml` configures a spec-driven pipeline (proposal → research → specs → design → tasks → apply) in `deep` mode with strict gates on proposal/specs/tasks. Every requirement gets a `REQ-<CAP>-<seq>` ID, scenarios use GIVEN/WHEN/THEN, and tasks must trace to requirements. If the user asks to work in this pipeline, follow the per-phase rules in `openspec/config.yaml` rather than ad-hoc structure.

## Notes

- `.claude/plans/` is gitignored — plans live there but are local-only.
- `test/discord-bot-lambda.test.ts` is a commented-out placeholder; there is no real test suite yet.
