import io

import httpx
from PIL import Image

from memedb.config import Settings

MAX_BYTES = 20 * 1024 * 1024
MIN_DIMENSION = 10
MAX_DIMENSION = 16000

_API_VERSION = "2024-02-01"


class ImageValidationError(ValueError):
    pass


def validate_image(data: bytes) -> None:
    if len(data) > MAX_BYTES:
        raise ImageValidationError(f"Image is {len(data)} bytes, exceeds the 20MB limit")

    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size

    if not (MIN_DIMENSION <= width <= MAX_DIMENSION and MIN_DIMENSION <= height <= MAX_DIMENSION):
        raise ImageValidationError(
            f"Image dimensions {width}x{height} are outside the allowed "
            f"{MIN_DIMENSION}x{MIN_DIMENSION} - {MAX_DIMENSION}x{MAX_DIMENSION} range"
        )


class VisionService:
    def __init__(self, settings: Settings):
        self._endpoint = settings.vision_endpoint.rstrip("/")
        self._key = settings.vision_key
        self.model_version = settings.vision_model_version

    def vectorize_image(self, data: bytes) -> list[float]:
        validate_image(data)
        url = f"{self._endpoint}/computervision/retrieval:vectorizeImage"
        response = httpx.post(
            url,
            params={"api-version": _API_VERSION, "model-version": self.model_version},
            headers={
                "Content-Type": "application/octet-stream",
                "Ocp-Apim-Subscription-Key": self._key,
            },
            content=data,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["vector"]

    def vectorize_text(self, text: str) -> list[float]:
        url = f"{self._endpoint}/computervision/retrieval:vectorizeText"
        response = httpx.post(
            url,
            params={"api-version": _API_VERSION, "model-version": self.model_version},
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": self._key,
            },
            json={"text": text},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["vector"]
