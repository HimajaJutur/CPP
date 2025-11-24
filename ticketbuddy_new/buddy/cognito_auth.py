import boto3, hmac, hashlib, base64
from botocore.exceptions import ClientError
from .cognito_config import AWS_REGION, USER_POOL_ID, CLIENT_ID, CLIENT_SECRET

client = boto3.client("cognito-idp", region_name=AWS_REGION)

def get_secret_hash(username):
    message = username + CLIENT_ID
    dig = hmac.new(CLIENT_SECRET.encode(), msg=message.encode(), digestmod=hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

# -----------------------------
# SIGN UP
# -----------------------------
def cognito_signup(username, email, password):
    try:
        return client.sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            Password=password,
            SecretHash=get_secret_hash(username),
            UserAttributes=[
                {'Name': 'email', 'Value': email}
            ]
        )
    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}

# -----------------------------
# CONFIRM SIGN UP (OTP)
# -----------------------------
def cognito_confirm(username, code):
    try:
        return client.confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            ConfirmationCode=code,
            SecretHash=get_secret_hash(username)
        )
    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}

# -----------------------------
# LOGIN
# -----------------------------
def cognito_login(username, password):
    try:
        return client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
                "SECRET_HASH": get_secret_hash(username)
            }
        )
    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}

# -----------------------------
# FORGOT PASSWORD (Send OTP)
# -----------------------------
def cognito_forgot_password(username):
    try:
        return client.forgot_password(
            ClientId=CLIENT_ID,
            Username=username,
            SecretHash=get_secret_hash(username)
        )
    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}

# -----------------------------
# CONFIRM NEW PASSWORD (Reset)
# -----------------------------
def cognito_confirm_new_password(username, code, new_password):
    try:
        return client.confirm_forgot_password(
            ClientId=CLIENT_ID,
            Username=username,
            ConfirmationCode=code,
            Password=new_password,
            SecretHash=get_secret_hash(username)
        )
    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}
