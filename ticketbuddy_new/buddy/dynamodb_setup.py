#!/usr/bin/env python3
"""
dynamodb_setup.py

Creates three DynamoDB tables for TicketBuddy:
 - Users
 - Tickets (with GSI TicketsByUser)
 - Alerts  (with GSI AlertsByUser)

Idempotent: will not recreate tables that already exist.

Run:
    source venv/bin/activate
    python3 buddy/dynamodb_setup.py
"""

import time
import boto3
from botocore.exceptions import ClientError

AWS_REGION = "us-east-1"
dynamo = boto3.client("dynamodb", region_name=AWS_REGION)


def table_exists(table_name: str) -> bool:
    try:
        dynamo.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def wait_for_table_active(table_name: str):
    print(f"Waiting for {table_name} to become ACTIVE...", end="")
    while True:
        resp = dynamo.describe_table(TableName=table_name)
        if resp["Table"]["TableStatus"] == "ACTIVE":
            print(" done.")
            break
        time.sleep(2)


def create_users_table():
    name = "TicketBuddy_Users"
    if table_exists(name):
        print(f"{name} already exists — skipping")
        return
    print(f"Creating {name} ...")
    dynamo.create_table(
        TableName=name,
        AttributeDefinitions=[
            {"AttributeName": "username", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "username", "KeyType": "HASH"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_for_table_active(name)


def create_tickets_table():
    name = "TicketBuddy_Tickets"
    if table_exists(name):
        print(f"{name} already exists — skipping")
        return
    print(f"Creating {name} ...")
    dynamo.create_table(
        TableName=name,
        AttributeDefinitions=[
            {"AttributeName": "booking_id", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "booking_id", "KeyType": "HASH"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "TicketsByUser",
                "KeySchema": [
                    {"AttributeName": "username", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_for_table_active(name)


def create_alerts_table():
    name = "TicketBuddy_Alerts"
    if table_exists(name):
        print(f"{name} already exists — skipping")
        return
    print(f"Creating {name} ...")
    dynamo.create_table(
        TableName=name,
        AttributeDefinitions=[
            {"AttributeName": "alert_id", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "alert_id", "KeyType": "HASH"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "AlertsByUser",
                "KeySchema": [
                    {"AttributeName": "username", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    wait_for_table_active(name)


def main():
    print("Starting DynamoDB setup...")
    create_users_table()
    create_tickets_table()
    create_alerts_table()
    print("All DynamoDB tables ready.")


if __name__ == "__main__":
    main()
