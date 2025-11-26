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
    dep_time = event.get("departure_time") 
    seats = event.get("seats", [])
    booking_id = event.get("booking_id") or str(uuid.uuid4())

    if not route or not dep_time:
        return {"status": "error", "message": "Missing route_id or departure_time"}
        
    if not seats:
        return {"status": "error", "message": "Missing seats"}

    try:
        
          # Build seat keys
        for seat in seats:
            composite = f"{dep_time}#{seat}"
            
            
            # Check conflict
            resp = SEATS.get_item(
                Key={"route_id": route, "departure_time_seat": composite}   # FIXED
            )
            if "Item" in resp and resp["Item"]["status"] == "BOOKED":
                return {
                    "status": "error",
                    "message": f"Seat already booked: {seat}",
                    "conflict": seat
                }
 # No conflicts → insert all
        for seat in seats:
            composite = f"{dep_time}#{seat}"
            SEATS.put_item(
                Item={
                    "route_id": route,
                    "departure_time_seat": composite,
                    "departure_time": dep_time,
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

    
    except Exception as e:
        return {"status": "error", "message": str(e)}
