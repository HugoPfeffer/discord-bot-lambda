# Discord Bot on AWS Lambda

A serverless Discord bot running on AWS Lambda, built with Flask and deployed via AWS CDK. The bot currently provides two features:

- **CS2 Map Rotation Tracker** — Tracks which Active Duty maps a friend group has played each cycle, with a visual dashboard and slash commands.
- **Training Tracker** — Per-guild leaderboard for the squad's daily 200-frag deathmatch routine. Members `/pago` to mark today done, `/placar` to see the ranking.

Both features share a single Docker image deployed to Lambda, with separate DynamoDB tables.

## Architecture

```
Discord ──> Lambda Function URL ──> main.handler (Flask)
                                        ├── /dashboard, /played, ... (CS2)
                                        ├── /pago, /placar, /meu-pago, ... (Training)
                                        └── DynamoDB (cs2-map-tracker, pago-leaderboard)
```

**Stack:** Python 3.11, Flask, Docker on Lambda, DynamoDB, CDK (TypeScript), Discord Interactions Endpoint.

## CS2 Map Rotation

The dashboard uses Discord Components V2 with a Container, Media Gallery for map thumbnails, and toggle buttons:

| Command | Description |
|---------|-------------|
| `/dashboard` | Post the map rotation dashboard in the current channel |
| `/played <map>` | Mark a map as played |
| `/remaining` | Show maps not yet played this cycle (ephemeral) |
| `/history` | Show maps played this cycle in order (ephemeral) |
| `/undo` | Unmark the most recently played map |
| `/unmark <map>` | Unmark a specific map |
| `/reset` | Reset the current cycle (with confirmation) |

Maps: Ancient, Anubis, Dust II, Inferno, Mirage, Nuke, Overpass.

When all 7 maps have been played, the cycle auto-resets with a celebration message and the cycle counter increments.

## Training Tracker

Per-guild leaderboard for the daily 200-frag deathmatch routine. Trust-based — no anti-abuse.

| Command | Description |
|---------|-------------|
| `/pago` | Mark today's training done. Multiple calls per day allowed; only the first counts toward your "training days". Shows a 🔥 streak suffix when you've gone 2+ consecutive UTC days. Public. |
| `/despago` | Same-day undo for misclicks. Decrements your session count; if you'd marked today as a new day, also rolls back days_count and streak (lossily). Public. |
| `/placar` | Top-10 leaderboard for this guild. Sorted by training days (DESC), tiebreak by total sessions (DESC). Public. |
| `/meu-pago` | Your row + your rank. Useful when you're outside the top 10. Ephemeral. |
| `/pago-remove <user>` | **Admin-only** (Discord ADMINISTRATOR permission). Removes a user's row entirely — used to clean up ex-members. Ephemeral. |

**Notes:**
- Day boundary is UTC. A user training at 23:30 and 00:30 UTC counts as two distinct days.
- Streaks are display-only and do NOT affect `/placar` ranking — they extend on consecutive UTC days, reset on a gap.
- All five commands are guild-only (`dm_permission: false`); invoking from a DM is blocked by Discord.
- Storage: DynamoDB table `pago-leaderboard` with composite key `guild_id` + `user_id`. The `PAGO_TABLE_NAME` env var is wired automatically by CDK — no `.env` entry needed.
- Conflict-retry observability: a CloudWatch metric filter (`DiscordBot/Pago` namespace) counts every optimistic-lock conflict the Lambda logs.

## Setup

### Prerequisites

- Node.js and npm
- Python 3.11+
- Docker
- AWS CLI configured with credentials
- A Discord application with a bot token

### Environment Variables

Copy `lambda-bot/.env.example` to `lambda-bot/.env` and fill in real values (the CDK stack loads `.env` from `lambda-bot/` via `dotenv`):

```sh
# Discord (required)
DISCORD_PUBLIC_KEY=your_discord_public_key
DISCORD_TOKEN=your_bot_token
DISCORD_APPLICATION_ID=your_app_id

# Discord (optional / future use)
DISCORD_CHANNEL_ID=your_channel_id

# Optional: guild-scoped command registration (instant updates during dev)
DISCORD_GUILD_ID=your_guild_id
```

### Register Commands

Install the registration script dependencies and run it:

```sh
pip install -r commands/requirements.txt
cd commands
python register_commands.py
```

If `DISCORD_GUILD_ID` is set, commands register to that guild (instant). Otherwise they register globally (up to 1 hour propagation).

Commands are defined in `commands/discord_commands.yaml`. The script uses a bulk `PUT` so stale commands are automatically removed.

### Deploy

Bootstrap CDK if this is your first deploy to the account/region:

```sh
npx cdk bootstrap
```

Deploy the stack:

```sh
BUILDX_NO_DEFAULT_ATTESTATIONS=1 npx cdk deploy
```

The `BUILDX_NO_DEFAULT_ATTESTATIONS=1` flag ensures Docker builds a Lambda-compatible image manifest.

After deploying, copy the `FunctionUrl` output and set it as the **Interactions Endpoint URL** in your [Discord Developer Portal](https://discord.com/developers/applications).

## Map Pool Configuration

The Active Duty map pool is defined in `src/config/maps.yaml`:

```yaml
active_duty:
  - slug: ancient
    name: Ancient
    thumb_url: https://...
```

To update the pool (e.g., when Valve rotates maps):

1. Edit `src/config/maps.yaml` (add/remove entries)
2. Update the choices in `commands/discord_commands.yaml` to match
3. Run `python commands/register_commands.py` to sync commands with Discord
4. Run `npx cdk deploy` to redeploy the Lambda

## Tests

Unit tests for `pago.py` use [moto](https://github.com/getmoto/moto) for an in-memory DynamoDB. They live under `tests/` so the Lambda image (`docker build src/`) stays lean — moto and pytest are NOT in the runtime image.

```sh
pip install -r tests/requirements.txt
pytest tests/ -v
```

Two tests:
- `test_pago_concurrency.py` — 20 threads racing on the same `(guild_id, user_id)` to prove the optimistic-lock retry path merges concurrent writes correctly.
- `test_pago_streak.py` — monkeypatches `_today_utc`/`_yesterday_utc` to walk multiple UTC days, asserting streak extension, same-day no-op, gap reset, and lossy `/despago` rollback.

## Project Structure

```
├── bin/                        # CDK app entry point
├── lib/
│   └── discord-bot-lambda-stack.ts   # AWS infrastructure (Lambda, DynamoDB, MetricFilter)
├── commands/
│   ├── discord_commands.yaml         # Slash command definitions
│   └── register_commands.py          # Command registration script
├── src/
│   ├── Dockerfile                    # Lambda container image
│   ├── requirements.txt              # Python dependencies
│   ├── config/
│   │   └── maps.yaml                 # CS2 map pool + thumbnail URLs
│   └── app/
│       ├── main.py                   # Discord interaction handler (Flask)
│       ├── dashboard.py              # Components V2 dashboard builder
│       ├── db.py                     # DynamoDB state for CS2 tracker
│       ├── pago.py                   # DynamoDB state for training tracker
│       └── config.py                 # Map pool config loader
├── tests/                            # pytest + moto unit tests for pago.py
└── .env                              # Secrets (not committed)
```
