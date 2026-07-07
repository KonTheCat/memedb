from azure.storage.blob import BlobServiceClient, ContentSettings

from memedb.config import Settings

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class BlobService:
    def __init__(self, settings: Settings):
        account_url = f"https://{settings.blob_account_name}.blob.core.windows.net"
        self._client = BlobServiceClient(account_url, credential=settings.blob_account_key)
        self._container = settings.blob_container

    def upload_image(self, data: bytes, blob_name: str) -> str:
        ext = blob_name.rsplit(".", 1)[-1].lower()
        content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

        container_client = self._client.get_container_client(self._container)
        container_client.upload_blob(
            name=blob_name,
            data=data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return f"{self._client.url.rstrip('/')}/{self._container}/{blob_name}"

    def delete_image(self, blob_name: str) -> None:
        container_client = self._client.get_container_client(self._container)
        container_client.delete_blob(blob_name)

    def download_image(self, blob_name: str) -> tuple[bytes, str]:
        container_client = self._client.get_container_client(self._container)
        blob_client = container_client.get_blob_client(blob_name)
        downloader = blob_client.download_blob()
        content_type = downloader.properties.content_settings.content_type or "application/octet-stream"
        return downloader.readall(), content_type
