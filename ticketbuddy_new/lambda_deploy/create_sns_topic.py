import boto3

sns = boto3.client("sns")

def lambda_handler(event, context):
    response = sns.create_topic(Name="TicketBuddy_Alerts")
    return {"topic_arn": response["TopicArn"]}
