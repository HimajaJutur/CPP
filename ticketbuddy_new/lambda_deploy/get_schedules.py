import json
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Schedules")

def d2f(obj):
    if isinstance(obj, list):
        return [d2f(i) for i in obj]
    if isinstance(obj, dict):
        return {k: d2f(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

def lambda_handler(event, context):
    try:
        source = event.get("from") or event.get("source")
        destination = event.get("to") or event.get("destination")

        if not source or not destination:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing source or destination"})
            }

        resp = TABLE.scan(
            FilterExpression=Attr("source").eq(source) & Attr("destination").eq(destination)
        )

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
