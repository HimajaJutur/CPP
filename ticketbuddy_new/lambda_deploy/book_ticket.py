import json
import boto3
import uuid
from datetime import datetime

dynamo = boto3.resource("dynamodb")
TABLE = dynamo.Table("TicketBuddy_Tickets")

def lambda_handler(event, context):
    try:
        # If event is raw dict from Django, no need for ["body"]
        body = event

        username = body["username"]
        source = body["from"]
        destination = body["to"]
        ticket_type = body["ticket_type"]
        passengers = int(body["passengers"])
        departure_date = body["departure_date"]
        return_date = body.get("return_date", None)

        booking_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        item = {
            "booking_id": booking_id,
            "username": username,
            "source": source,
            "destination": destination,
            "ticket_type": ticket_type,
            "passengers": passengers,
            "departure_date": departure_date,
            "return_date": return_date,
            "status": "CONFIRMED",
            "created_at": created_at
        }

        TABLE.put_item(Item=item)

        return {
            "status": "success",
            "booking_id": booking_id
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
