import boto3
import itertools

dynamo = boto3.resource("dynamodb")
SEAT_TABLE = dynamo.Table("TicketBuddy_Seats")
SCHEDULE_TABLE = dynamo.Table("TicketBuddy_Schedules")

ROWS = ["A", "B", "C", "D", "E"]
COUNT = 8

def lambda_handler(event, context):
    try:
        # Fetch all routes
        routes = SCHEDULE_TABLE.scan()["Items"]
        client = boto3.client("dynamodb")

        requests = []

        # Build batch write list
        for r in routes:
            route_id = r["route_id"]

            for row in ROWS:
                for n in range(1, COUNT + 1):
                    seat_no = f"{row}{n}"

                    requests.append({
                        "PutRequest": {
                            "Item": {
                                "route_id": {"S": route_id},
                                "seat_no": {"S": seat_no},
                                "is_booked": {"BOOL": False}
                            }
                        }
                    })

        # Batch write in chunks of 25
        for chunk in _chunks(requests, 25):
            client.batch_write_item(
                RequestItems={
                    "TicketBuddy_Seats": chunk
                }
            )

        return {
            "status": "success",
            "message": f"Seats generated for {len(routes)} routes",
            "total_seats": len(routes) * 40
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def _chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]
