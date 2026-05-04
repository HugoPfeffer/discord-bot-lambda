import os
os.environ["PAGO_TABLE_NAME"] = "pago-leaderboard-test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
from moto import mock_aws


def _create_table():
    ddb = boto3.resource("dynamodb")
    ddb.create_table(
        TableName="pago-leaderboard-test",
        KeySchema=[
            {"AttributeName": "guild_id", "KeyType": "HASH"},
            {"AttributeName": "user_id",  "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "guild_id", "AttributeType": "S"},
            {"AttributeName": "user_id",  "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@mock_aws
def test_streak_progression_and_break(monkeypatch):
    _create_table()
    import sys
    sys.path.insert(0, "src/app")
    import importlib
    import pago
    importlib.reload(pago)

    # Day 1
    monkeypatch.setattr(pago, "_today_utc",     lambda: "2026-01-01")
    monkeypatch.setattr(pago, "_yesterday_utc", lambda: "2025-12-31")
    r = pago.record_pago("g", "u", "alice")
    assert int(r["streak"]) == 1 and int(r["days_count"]) == 1

    # Day 2 — consecutive, streak extends
    monkeypatch.setattr(pago, "_today_utc",     lambda: "2026-01-02")
    monkeypatch.setattr(pago, "_yesterday_utc", lambda: "2026-01-01")
    r = pago.record_pago("g", "u", "alice")
    assert int(r["streak"]) == 2 and int(r["days_count"]) == 2

    # Day 2 again — same-day session, streak unchanged
    r = pago.record_pago("g", "u", "alice")
    assert int(r["streak"]) == 2 and int(r["today_sessions"]) == 2

    # Day 5 — gap, streak resets to 1
    monkeypatch.setattr(pago, "_today_utc",     lambda: "2026-01-05")
    monkeypatch.setattr(pago, "_yesterday_utc", lambda: "2026-01-04")
    r = pago.record_pago("g", "u", "alice")
    assert int(r["streak"]) == 1 and int(r["days_count"]) == 3

    # Despago empties day 5 — streak rolls back lossily to 0
    r = pago.undo_pago("g", "u")
    assert int(r["today_sessions"]) == 0
    assert int(r["streak"]) == 0
    assert int(r["days_count"]) == 2
