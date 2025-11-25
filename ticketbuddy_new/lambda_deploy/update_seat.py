# lambda_deploy/update_seat.py
import json
import boto3
import uuid
from botocore.exceptions import ClientError

dynamo = boto3.resource("dynamodb")
SEATS = dynamo.Table("TicketBuddy_Seats")

def lambda_handler(event, context):
    """
    event: {
        "route_id": "R1001",
        "seats": ["A1","A2"],
        "booking_id": "optional"
    }
    """

    route = event.get("route_id")
    seats = event.get("seats", [])
    booking_id = event.get("booking_id") or str(uuid.uuid4())

    if not route or not seats:
        return {"status": "error", "message": "Missing route_id or seats"}

    try:
        # 1) Check if seats already booked
        for seat in seats:
            resp = SEATS.get_item(
                Key={"route_id": route, "seat_no": seat}   # FIXED
            )
            if "Item" in resp:
                return {
                    "status": "error",
                    "message": f"Seat already booked: {seat}",
                    "conflict": seat
                }

        # 2) Book each seat
        for seat in seats:
            SEATS.put_item(
                Item={
                    "route_id": route,
                    "seat_no": seat,     # FIXED
                    "status": "BOOKED",
                    "booking_id": booking_id
                }
            )

        return {
            "status": "success",
            "booking_id": booking_id,
            "booked": seats
        }

    except ClientError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
