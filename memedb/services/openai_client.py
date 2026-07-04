import base64
import json

from openai import AzureOpenAI

from memedb.config import Settings

_SYSTEM_PROMPT = """You are a meme metadata extractor. Given a meme image, return ONLY a JSON object
with these exact fields:
- ocrText: string — the exact text visible in the image, preserving original spelling/casing
- caption: string — one sentence describing what is happening in the image
- templateName: string — the common meme template name in kebab-case (e.g. "distracted-boyfriend"), or "" if unknown
- tags: array of strings — 3-8 relevant tags (topic, emotion, format, cultural reference)

Return only the JSON object. No markdown, no explanation."""

_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


class OpenAIMetadataService:
    def __init__(self, settings: Settings):
        self._client = AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_key=settings.openai_key,
            api_version="2024-06-01",
        )
        self._deployment = settings.openai_deployment

    def extract_metadata(self, data: bytes, ext: str) -> dict:
        mime_type = _MIME_TYPES.get(ext.lower(), "image/jpeg")
        b64_image = base64.b64encode(data).decode("ascii")

        response = self._client.chat.completions.create(
            model=self._deployment,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
                        }
                    ],
                },
            ],
        )
        content = response.choices[0].message.content
        return json.loads(content)
