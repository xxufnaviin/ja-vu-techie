from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3, os
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION_NAME = os.environ["AWS_REGION_NAME"]
OPENSEARCH_HOST = os.environ["OPENSEARCH_HOST"]
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "javutechnie-medical")

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_NAME
)

credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION_NAME,
    "es",
    session_token=credentials.token,
)

opensearch = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST.replace("https://", ""), "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

# Define index mapping
index_body = {
    "settings": {
        "analysis": {
            "analyzer": {
                "default": {"type": "standard"}
            }
        }
    },
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "content": {"type": "text"},
            "timestamp": {"type": "date"}
        }
    }
}

# Create index
# Create index
if not opensearch.indices.exists(index=OPENSEARCH_INDEX):
    opensearch.indices.create(index=OPENSEARCH_INDEX, body=index_body)
    print(f"✅ Created index: {OPENSEARCH_INDEX}")
else:
    print(f"ℹ️ Index already exists: {OPENSEARCH_INDEX}")

