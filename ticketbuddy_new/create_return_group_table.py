import boto3

dynamo = boto3.client("dynamodb", region_name="us-east-1")

def create_table():
    table_name = "TicketBuddy_ReturnGroups"

    try:
        response = dynamo.create_table(
            TableName=table_name,
            AttributeDefinitions=[
                {"AttributeName": "group_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "group_id", "KeyType": "HASH"},
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        print("Creating table... wait 10 seconds")
        dynamo.get_waiter("table_exists").wait(TableName=table_name)
        print("Table created successfully!")

    except dynamo.exceptions.ResourceInUseException:
        print("Table already exists!")

if __name__ == "__main__":
    create_table()
