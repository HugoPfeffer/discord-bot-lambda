import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from config import MAP_SLUGS

_TABLE_NAME = os.environ.get("MAP_TRACKER_TABLE_NAME", "cs2-map-tracker")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)

_MAX_RETRIES = 2


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


def _build_condition(previous_updated_at):
    if previous_updated_at:
        return Attr("updated_at").eq(previous_updated_at)
    return Attr("updated_at").not_exists() | Attr("guild_id").not_exists()


def _conditional_put(item: dict, previous_updated_at):
    """Single-attempt conditional write. Raises on conflict."""
    item["updated_at"] = _now_iso()
    condition = _build_condition(previous_updated_at)
    _table.put_item(Item=item, ConditionExpression=condition)
    return item


def _prepare_item(state: dict) -> dict:
    """Convert state dict to a DynamoDB-safe item (no empty sets)."""
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


def _is_conflict(e: ClientError) -> bool:
    return e.response["Error"]["Code"] == "ConditionalCheckFailedException"


def mark_played(guild_id: str, slug: str) -> dict:
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        if slug in state["played"]:
            return state

        prev = state["updated_at"]
        state["played"].add(slug)
        state["played_order"].append(slug)

        try:
            item = _prepare_item(state)
            _conditional_put(item, prev)
            state["updated_at"] = item["updated_at"]
            return state
        except ClientError as e:
            if not _is_conflict(e):
                raise

    state = get_state(guild_id)
    if slug in state["played"]:
        return state
    raise RuntimeError(f"Failed to mark {slug} after {_MAX_RETRIES} retries")


def unmark_map(guild_id: str, slug: str) -> dict:
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        if slug not in state["played"]:
            return state

        prev = state["updated_at"]
        state["played"].discard(slug)
        state["played_order"] = [s for s in state["played_order"] if s != slug]

        try:
            _conditional_put(_prepare_item(state), prev)
            return state
        except ClientError as e:
            if not _is_conflict(e):
                raise

    state = get_state(guild_id)
    if slug not in state["played"]:
        return state
    raise RuntimeError(f"Failed to unmark {slug} after {_MAX_RETRIES} retries")


def undo_last(guild_id: str) -> tuple[dict, str | None]:
    """Undo the most recently played map. Returns (state, undone_slug)."""
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        if not state["played_order"]:
            return state, None

        prev = state["updated_at"]
        slug = state["played_order"].pop()
        state["played"].discard(slug)

        try:
            _conditional_put(_prepare_item(state), prev)
            return state, slug
        except ClientError as e:
            if not _is_conflict(e):
                raise

    return get_state(guild_id), None


def reset_cycle(guild_id: str) -> dict:
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        prev = state["updated_at"]

        state["played"] = set()
        state["played_order"] = []
        state["cycle_number"] += 1

        try:
            _conditional_put(_prepare_item(state), prev)
            return state
        except ClientError as e:
            if not _is_conflict(e):
                raise

    raise RuntimeError(f"Failed to reset cycle after {_MAX_RETRIES} retries")


def save_dashboard_ref(guild_id: str, channel_id: str, message_id: str) -> dict:
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        prev = state["updated_at"]

        state["dashboard_message_id"] = message_id
        state["dashboard_channel_id"] = channel_id

        try:
            _conditional_put(_prepare_item(state), prev)
            return state
        except ClientError as e:
            if not _is_conflict(e):
                raise

    raise RuntimeError(f"Failed to save dashboard ref after {_MAX_RETRIES} retries")


def toggle_map(guild_id: str, slug: str) -> tuple[dict, bool]:
    """Toggle a map's played status. Returns (state, cycle_completed).

    If this toggle marks the last remaining map, the cycle auto-resets.
    """
    for _ in range(_MAX_RETRIES):
        state = get_state(guild_id)
        prev = state["updated_at"]

        if slug in state["played"]:
            state["played"].discard(slug)
            state["played_order"] = [s for s in state["played_order"] if s != slug]
            try:
                _conditional_put(_prepare_item(state), prev)
                return state, False
            except ClientError as e:
                if not _is_conflict(e):
                    raise
                continue

        state["played"].add(slug)
        state["played_order"].append(slug)

        cycle_completed = len(state["played"]) >= len(MAP_SLUGS)
        if cycle_completed:
            completed_cycle = state["cycle_number"]
            state["played"] = set()
            state["played_order"] = []
            state["cycle_number"] += 1
            state["_completed_cycle"] = completed_cycle

        try:
            _conditional_put(_prepare_item(state), prev)
            return state, cycle_completed
        except ClientError as e:
            if not _is_conflict(e):
                raise

    return get_state(guild_id), False
