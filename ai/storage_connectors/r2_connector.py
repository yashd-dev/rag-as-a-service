from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.client import Config

from ai.schemas.documents import SourceObject


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class R2Connector:
    def __init__(self, bucket: str, endpoint_url: str | None = None, access_key_id: str | None = None, secret_access_key: str | None = None, public_base_url: str | None = None):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.public_base_url = public_base_url
        if access_key_id and secret_access_key:
            self.client = boto3.client("s3", endpoint_url=endpoint_url, aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key)
        else:
            self.client = boto3.client("s3", endpoint_url=endpoint_url, config=Config(signature_version=UNSIGNED))

    def object_url(self, object_key: str) -> str:
        base = self.public_base_url or f"https://{self.bucket}.s3.amazonaws.com"
        return f"{base.rstrip('/')}/{object_key.lstrip('/')}"

    def is_supported(self, object_key: str) -> bool:
        return Path(object_key.lower()).suffix in SUPPORTED_EXTENSIONS

    def list_objects(self, prefix: str = "") -> list[SourceObject]:
        objects = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not self.is_supported(key):
                    continue
                objects.append(SourceObject(object_key=key, size_bytes=obj.get("Size"), etag=str(obj.get("ETag", "")).strip('"'), last_modified=obj.get("LastModified").isoformat() if obj.get("LastModified") else None, url=self.object_url(key)))
        return objects

    def download_object(self, object_key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, object_key, str(destination))
