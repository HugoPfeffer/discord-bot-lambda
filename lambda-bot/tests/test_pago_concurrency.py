import os
import threading
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
def test_concurrent_pagos_same_user():
    _create_table()
    import sys
    sys.path.insert(0, "src/app")
    import importlib
    import pago
    importlib.reload(pago)

    errors: list[BaseException] = []

    def _hit():
        try:
            pago.record_pago("g1", "u1", "alice")
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=_hit) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"threads raised: {errors!r}"

    table = boto3.resource("dynamodb").Table("pago-leaderboard-test")
    item = table.get_item(Key={"guild_id": "g1", "user_id": "u1"})["Item"]
    assert int(item["total_pagos"]) == 20
    assert int(item["days_count"]) == 1
    assert int(item["today_sessions"]) == 20
