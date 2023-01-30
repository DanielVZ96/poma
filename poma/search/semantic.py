import os
import io
from datetime import datetime
import json
from typing import List, Tuple
from authlib.integrations.requests_client import OAuth2Session

import argparse
import json
import logging
import struct

from authlib.integrations.requests_client import OAuth2Session
import requests
import grpc

import admin_pb2
import indexing_pb2
import services_pb2
import services_pb2_grpc
import serving_pb2

KEY = os.environ["SEMANTIC_KEY"]
REDIRECT_URI = os.environ["SEMANTIC_REDIRECT_URI"]
APP_ID = os.environ["SEMANTIC_APP_ID"]
CLIENT_SECRET = os.environ["SEMANTIC_CLIENT_SECRET"]
CUSTOMER_ID = os.environ["SEMANTIC_CUSTOMER_ID"]
SERVING_ENDPOINT = "serving.vectara.io"
INDEXING_ENDPOINT = "indexing.vectara.io"
UPLOAD_ENDPOINT = "https://api.vectara.io/v1/upload"
TOKEN = None


def _get_jwt_token() -> Tuple[str, datetime]:
    """Connect to the server and get a JWT token and it's expiration datetime."""
    global TOKEN
    if TOKEN is None or datetime.fromtimestamp(TOKEN["expires_in"]) < datetime.now():
        token_endpoint = f"{REDIRECT_URI}/oauth2/token"
        session = OAuth2Session(APP_ID, CLIENT_SECRET, scope="")
        TOKEN = session.fetch_token(token_endpoint, grant_type="client_credentials")
        return TOKEN["access_token"], datetime.fromtimestamp(TOKEN["expires_in"])
    return (TOKEN["access_token"], datetime.fromtimestamp(TOKEN["expires_in"]))


def index(
    document: indexing_pb2.Document,
    customer_id: int,
    corpus_id: int,
    idx_address: str,
    jwt_token: str,
):
    """ Indexes data to the corpus.
    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        idx_address: Address of the indexing server. e.g., indexing.vectara.io
        jwt_token: A valid Auth token.
    Returns:
        (None, True) in case of success and returns (error, False) in case of failure.
    """

    logging.info("Indexing data into the corpus.")
    index_req = services_pb2.IndexDocumentRequest()
    index_req.customer_id = customer_id
    index_req.corpus_id = corpus_id
    index_req.document.MergeFrom(document)

    try:
        index_stub = services_pb2_grpc.IndexServiceStub(
            grpc.secure_channel(idx_address, grpc.ssl_channel_credentials())
        )

        # Vectara API expects customer_id as a 64-bit binary encoded value in the metadata of
        # all grpcs calls. Following line generates the encoded value from customer ID.
        packed_customer_id = struct.pack(">q", customer_id)
        response = index_stub.Index(
            index_req,
            credentials=grpc.access_token_call_credentials(jwt_token),
            metadata=[("customer-id-bin", packed_customer_id)],
        )
        logging.info("Indexed document successful: %s", response)
    except grpc.RpcError as rpc_error:
        return rpc_error, False
    return None, True


def query(
    customer_id: int, corpus_id: int, query_address: str, jwt_token: str, query: str,
):
    """This method queries the data.
    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        query_address: Address of the querying server. e.g., serving.vectara.io
        jwt_token: A valid Auth token.
    Returns:
        (None, True) in case of success and returns (error, False) in case of failure.
    """

    headers = {"Authorization": f"Bearer {jwt_token}", "customer-id": str(customer_id)}
    payload = {
        "query": [
            {
                "query": query,
                "start": 0,
                "numResults": 20,
                "corpusKey": [
                    {
                        "customerId": customer_id,
                        "corpusId": corpus_id,
                        "semantics": "DEFAULT",
                    }
                ],
            }
        ]
    }
    response = requests.request(
        "POST", "https://api.vectara.io/v1/query", headers=headers, json=payload
    )
    if response.status_code != 200:
        logging.error(
            "REST upload failed with code %d, reason %s, text %s",
            response.status_code,
            response.reason,
            response.text,
        )
        return response, response.text, False
    return response, response.text, True


def search(query_string, corpus_id=2):
    token = _get_jwt_token()[0]
    response, error, success = query(
        CUSTOMER_ID, corpus_id, SERVING_ENDPOINT, token, query_string
    )
    return response, error, success


def store(id: str, title: str, is_title: bool, sections: List[str]):
    document = indexing_pb2.Document()
    document.metadata_json = json.dumps({"is_title": is_title})
    document.document_id = f"mvp-{id}"
    document.title = title
    for section_text in sections:
        section = indexing_pb2.Section()
        section.text = section_text
        document.section.extend([section])
    return document


def upload(fh: io.BytesIO, title: str, extension: str, mimetype: str, corpus_id=2):
    token, _ = _get_jwt_token()
    post_headers = {
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(
        f"https://api.vectara.io/v1/upload?c={CUSTOMER_ID}&o={corpus_id}&d=true",
        files={"file": (f"{title}{extension}", fh, mimetype)},
        headers=post_headers,
        data={"c": CUSTOMER_ID, "o": corpus_id, "d": True},
        stream=True,
    )
    if response.status_code != 200:
        logging.error(
            "REST upload failed with code %d, reason %s, text %s",
            response.status_code,
            response.reason,
            response.text,
        )
        return response, False
    return response, True


def create_corpus(name: str, description: str):
    """Create a corpus.
    Args:
        customer_id: Unique customer ID in vectara platform.
        admin_address: Address of the admin server. e.g., api.vectara.io
        jwt_token: A valid Auth token.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.
    """

    jwt_token, _ = _get_jwt_token()
    post_headers = {
        "customer-id": f"{CUSTOMER_ID}",
        "Authorization": f"Bearer {jwt_token}",
    }
    corpus = {"corpus": {"name": name, "description": description,}}
    response = requests.post(
        f"https://api.vectara.io/v1/create-corpus",
        verify=True,
        headers=post_headers,
        json=corpus,
    )

    if response.status_code != 200:
        logging.error(
            "Create Corpus failed with code %d, reason %s, text %s",
            response.status_code,
            response.reason,
            response.text,
        )
        return response, False
    return response, True
