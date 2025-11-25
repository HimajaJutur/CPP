import boto3
import json
from boto3.dynamodb.conditions import Key

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Seats")

def lambda_handler(event, context):
    route_id = event.get("route_id")

    resp = TABLE.query(
        KeyConditionExpression=Key("route_id").eq(route_id)
    )

    return {
        "seats": resp["Items"]
    }
