import boto3
import zipfile

lambda_client = boto3.client('lambda')

# Your LabRole ARN
role_arn = "arn:aws:iam::943886678149:role/LabRole"

# Create a simple Lambda handler file
with open('lambda_function.py', 'w') as f:
    f.write("""
def lambda_handler(event, context):
    return "Hello from Lambda"
""")

# Zip the handler
with zipfile.ZipFile('function.zip', 'w') as z:
    z.write('lambda_function.py')

# Try to create Lambda function
response = lambda_client.create_function(
    FunctionName="TestLambda",
    Runtime="python3.9",
    Role=role_arn,
    Handler="lambda_function.lambda_handler",
    Code={"ZipFile": open("function.zip", "rb").read()},
    Timeout=5
)

print(response)
