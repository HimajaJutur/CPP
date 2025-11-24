import json
import boto3
from boto3.dynamodb.conditions import Key

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Tickets")

def lambda_handler(event, context):
    try:
        username = event["queryStringParameters"]["username"]

        resp = TABLE.query(
            IndexName="TicketsByUser",
            KeyConditionExpression=Key("username").eq(username),
            ScanIndexForward=False
        )

        return {
            "statusCode": 200,
            "body": json.dumps(resp["Items"])
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
