''' this file is used as module and does not run as a script '''

import hashlib
import json
import requests
from botocore.session import Session
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth

REGION = "us-east-1"
SERVICE = "neptune-db"
HOST = "db-neptune-1.cluster-cotecqm6cl3n.us-east-1.neptune.amazonaws.com"
URL = f"https://{HOST}:8182/sparql"

def neptune_query(sparql_query: str):
    """
    Execute a SPARQL SELECT query on Neptune and return the JSON result.
    """
    sess = Session()
    creds = sess.get_credentials().get_frozen_credentials()

    query_bytes = sparql_query.encode('utf-8')
    headers = {
        "host": f"{HOST}:8182",
        "content-type": "application/sparql-query",
        "accept": "application/sparql-results+json",
        "x-amz-content-sha256": hashlib.sha256(query_bytes).hexdigest(),
    }

    awsreq = AWSRequest(method="POST", url=URL, data=query_bytes, headers=headers)
    SigV4Auth(creds, SERVICE, REGION).add_auth(awsreq)

    resp = requests.post(URL, data=query_bytes, headers=dict(awsreq.headers), timeout=30)
    resp.raise_for_status()
    return resp.json()


def neptune_update(sparql_update: str):
    """
    Execute a SPARQL UPDATE statement on Neptune.
    """
    sess = Session()
    creds = sess.get_credentials().get_frozen_credentials()

    body_bytes = sparql_update.encode('utf-8')
    headers = {
        "host": f"{HOST}:8182",
        "content-type": "application/sparql-update",
        "x-amz-content-sha256": hashlib.sha256(body_bytes).hexdigest(),
    }

    awsreq = AWSRequest(method="POST", url=URL, data=body_bytes, headers=headers)
    SigV4Auth(creds, SERVICE, REGION).add_auth(awsreq)

    resp = requests.post(URL, data=body_bytes, headers=dict(awsreq.headers), timeout=30)
    resp.raise_for_status()
    return resp.status_code, resp.text


# ------------------------
# Example usage
# ------------------------

# Query example
query = 'SELECT ?name WHERE { <http://example.com/patient1> <http://example.com/hasName> ?name }'
result = neptune_query(query)
print(json.dumps(result, indent=2))

# Update example
update = 'INSERT DATA { <http://example.com/patient1> <http://example.com/hasName> "John Smith" . }'
status, text = neptune_update(update)
print(status, text)
