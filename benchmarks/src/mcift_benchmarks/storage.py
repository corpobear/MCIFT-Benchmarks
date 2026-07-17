from __future__ import annotations

from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient


def require_safe_blob_uri(uri: str) -> None:
    parsed = urlparse(uri)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".blob.core.windows.net")
    ):
        raise ValueError("only HTTPS Azure Blob URIs are accepted")
    if parsed.query:
        raise ValueError("SAS/query credentials are not accepted; use Microsoft Entra ID")


def blob_client(uri: str) -> BlobClient:
    require_safe_blob_uri(uri)
    return BlobClient.from_blob_url(uri, credential=DefaultAzureCredential())
