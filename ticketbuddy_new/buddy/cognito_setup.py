import boto3
import json

def create_cognito_pool():
    client = boto3.client("cognito-idp")

    print("Creating User Pool...")

    # Create User Pool
    pool = client.create_user_pool(
        PoolName="TicketBuddyUserPool",
        AutoVerifiedAttributes=["email"],
        Schema=[
            {
                "Name": "email",
                "AttributeDataType": "String",
                "Mutable": True,
                "Required": True,
            }
        ]
    )

    user_pool_id = pool["UserPool"]["Id"]
    print("User Pool Created:", user_pool_id)

    print("Creating App Client...")

    # Create App Client
    app_client = client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName="TicketBuddyAppClient",
        GenerateSecret=True,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH"
        ]
    )

    client_id = app_client["UserPoolClient"]["ClientId"]
    client_secret = app_client["UserPoolClient"]["ClientSecret"]

    print("App Client Created:", client_id)

    # Save config to cognito_config.py
    config = f'''
AWS_REGION = "us-east-1"
USER_POOL_ID = "{user_pool_id}"
CLIENT_ID = "{client_id}"
CLIENT_SECRET = "{client_secret}"
'''
    with open("buddy/cognito_config.py", "w") as f:
        f.write(config)

    print("\nConfiguration saved to buddy/cognito_config.py")

    return {
        "USER_POOL_ID": user_pool_id,
        "CLIENT_ID": client_id,
        "CLIENT_SECRET": client_secret,
    }


if __name__ == "__main__":
    result = create_cognito_pool()
    print("\nFinal Cognito Config:")
    print(json.dumps(result, indent=4))
