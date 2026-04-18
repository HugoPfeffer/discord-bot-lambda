import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from config import MAP_SLUGS

_TABLE_NAME = os.environ.get("MAP_TRACKER_TABLE_NAME", "cs2-map-tracker")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)

def _default_state():
    return {
        "played": set(),
        "played_order": [],
        "cycle_number": 1,
        "dashboard_message_id": None,
        "dashboard_channel_id": None,
        "updated_at": None,
    }


def get_state(guild_id: str) -> dict:
    resp = _table.get_item(Key={"guild_id": guild_id})
    item = resp.get("Item")
    if not item:
        return {"guild_id": guild_id, **_default_state()}

    played_raw = item.get("played") or set()
    if isinstance(played_raw, list):
        played_raw = set(played_raw)

    valid_played = played_raw & set(MAP_SLUGS)
    valid_order = [s for s in (item.get("played_order") or []) if s in valid_played]

    return {
        "guild_id": guild_id,
        "played": valid_played,
        "played_order": valid_order,
        "cycle_number": int(item.get("cycle_number", 1)),
        "dashboard_message_id": item.get("dashboard_message_id"),
        "dashboard_channel_id": item.get("dashboard_channel_id"),
        "updated_at": item.get("updated_at"),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conditional_put(item: dict, previous_updated_at):
    """Put with optimistic concurrency on updated_at. Retries once."""
    item["updated_at"] = _now_iso()

    condition = (
        Attr("updated_at").eq(previous_updated_at)
        if previous_updated_at
        else Attr("guild_id").not_exists()
    )

    for attempt in range(2):
        try:
            _table.put_item(Item=item, ConditionExpression=condition)
            return item
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            if attempt == 0:
                fresh = get_state(item["guild_id"])
                item["updated_at"] = _now_iso()
                condition = (
                    Attr("updated_at").eq(fresh["updated_at"])
                    if fresh["updated_at"]
                    else Attr("guild_id").not_exists()
                )
            else:
                raise


def _prepare_item(state: dict) -> dict:
    """Convert state dict to a DynamoDB-safe item."""
    item = {
        "guild_id": state["guild_id"],
        "played": state["played"] if state["played"] else None,
        "played_order": state["played_order"],
        "cycle_number": state["cycle_number"],
        "updated_at": state.get("updated_at"),
    }
    if state.get("dashboard_message_id"):
        item["dashboard_message_id"] = state["dashboard_message_id"]
    if state.get("dashboard_channel_id"):
        item["dashboard_channel_id"] = state["dashboard_channel_id"]
    if item["played"] is None:
        del item["played"]
    return item


def mark_played(guild_id: str, slug: str) -> dict:
    state = get_state(guild_id)
    prev_updated = state["updated_at"]

    if slug in state["played"]:
        return state

    state["played"].add(slug)
    state["played_order"].append(slug)

    item = _prepare_item(state)
    _conditional_put(item, prev_updated)

    state["updated_at"] = item["updated_at"]
    return state


def unmark_map(guild_id: str, slug: str) -> dict:
    state = get_state(guild_id)
    prev_updated = state["updated_at"]

    if slug not in state["played"]:
        return state

    state["played"].discard(slug)
    state["played_order"] = [s for s in state["played_order"] if s != slug]

    item = _prepare_item(state)
    _conditional_put(item, prev_updated)

    state["updated_at"] = item["updated_at"]
    return state


def undo_last(guild_id: str) -> tuple[dict, str | None]:
    """Undo the most recently played map. Returns (state, undone_slug)."""
    state = get_state(guild_id)
    prev_updated = state["updated_at"]

    if not state["played_order"]:
        return state, None

    slug = state["played_order"].pop()
    state["played"].discard(slug)

    item = _prepare_item(state)
    _conditional_put(item, prev_updated)

    state["updated_at"] = item["updated_at"]
    return state, slug


def reset_cycle(guild_id: str) -> dict:
    state = get_state(guild_id)
    prev_updated = state["updated_at"]

    state["played"] = set()
    state["played_order"] = []
    state["cycle_number"] += 1

    item = _prepare_item(state)
    _conditional_put(item, prev_updated)

    state["updated_at"] = item["updated_at"]
    return state


def save_dashboard_ref(guild_id: str, channel_id: str, message_id: str) -> dict:
    state = get_state(guild_id)
    prev_updated = state["updated_at"]

    state["dashboard_message_id"] = message_id
    state["dashboard_channel_id"] = channel_id

    item = _prepare_item(state)
    _conditional_put(item, prev_updated)

    state["updated_at"] = item["updated_at"]
    return state


def toggle_map(guild_id: str, slug: str) -> tuple[dict, bool]:
    """Toggle a map's played status. Returns (state, cycle_completed).

    If this toggle marks the last remaining map, the cycle auto-resets.
    """
    state = get_state(guild_id)

    if slug in state["played"]:
        return unmark_map(guild_id, slug), False

    state_after = mark_played(guild_id, slug)

    if len(state_after["played"]) >= len(MAP_SLUGS):
        cycle_num = state_after["cycle_number"]
        state_after = reset_cycle(guild_id)
        state_after["_completed_cycle"] = cycle_num
        return state_after, True

    return state_after, False
