import boto3
import json

dynamo = boto3.resource("dynamodb")
tickets_table = dynamo.Table("TicketBuddy_Tickets")
seats_table = dynamo.Table("TicketBuddy_Seats")
sns = boto3.client("sns")

TOPIC_ARN = "arn:aws:sns:us-east-1:943886678149:TicketBuddy_Alerts"

def lambda_handler(event, context):
    try:
        booking_id = event.get("booking_id")
        if not booking_id:
            return {"status": "error", "message": "Missing booking_id"}

        # 1️⃣ Get ticket
        resp = tickets_table.get_item(Key={"booking_id": booking_id})
        ticket = resp.get("Item")
        if not ticket:
            return {"status": "error", "message": "Booking not found"}

        route = ticket.get("route")
        dep_time = ticket.get("departure_time")
        seats = ticket.get("seats", [])

        # 2️⃣ Release seats
        if route and dep_time and seats:
            for seat in seats:
                composite = f"{dep_time}#{seat}"

                seats_table.update_item(
                    Key={
                        "route_id": route,
                        "departure_time_seat": composite
                    },
                    UpdateExpression="SET #s = :a",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":a": "AVAILABLE"}
                )

        # 3️⃣ Update ticket status
        tickets_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "CANCELLED"}
        )

        # (Optional SNS)
        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
