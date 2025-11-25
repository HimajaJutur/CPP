import boto3
import json
from boto3.dynamodb.conditions import Key, Attr

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

        # 1️⃣ Get the ticket details
        resp = tickets_table.get_item(Key={"booking_id": booking_id})
        ticket = resp.get("Item")

        if not ticket:
            return {"status": "error", "message": "Booking not found"}

        username = ticket.get("username")
        route_id = ticket.get("route")         # your Ticket table uses field "route"
        travel_date = ticket.get("departure_date")
        seats = ticket.get("seats", [])

        # 2️⃣ Release seats — only if route_id & seats exist
        if route_id and seats:
            for seat_id in seats:
                seats_table.update_item(
                    Key={
                        "route_id": route_id,
                        "seat_id": seat_id
                    },
                    UpdateExpression="SET #s = :a",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":a": "available"}
                )

        # 3️⃣ Mark ticket as CANCELLED
        tickets_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET #s = :c",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "CANCELLED"}
        )

        # 4️⃣ Send Email notification via SNS
        try:
            msg = (
                f"Hello {username},\n\n"
                f"Your ticket (Booking ID: {booking_id}) has been CANCELLED.\n\n"
                f"Released Seats: {', '.join(seats) if seats else 'None'}\n"
                f"Travel Date: {travel_date}\n"
                f"Route: {ticket.get('source')} → {ticket.get('destination')}\n\n"
                f"Thank you for using TicketBuddy 🚍"
            )

            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject="Your Ticket Has Been Cancelled",
                Message=msg
            )
        except Exception as sns_err:
            # Do not break cancellation if SNS fails
            print("SNS Error:", sns_err)

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
