import json
import boto3
import uuid
from datetime import datetime

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Alerts")

def lambda_handler(event, context):
    try:
        body = json.loads(event["body"])
        username = body["username"]
        message = body["message"]
        level = body.get("level", "info")

        alert_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        TABLE.put_item(Item={
            "alert_id": alert_id,
            "username": username,
            "message": message,
            "created_at": created_at,
            "level": level
        })

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Alert stored"})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
