import boto3
import os
from dotenv import load_dotenv
import os

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")


# Initialize S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_NAME
)

bucket_name = "javu-techie"
folder_prefix = "pdfs/"  # your S3 folder
local_dir = "pipeline/data"

os.makedirs(local_dir, exist_ok=True)

# List all objects in the folder
response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
for obj in response.get("Contents", []):
    key = obj["Key"]
    if key.endswith(".pdf"):  # only PDFs
        local_file_path = os.path.join(local_dir, os.path.basename(key))
        # Download file
        s3.download_file(bucket_name, key, local_file_path)
        print(f"Downloaded {local_file_path}")
