import os
from datetime import datetime, timezone

import boto3
import requests

FIVEM_CFX_ID = os.environ["FIVEM_CFX_ID"]
FIVEM_PLAYER_ID = os.environ["FIVEM_PLAYER_ID"]
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
TABLE_NAME = os.environ["TABLE_NAME"]

FIVEM_API_URL = (
    f"https://servers-frontend.fivem.net/api/servers/single/{FIVEM_CFX_ID}"
)
DISCORD_API_URL = (
    f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
)
WATCH_ID = "default"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    state = _get_state()

    try:
        online, player_name = _check_player_online()
        was_online = state.get("online", False)

        if state.get("consecutiveErrors", 0) > 0:
            state["consecutiveErrors"] = 0

        if online and not was_online:
            _send_discord_message(
                f"\U0001f3ae **{player_name}** just joined the FiveM server!"
            )
        elif not online and was_online:
            last_name = state.get("playerName", "Friend")
            _send_discord_message(
                f"\U0001f44b **{last_name}** left the FiveM server."
            )

        state["online"] = online
        if player_name:
            state["playerName"] = player_name

    except Exception as e:
        consecutive = state.get("consecutiveErrors", 0) + 1
        state["consecutiveErrors"] = consecutive
        print(f"FiveM API error (attempt {consecutive}): {e}")

        if consecutive == 5:
            _send_discord_message(
                f"\u26a0\ufe0f FiveM API has been unreachable for ~5 minutes: `{e}`"
            )

    state["lastChecked"] = datetime.now(timezone.utc).isoformat()
    _put_state(state)

    return {"statusCode": 200}


def _check_player_online():
    resp = requests.get(
        FIVEM_API_URL,
        timeout=10,
        headers={"User-Agent": "discord-fivem-watcher/1.0"},
    )
    resp.raise_for_status()

    data = resp.json().get("Data") or {}
    for player in data.get("players") or []:
        identifiers = player.get("identifiers") or []
        if FIVEM_PLAYER_ID in identifiers:
            return True, player.get("name")

    return False, None


def _send_discord_message(content):
    resp = requests.post(
        DISCORD_API_URL,
        json={"content": content},
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    print(f"Discord message sent: {content}")


def _get_state():
    response = table.get_item(Key={"watchId": WATCH_ID})
    return response.get(
        "Item",
        {"watchId": WATCH_ID, "online": False, "consecutiveErrors": 0},
    )


def _put_state(state):
    state["watchId"] = WATCH_ID
    table.put_item(Item=state)
