import os
import json
import boto3
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ---------- CONFIG ----------
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")
BEDROCK_MODEL_LLM = os.environ.get("BEDROCK_MODEL_LLM")

# ---------- CONNECTION ----------
session = boto3.Session(region_name=AWS_REGION_NAME)
bedrock = session.client(
    "bedrock-runtime", 
    region_name=AWS_REGION_NAME,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# ---------- FASTAPI APP ----------
app = FastAPI()

class QueryIn(BaseModel):
    question: str

def call_bedrock(prompt: str):
    payload = {
        "messages": [
            {
                "role": "user",  # must be "user" for your question
                "content": [
                    {"text": str(prompt)}  # the actual message
                ]
            }
        ]
    }
    
    # get response from LLM
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_LLM,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

    output = json.loads(response["body"].read().decode("utf-8"))
    return output

# API to handle input
@app.post("/chat")
def chat(q: QueryIn):
    answer = call_bedrock(q.question)
    return {"response": answer}
