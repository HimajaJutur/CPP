# lambda_deploy/get_history.py
import boto3
import json
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamo = boto3.resource("dynamodb")
TICKETS = dynamo.Table("TicketBuddy_Tickets")

def dec_to_native(obj):
    if isinstance(obj, list):
        return [dec_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: dec_to_native(v) for k,v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

def lambda_handler(event, context):
    username = event.get("username") or (event.get("body") and json.loads(event.get("body")).get("username"))
    if not username:
        return {"status":"error","message":"Missing username"}

    try:
        resp = TICKETS.query(
            IndexName="username-index",
            KeyConditionExpression=Key("username").eq(username),
            ScanIndexForward=False
        )
        items = resp.get("Items", [])
        items = [dec_to_native(it) for it in items]
        return {"status":"success","bookings": items}
    except Exception as e:
        return {"status":"error","message": str(e)}
