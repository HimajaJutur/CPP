import boto3

BUCKET_NAME = "ticketbuddy-tickets-943886678149"  # use yours

s3 = boto3.client("s3")

def create_bucket():
    try:
        print(f"Creating bucket: {BUCKET_NAME}")
        s3.create_bucket(Bucket=BUCKET_NAME)   # no LocationConstraint for us-east-1
        print("Bucket created successfully!")
    except Exception as e:
        if "BucketAlreadyOwnedByYou" in str(e) or "BucketAlreadyExists" in str(e):
            print("Bucket already exists — proceeding.")
        else:
            raise e

if __name__ == "__main__":
    create_bucket()
    print("S3 Bucket setup completed ✔️ (Policy skipped for Learner Lab)")
