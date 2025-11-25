import boto3
import os
import zipfile
import botocore.exceptions

LAMBDA_ROLE = "arn:aws:iam::943886678149:role/LabRole"
LAMBDA_DIR = "../lambda_deploy"

FUNCTIONS = {
    "TicketBuddy_BookTicket": "book_ticket.py",
    "TicketBuddy_GetHistory": "get_history.py",
    "TicketBuddy_CreateAlert": "create_alert.py",
    "TicketBuddy_CancelTicket": "cancel_ticket.py",
    "TicketBuddy_GetSchedules": "get_schedules.py",
    "TicketBuddy_SeedSeats": "seed_seats.py",
    "TicketBuddy_GetSeats": "get_seats.py",
    "TicketBuddy_UpdateSeat": "update_seat.py",
}

lambda_client = boto3.client("lambda")

def zip_lambda(py_file):
    zip_name = py_file.replace(".py", ".zip")
    py_path = os.path.join(LAMBDA_DIR, py_file)
    zip_path = os.path.join(LAMBDA_DIR, zip_name)

    print(f"Zipping {py_file} → {zip_name}")

    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(py_path, arcname=py_file)

    return zip_path


def deploy_lambda(function_name, file_name):
    zip_path = zip_lambda(file_name)

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    try:
        print(f"Creating Lambda: {function_name} ...")
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.9",
            Role=LAMBDA_ROLE,
            Handler=file_name.replace(".py", "") + ".lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=15
        )
        print(f"✔ CREATED {function_name}")

    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "ResourceConflictException":
            print(f"Updating Lambda: {function_name} ...")
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_bytes
            )
            print(f"✔ UPDATED {function_name}")
        else:
            raise e


if __name__ == "__main__":
    print("Deploying TicketBuddy Lambda Functions...\n")
    for fn, file in FUNCTIONS.items():
        deploy_lambda(fn, file)
    print("\n✔ ALL LAMBDAS DEPLOYED OR UPDATED SUCCESSFULLY")
