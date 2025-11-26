import json
import boto3
from boto3.dynamodb.conditions import Key

dynamo = boto3.resource("dynamodb")
SEATS = dynamo.Table("TicketBuddy_Seats")

def lambda_handler(event, context):
    route = event.get("route_id")
    dep_time = event.get("departure_time")
    
    if not route and "body" in event:
        try:
            body = json.loads(event["body"])
            route = body.get("route_id")
            dep_time = body.get("departure_time")
        except:
            pass

    if not route or not dep_time:
        return {"status": "error", "message": "Missing route_id or departure_time"}

    try:
        resp = SEATS.query(
            KeyConditionExpression=Key("route_id").eq(route)
        )

        # return only seat_no (A1, A2, A3…)
        booked = [item["seat_no"] for item in resp.get("Items", [])
        if item["departure_time"] == dep_time and item["status"] == "BOOKED"]

        return {"status": "success", "booked_seats": booked}

    except Exception as e:
        return {"status": "error", "message": str(e)}
