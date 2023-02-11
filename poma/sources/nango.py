import os
from urllib.parse import urljoin
import requests

NANGO_HOSTPORT = os.getenv("NANGO_SERVER")
NANGO_SECRET_KEY = os.getenv("NANGO_SECRET_KEY", "")


def _get(path, provider, headers=None):
    headers = headers or {}
    url = urljoin(NANGO_HOSTPORT, path) + f"?provider_config_key={provider}"
    return requests.get(url, auth=(NANGO_SECRET_KEY, ""), headers=headers)


def _delete(path, provider):
    url = urljoin(NANGO_HOSTPORT, path) + f"?provider_config_key={provider}"
    return requests.delete(url, auth=(NANGO_SECRET_KEY, ""))


def get_token(provider, workspace_id):
    response = _get(f"connection/{provider}-{workspace_id}", provider)
    if response.ok:
        return response.json(), True
    else:
        return response.text, False


def revoke(provider, workspace_id):
    _delete(f"connection/{provider}-{workspace_id}")
