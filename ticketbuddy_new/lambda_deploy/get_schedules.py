import json
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Schedules")

def d2f(obj):
    """Convert Decimal → float for JSON serialization"""
    if isinstance(obj, list):
        return [d2f(i) for i in obj]
    if isinstance(obj, dict):
        return {k: d2f(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

def lambda_handler(event, context):
    try:
        # Handle API Gateway body or direct invoke
        if "body" in event and isinstance(event["body"], str):
            body = json.loads(event["body"])
        else:
            body = event

        source = body.get("from") or body.get("source")
        destination = body.get("to") or body.get("destination")

        # MODE 1: Filter by source + destination
        if source and destination:
            resp = TABLE.scan(
                FilterExpression=Attr("source").eq(source) &
                                 Attr("destination").eq(destination)
            )
            items = d2f(resp.get("Items", []))
            return {
                "statusCode": 200,
                "body": json.dumps(items)
            }

        # MODE 2: Return ALL schedules (Destinations page)
        resp = TABLE.scan()
        items = d2f(resp.get("Items", []))
        return {
            "statusCode": 200,
            "body": json.dumps(items)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
