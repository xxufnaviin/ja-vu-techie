import json
import re
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import boto3
from requests_aws4auth import AWS4Auth
import requests
from dotenv import load_dotenv
import os
from load import neptune_update

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME")
BEDROCK_MODEL_LLM = os.environ.get("BEDROCK_MODEL_LLM")

NEPTUNE_ENDPOINT = "https://db-neptune-1.cluster-cotecqm6cl3n.us-east-1.neptune.amazonaws.com:8182/sparql"
REGION = "us-east-1"

# Use IAM credentials (from env, ~/.aws/credentials, or role)
session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()

awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "neptune-db",
    session_token=credentials.token
)


def load_ocr_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[0]["parsed_results"]["full_text"]

def extract_metadata(text):
    metadata = {}
    
    patterns = {
        "Patient Name": r"Patient Name:\s*(.+)",
        "Patient ID": r"Patient ID:\s*(.+)",
        "DOB": r"Date of Birth:\s*(.+)",
        "Gender": r"Gender:\s*(.+)",
        "Doctor": r"(Dr\.\s*[A-Za-z ]+)"
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metadata[key] = match.group(1).strip()
            
    return metadata

def initialize_rebel_model():
    model_name = "Babelscape/rebel-large"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype="auto"
    )
    return model, tokenizer

def extract_relations(text, model, tokenizer):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_length=512)
    decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    return decoded[0]

def parse_rebel_output(raw_text):
    parts = raw_text.split("  ")
    triples = []
    for i in range(0, len(parts), 3):
        if i + 2 < len(parts):
            head = parts[i].strip()
            tail = parts[i + 1].strip()
            relation = parts[i + 2].strip()
            if head and relation and tail:
                triples.append({"head": head, "type": relation, "tail": tail})
    return triples

def build_graph(metadata, triples):
    graph_data = {"nodes": [], "edges": []}
    node_ids = set()

    if "Patient Name" in metadata:
        pname = metadata["Patient Name"]
        graph_data["nodes"].append({"id": pname, "label": "Patient"})
        node_ids.add(pname)

        if "Doctor" in metadata:
            doc = metadata["Doctor"]
            graph_data["nodes"].append({"id": doc, "label": "Doctor"})
            node_ids.add(doc)
            graph_data["edges"].append({"from": doc, "to": pname, "label": "treats"})

    # Add Rebel triples
    for t in triples:
        h, r, o = t["head"], t["type"], t["tail"]

        if h not in node_ids:
            graph_data["nodes"].append({"id": h, "label": "Entity"})
            node_ids.add(h)
        if o not in node_ids:
            graph_data["nodes"].append({"id": o, "label": "Entity"})
            node_ids.add(o)

        graph_data["edges"].append({"from": h, "to": o, "label": r})

    return graph_data

def create_sparql_insert(graph_data, prefix="http://javutech.com/"):
    insert_statements = []

    # Add nodes as triples (rdf:type)
    for node in graph_data["nodes"]:
        node_uri = f"<{prefix}{node['id'].replace(' ', '_')}>"
        insert_statements.append(f"{node_uri} <{prefix}type> \"{node['label']}\" .")

    # Add edges as triples
    for edge in graph_data["edges"]:
        from_uri = f"<{prefix}{edge['from'].replace(' ', '_')}>"
        to_uri = f"<{prefix}{edge['to'].replace(' ', '_')}>"
        label_uri = f"<{prefix}{edge['label'].replace(' ', '_')}>"
        insert_statements.append(f"{from_uri} {label_uri} {to_uri} .")

    return "INSERT DATA { " + " ".join(insert_statements) + " }"


def main(ocr_path_data):
    # Step 1: Load OCR data
    full_text = load_ocr_data(ocr_path_data)
    print("Extracted Text:\n", full_text, "...\n")

    # Step 2: Extract metadata
    metadata = extract_metadata(full_text)
    print("\nExtracted Metadata:", metadata)

    # Step 3: Initialize and run REBEL model
    model, tokenizer = initialize_rebel_model()
    rebel_output = extract_relations(full_text, model, tokenizer)
    print("\nRaw Rebel Output:", rebel_output)

    # Step 4: Parse REBEL output
    triples = parse_rebel_output(rebel_output)
    print("\nExtracted Triples:")
    for t in triples:
        print(f"({t['head']} , {t['type']} , {t['tail']})")

    # Step 5: Build and output graph
    graph_data = build_graph(metadata, triples)
    print("\nGraph JSON:\n", json.dumps(graph_data, indent=2))
    
    # Step 6: Create SPARQL insert statement
    sparql_insert = create_sparql_insert(graph_data)
    print("\nSPARQL Insert Statement:\n", sparql_insert)
    
    neptune_update(sparql_update=sparql_insert)
    

if __name__ == "__main__":
    main()