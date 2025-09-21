import os
import json
import boto3
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from typing import List

# ------------------ LOAD ENV ------------------
load_dotenv()

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")
BEDROCK_MODEL_LLM = os.environ.get("BEDROCK_MODEL_LLM")
OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX")

# ------------------ AWS BEDROCK ------------------s
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_NAME
)

# ------------------ AWS Client ------------------
bedrock = session.client(
    "bedrock-runtime", 
    region_name=AWS_REGION_NAME,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# ------------------ OpenSearch ------------------
credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION_NAME,
    "es",  # service name for OpenSearch
    session_token=credentials.token,
)

opensearch = OpenSearch(
    hosts=[OPENSEARCH_HOST],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

# ------------------ FastAPI ------------------
app = FastAPI()

class QueryIn(BaseModel):
    question: str
    top_k: int = 3

# ------------------ Helper Functions ------------------
def search_opensearch(query: str, top_k: int = 3) -> List[str]:
    """
    Search OpenSearch for relevant document snippets.
    """
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["content^2", "title"]
            }
        }
    }
    resp = opensearch.search(index=OPENSEARCH_INDEX, body=body)
    snippets = [hit["_source"]["content"] for hit in resp["hits"]["hits"]]
    return snippets

def call_bedrock(prompt: str):
    # Call AWS Bedrock LLM with a given prompt.
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"text": str(prompt)} 
                ]
            }
        ]
    }
    
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_LLM,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

    output = json.loads(response["body"].read().decode("utf-8"))
    return output

# ------------------ API ------------------
@app.post("/chat")
def chat(q: QueryIn):
    # Step 1: Retrieve relevant context from OpenSearch
    snippets = search_opensearch(q.question, top_k=q.top_k)
    
    # Step 2: Construct prompt for Bedrock including retrieved context
    context_text = "\n\n".join(snippets) if snippets else "No relevant documents found."
    prompt = f"""
    You are a medical AI assistant. Answer the following question using the provided documents. 
    Only use the information present in the documents.

    Documents:
    {context_text}

    Question:
    {q.question}
    """

    # Step 3: Get answer from Bedrock LLM
    answer = call_bedrock(prompt)
    return {"response": answer, "retrieved_snippets": snippets}