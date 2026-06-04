"""
S3-compatible object storage service for image and document uploads.

This module wraps the synchronous ``boto3`` client in an async-safe interface
using ``asyncio.get_running_loop().run_in_executor`` to offload blocking I/O
without stalling the FastAPI event loop.

The same ``S3Service`` class is used for both production AWS S3 and the local
MinIO instance used in development and testing.  The endpoint URL in
``core/config.py`` controls which backend is targeted at runtime.

Typical use-cases in this application:
- Delivery-note (BL) photo uploads during reception sessions.
- Corrective-action evidence photos for non-conformity tickets.
"""

import asyncio
import uuid
from pathlib import Path

import boto3
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class S3Service:
    """Async-safe wrapper around the boto3 S3 client.

    A new instance is created per request via the ``get_s3_service`` FastAPI
    dependency function.  This keeps the boto3 client stateless and avoids
    shared-state issues across concurrent requests.

    Attributes:
        bucket_name (str): The S3 bucket where all objects are stored.
        endpoint_url (str): The S3-compatible API endpoint (AWS or MinIO).
        public_endpoint_url (str): The publicly reachable base URL used to
            build download links for client applications.
        allowed_extensions (set[str]): Lowercase file extensions accepted for
            upload. Restricted to JPEG and PNG to limit attack surface.
    """

    allowed_extensions = {".jpg", ".jpeg", ".png"}

    def __init__(self) -> None:
        self.bucket_name = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.AWS_ENDPOINT_URL
        self.public_endpoint_url = settings.S3_PUBLIC_ENDPOINT_URL
        # boto3 client is created once per instance; it is thread-safe but not
        # async-native, hence the run_in_executor pattern in upload_image.
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    async def upload_image(self, file: UploadFile, prefix: str = "uploads") -> str:
        """Validate and upload an image file, returning the S3 object key.

        Validation is intentionally strict (extension and content-type) to
        prevent disguised executable uploads.  Only the S3 key is returned and
        stored — never a presigned URL — so that public URL construction remains
        under application control at read time.

        Args:
            file (UploadFile): The multipart file received by the FastAPI endpoint.
            prefix (str): S3 key prefix (virtual folder) for the upload.
                Defaults to ``"uploads"``.

        Returns:
            str: The S3 object key (e.g. ``"bl-photos/<uuid>.jpg"``). Store this
                value in the database; call ``object_url()`` to build a public URL.

        Raises:
            HTTPException: 400 Bad Request if the file extension or content-type
                is not an accepted image format.
        """
        extension = Path(file.filename or "").suffix.lower()
        if extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image extension. Only .jpg, .jpeg and .png are allowed.",
            )
        content_type = file.content_type or "application/octet-stream"
        if content_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image content type. Only JPEG and PNG images are allowed.",
            )

        # UUID-based key prevents filename collisions and avoids path traversal.
        key = f"{prefix.strip('/')}/{uuid.uuid4()}{extension}"
        await file.seek(0)

        loop = asyncio.get_running_loop()
        # boto3's upload_fileobj is blocking; offload it to a thread-pool
        # executor to avoid stalling the asyncio event loop during the upload.
        await loop.run_in_executor(
            None,
            lambda: self._client.upload_fileobj(
                file.file, self.bucket_name, key, ExtraArgs={"ContentType": content_type}
            ),
        )
        return key

    def object_url(self, key: str) -> str:
        """Build a public URL for a stored S3 object key.

        Args:
            key (str): The S3 object key as returned by ``upload_image``.

        Returns:
            str: The fully qualified public URL for the object.
        """
        return f"{self.public_endpoint_url.rstrip('/')}/{self.bucket_name}/{key.lstrip('/')}"


def get_s3_service() -> S3Service:
    """FastAPI dependency factory that returns a fresh ``S3Service`` instance.

    Returns:
        S3Service: A new S3 client wrapper configured from ``app.core.config``.
    """
    return S3Service()
