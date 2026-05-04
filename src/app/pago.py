import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

_TABLE_NAME = os.environ.get("PAGO_TABLE_NAME", "pago-leaderboard")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)

_MAX_RETRIES = 3   # higher than db.py's 2; same-user spam is realistic

logger = logging.getLogger("pago")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday_utc() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_condition(prev_updated_at):
    if prev_updated_at:
        return Attr("updated_at").eq(prev_updated_at)
    return Attr("updated_at").not_exists() | Attr("user_id").not_exists()


def _is_conflict(e: ClientError) -> bool:
    return e.response["Error"]["Code"] == "ConditionalCheckFailedException"


def _get_item(guild_id: str, user_id: str) -> dict | None:
    return _table.get_item(Key={"guild_id": guild_id, "user_id": user_id}).get("Item")


def _log_conflict(op: str, guild_id: str, user_id: str, attempt: int) -> None:
    logger.warning(json.dumps({
        "event": "ConditionalCheckFailedException",
        "op": op,
        "guild_id": guild_id,
        "user_id": user_id,
        "attempt": attempt,
    }))


def record_pago(guild_id: str, user_id: str, username: str) -> dict:
    for attempt in range(_MAX_RETRIES):
        prev = _get_item(guild_id, user_id)
        today = _today_utc()
        is_new_day = prev is None or prev.get("last_pago_date") != today

        if is_new_day:
            if prev is not None and prev.get("last_pago_date") == _yesterday_utc():
                new_streak = int(prev.get("streak", 0)) + 1
            else:
                new_streak = 1
            new_today_sessions = 1
        else:
            new_streak = int(prev.get("streak", 1))
            new_today_sessions = int(prev.get("today_sessions", 0)) + 1

        new_days  = int((prev or {}).get("days_count", 0))  + (1 if is_new_day else 0)
        new_total = int((prev or {}).get("total_pagos", 0)) + 1

        item = {
            "guild_id":       guild_id,
            "user_id":        user_id,
            "username":       username,
            "days_count":     new_days,
            "total_pagos":    new_total,
            "today_sessions": new_today_sessions,
            "last_pago_date": today,
            "streak":         new_streak,
            "updated_at":     _now_iso(),
        }

        try:
            _table.put_item(
                Item=item,
                ConditionExpression=_build_condition(prev["updated_at"] if prev else None),
            )
            item["is_new_day"] = is_new_day
            return item
        except ClientError as e:
            if not _is_conflict(e):
                raise
            _log_conflict("record_pago", guild_id, user_id, attempt + 1)

    raise RuntimeError(f"record_pago failed for {guild_id}/{user_id} after {_MAX_RETRIES} retries")


def undo_pago(guild_id: str, user_id: str) -> dict | None:
    for attempt in range(_MAX_RETRIES):
        prev = _get_item(guild_id, user_id)
        if (
            prev is None
            or prev.get("last_pago_date") != _today_utc()
            or int(prev.get("today_sessions", 0)) <= 0
        ):
            return None

        new_today = int(prev["today_sessions"]) - 1
        new_total = int(prev["total_pagos"]) - 1

        if new_today == 0:
            new_days       = max(0, int(prev["days_count"]) - 1)
            # Streak rollback is intentionally lossy: we cannot reconstruct the prior
            # streak without storing history. See plan Gotchas section.
            new_streak     = max(0, int(prev.get("streak", 0)) - 1)
            last_pago_date = None
        else:
            new_days       = int(prev["days_count"])
            new_streak     = int(prev["streak"])
            last_pago_date = prev["last_pago_date"]

        item = {
            "guild_id":       guild_id,
            "user_id":        user_id,
            "username":       prev.get("username", ""),
            "days_count":     new_days,
            "total_pagos":    new_total,
            "today_sessions": new_today,
            "streak":         new_streak,
            "updated_at":     _now_iso(),
        }
        if last_pago_date is not None:
            item["last_pago_date"] = last_pago_date

        try:
            _table.put_item(
                Item=item,
                ConditionExpression=_build_condition(prev["updated_at"]),
            )
            return item
        except ClientError as e:
            if not _is_conflict(e):
                raise
            _log_conflict("undo_pago", guild_id, user_id, attempt + 1)

    raise RuntimeError(f"undo_pago failed for {guild_id}/{user_id} after {_MAX_RETRIES} retries")


def remove_user(guild_id: str, user_id: str) -> bool:
    resp = _table.delete_item(
        Key={"guild_id": guild_id, "user_id": user_id},
        ReturnValues="ALL_OLD",
    )
    return "Attributes" in resp


def get_leaderboard(guild_id: str, limit: int = 10) -> list[dict]:
    items: list[dict] = []
    last_key = None
    while True:
        kwargs = {"KeyConditionExpression": Key("guild_id").eq(guild_id)}
        if last_key is not None:
            kwargs["ExclusiveStartKey"] = last_key
        resp = _table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if last_key is None:
            break

    items.sort(key=lambda r: (-int(r.get("days_count", 0)), -int(r.get("total_pagos", 0))))

    out = []
    for r in items[:limit]:
        out.append({
            "guild_id":       r["guild_id"],
            "user_id":        r["user_id"],
            "username":       r.get("username", ""),
            "days_count":     int(r.get("days_count", 0)),
            "total_pagos":    int(r.get("total_pagos", 0)),
            "today_sessions": int(r.get("today_sessions", 0)),
            "streak":         int(r.get("streak", 0)),
            "last_pago_date": r.get("last_pago_date"),
        })
    return out


def get_user_rank(guild_id: str, user_id: str) -> tuple[dict | None, int | None]:
    # Fetches all rows to compute rank — acceptable at Discord-guild scale (<100 trainers).
    rows = get_leaderboard(guild_id, limit=10**9)
    for i, r in enumerate(rows):
        if r["user_id"] == user_id:
            return r, i + 1
    return None, None
