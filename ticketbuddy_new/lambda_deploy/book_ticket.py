# lambda_deploy/book_ticket.py
import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
import traceback

dynamo = boto3.resource("dynamodb")
TICKETS = dynamo.Table("TicketBuddy_Tickets")
SCHEDULES = dynamo.Table("TicketBuddy_Schedules")  # optional lookup

def to_decimal(v, default="0"):
    try:
        return Decimal(str(v))
    except:
        return Decimal(default)

def lookup_schedule_fare(source, destination):
    try:
        resp = SCHEDULES.scan()  # small table acceptable
        for it in resp.get("Items", []):
            if it.get("source") == source and it.get("destination") == destination:
                return it.get("fare")
    except:
        pass
    return None

def lambda_handler(event, context):
    try:
        body = event if isinstance(event, dict) else json.loads(event.get("body","{}"))
        username = body.get("username")
        source = body.get("from") or body.get("source")
        destination = body.get("to") or body.get("destination")
        passengers = body.get("passengers", 1)
        seats = body.get("seats", [])
        fare = body.get("fare")

        if not fare:
            fare = lookup_schedule_fare(source, destination) or 0

        fare_dec = to_decimal(fare)
        passengers_dec = to_decimal(passengers)
        total = fare_dec * passengers_dec

        booking_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        item = {
            "booking_id": booking_id,
            "username": username,
            "source": source,
            "destination": destination,
            "passengers": passengers_dec,
            "seats": seats,
            "fare": total,  # Decimal
            "departure_time": body.get("departure_time",""),
            "arrival_time": body.get("arrival_time",""),
            "status": "CONFIRMED",
            "created_at": created_at
        }

        TICKETS.put_item(Item=item)

        return {"status": "success", "booking_id": booking_id, "item": item}
    except Exception as e:
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}
