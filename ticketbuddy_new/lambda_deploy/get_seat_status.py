# lambda_deploy/get_seat_status.py
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamo = boto3.resource("dynamodb")
SEATS = dynamo.Table("TicketBuddy_Seats")

def lambda_handler(event, context):

    # Accept both {"route_id"} and {"body": "..."}
    route = event.get("route_id")
    if not route and "body" in event:
        try:
            body = json.loads(event["body"])
            route = body.get("route_id")
        except:
            route = None

    if not route:
        return {"status": "error", "message": "Missing route_id"}

    try:
        # Query all booked seats for this route
        resp = SEATS.query(
            KeyConditionExpression=Key("route_id").eq(route)
        )

        # IMPORTANT: use seat_no (NOT seat_id)
        booked = [item["seat_no"] for item in resp.get("Items", [])]

        return {
            "status": "success",
            "booked_seats": booked
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
