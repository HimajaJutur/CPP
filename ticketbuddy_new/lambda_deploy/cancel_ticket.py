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

        # 1️⃣ Fetch the ticket
        resp = tickets_table.get_item(Key={"booking_id": booking_id})
        ticket = resp.get("Item")

        if not ticket:
            return {"status": "error", "message": "Booking not found"}

        route = ticket.get("route")
        dep_time = ticket.get("departure_time")
        seats = ticket.get("seats", [])

        # 2️⃣ Release seats (mark them AVAILABLE again)
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

        # 3️⃣ Update ticket status in DynamoDB
        tickets_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "CANCELLED"}
        )

        # 4️⃣ Send cancellation email via SNS
        message = (
            f"Your TicketBuddy booking has been cancelled.\n\n"
            f"Booking ID: {booking_id}\n"
            f"Route: {ticket.get('source')} → {ticket.get('destination')}\n"
            f"Date: {ticket.get('departure_date')}\n"
            f"Seats: {', '.join(ticket.get('seats', []))}\n"
            f"Status: CANCELLED\n\n"
            f"If this was not you, please contact support."
        )

        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="TicketBuddy – Ticket Cancelled",
            Message=message
        )

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
