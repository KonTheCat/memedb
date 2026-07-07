"""In-memory stand-ins for the Azure/OpenAI-backed services, used in place of mocks."""

from memedb.models import MemeDocument


class FakeBlobService:
    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    def upload_image(self, data: bytes, blob_name: str) -> str:
        self.blobs[blob_name] = data
        return f"https://fakeaccount.blob.core.windows.net/memes/{blob_name}"

    def delete_image(self, blob_name: str) -> None:
        self.blobs.pop(blob_name, None)

    def download_image(self, blob_name: str) -> tuple[bytes, str]:
        return self.blobs.get(blob_name, b""), "image/jpeg"


class FakeVisionService:
    model_version = "fake-vision-v1"

    def vectorize_image(self, data: bytes) -> list[float]:
        return [0.1, 0.2, 0.3]

    def vectorize_text(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeOpenAIMetadataService:
    def extract_metadata(self, data: bytes, ext: str) -> dict:
        return {
            "ocrText": "such wow",
            "caption": "a dog looking skeptical",
            "templateName": "doge",
            "tags": ["dog", "meme"],
        }


class FakeCosmosService:
    def __init__(self):
        self._docs: dict[str, dict] = {}

    @staticmethod
    def _public(doc: dict) -> dict:
        return {k: v for k, v in doc.items() if k != "visualEmbedding"}

    def get_by_id(self, doc_id: str) -> dict | None:
        doc = self._docs.get(doc_id)
        return self._public(doc) if doc is not None else None

    def get_full_by_id(self, doc_id: str, category: str) -> dict:
        return dict(self._docs[doc_id])

    def list_memes(self, category: str | None, limit: int, offset: int) -> list[dict]:
        docs = [d for d in self._docs.values() if category is None or d["category"] == category]
        return [self._public(d) for d in docs[offset : offset + limit]]

    def count_memes(self, category: str | None) -> int:
        return sum(1 for d in self._docs.values() if category is None or d["category"] == category)

    def delete_meme(self, doc_id: str, category: str) -> None:
        self._docs.pop(doc_id, None)

    def replace_meme(self, doc: dict, previous_category: str) -> None:
        self._docs[doc["id"]] = doc

    def find_by_hash(self, file_hash: str) -> dict | None:
        for doc in self._docs.values():
            if doc["fileHash"] == file_hash:
                return {"id": doc["id"], "blobUrl": doc["blobUrl"]}
        return None

    def upsert_meme(self, doc: MemeDocument) -> None:
        self._docs[doc.id] = doc.to_dict()

    def search_hybrid(
        self,
        query_vector: list[float],
        words: list[str],
        category: str | None,
        top_k: int,
    ) -> list[dict]:
        return []

    def search_vector(
        self,
        query_vector: list[float],
        category: str | None,
        top_k: int,
    ) -> list[dict]:
        return []
