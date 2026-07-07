import hashlib
import uuid
from datetime import datetime, timezone

from memedb.models import MemeDocument
from memedb.services.blob import BlobService
from memedb.services.cosmos import CosmosService
from memedb.services.openai_client import OpenAIMetadataService
from memedb.services.vision import VisionService


class DuplicateMemeError(Exception):
    def __init__(self, existing_id: str):
        super().__init__(f"duplicate of {existing_id}")
        self.existing_id = existing_id


def build_searchable_text(ocr_text: str, caption: str, template_name: str, tags: list[str]) -> str:
    parts = [ocr_text, caption, template_name, *tags]
    return " ".join(p for p in parts if p)


EDITABLE_FIELDS = ("category", "templateName", "caption", "ocrText", "tags", "sourceUrl")


def update_meme_fields(
    meme_id: str,
    current_category: str,
    updates: dict,
    cosmos_service: CosmosService,
) -> dict:
    full_doc = cosmos_service.get_full_by_id(meme_id, current_category)
    for field in EDITABLE_FIELDS:
        if field in updates and updates[field] is not None:
            full_doc[field] = updates[field]
    full_doc["searchableText"] = build_searchable_text(
        full_doc["ocrText"], full_doc["caption"], full_doc["templateName"], full_doc["tags"]
    )
    cosmos_service.replace_meme(full_doc, current_category)
    return cosmos_service.get_by_id(meme_id)


def ingest_image(
    data: bytes,
    original_filename: str,
    category: str,
    template_name_override: str | None,
    source_url: str,
    blob_service: BlobService,
    vision_service: VisionService,
    openai_service: OpenAIMetadataService,
    cosmos_service: CosmosService,
) -> MemeDocument:
    file_hash = hashlib.sha256(data).hexdigest()

    existing = cosmos_service.find_by_hash(file_hash)
    if existing:
        raise DuplicateMemeError(existing["id"])

    doc_id = str(uuid.uuid4())
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    blob_name = f"{doc_id}.{ext}"

    blob_url = blob_service.upload_image(data, blob_name)
    vector = vision_service.vectorize_image(data)
    metadata = openai_service.extract_metadata(data, ext)

    template_name = template_name_override or metadata.get("templateName", "")
    tags = metadata.get("tags", [])
    ocr_text = metadata.get("ocrText", "")
    caption = metadata.get("caption", "")

    doc = MemeDocument(
        id=doc_id,
        category=category,
        blobUrl=blob_url,
        fileHash=file_hash,
        uploadedAt=datetime.now(timezone.utc).isoformat(),
        originalFilename=original_filename,
        ocrText=ocr_text,
        caption=caption,
        templateName=template_name,
        tags=tags,
        sourceUrl=source_url,
        searchableText=build_searchable_text(ocr_text, caption, template_name, tags),
        visualEmbedding=vector,
        embeddingModel=vision_service.model_version,
    )
    cosmos_service.upsert_meme(doc)
    return doc


def search_by_text(
    query: str,
    category: str | None,
    top_k: int,
    vision_service: VisionService,
    cosmos_service: CosmosService,
) -> list[dict]:
    query_vector = vision_service.vectorize_text(query)
    words = query.split()[:10]
    return cosmos_service.search_hybrid(query_vector, words, category, top_k)


def blob_name_from_url(blob_url: str) -> str:
    return blob_url.rsplit("/", 1)[-1]


def search_by_image(
    data: bytes,
    category: str | None,
    top_k: int,
    vision_service: VisionService,
    cosmos_service: CosmosService,
) -> list[dict]:
    query_vector = vision_service.vectorize_image(data)
    return cosmos_service.search_vector(query_vector, category, top_k)
