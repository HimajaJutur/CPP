import boto3

dynamo = boto3.client("dynamodb")

response = dynamo.create_table(
    TableName="TicketBuddy_Seats",
    KeySchema=[
        {"AttributeName": "route_id", "KeyType": "HASH"},
        {"AttributeName": "seat_id", "KeyType": "RANGE"},
    ],
    AttributeDefinitions=[
        {"AttributeName": "route_id", "AttributeType": "S"},
        {"AttributeName": "seat_id", "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST"
)

print("Table creation started:", response["TableDescription"]["TableStatus"])
