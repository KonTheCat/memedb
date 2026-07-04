import argparse
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from memedb.config import load_settings
from memedb.models import VALID_CATEGORIES, MemeDocument
from memedb.services.blob import BlobService
from memedb.services.cosmos import CosmosService
from memedb.services.openai_client import OpenAIMetadataService
from memedb.services.vision import ImageValidationError, VisionService

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def build_searchable_text(ocr_text: str, caption: str, template_name: str, tags: list[str]) -> str:
    parts = [ocr_text, caption, template_name, *tags]
    return " ".join(p for p in parts if p)


def ingest_one(
    path: Path,
    category: str,
    template_name_override: str | None,
    source_url: str,
    blob_service: BlobService,
    vision_service: VisionService,
    openai_service: OpenAIMetadataService,
    cosmos_service: CosmosService,
) -> None:
    data = path.read_bytes()
    file_hash = hashlib.sha256(data).hexdigest()

    existing = cosmos_service.find_by_hash(file_hash)
    if existing:
        print(f"skipped {path.name}: duplicate of {existing['id']}")
        return

    doc_id = str(uuid.uuid4())
    ext = path.suffix.lstrip(".").lower()
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
        originalFilename=path.name,
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
    print(f"ingested {path.name}: {doc_id}")


def print_results(results: list[dict]) -> None:
    if not results:
        print("no results")
        return
    for rank, item in enumerate(results, start=1):
        tags = ", ".join(item.get("tags", []))
        print(
            f"{rank}. {item['id']} [{item['category']}] similarity={item.get('similarity'):.4f}\n"
            f"   caption: {item.get('caption', '')}\n"
            f"   template: {item.get('templateName', '')}  tags: {tags}\n"
            f"   {item.get('blobUrl', '')}"
        )


def cmd_search_text(args: argparse.Namespace) -> int:
    settings = load_settings()
    vision_service = VisionService(settings)
    cosmos_service = CosmosService(settings)

    query_vector = vision_service.vectorize_text(args.query)
    words = args.query.split()[:10]
    results = cosmos_service.search_hybrid(query_vector, words, args.category, args.top_k)
    print_results(results)
    return 0


def cmd_search_image(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"error: path not found: {path}", file=sys.stderr)
        return 1

    settings = load_settings()
    vision_service = VisionService(settings)
    cosmos_service = CosmosService(settings)

    try:
        query_vector = vision_service.vectorize_image(path.read_bytes())
    except ImageValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    results = cosmos_service.search_vector(query_vector, args.category, args.top_k)
    print_results(results)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"error: path not found: {path}", file=sys.stderr)
        return 1

    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        files = [path]

    if not files:
        print(f"error: no image files found at {path}", file=sys.stderr)
        return 1

    settings = load_settings()
    blob_service = BlobService(settings)
    vision_service = VisionService(settings)
    openai_service = OpenAIMetadataService(settings)
    cosmos_service = CosmosService(settings)

    exit_code = 0
    for file_path in files:
        try:
            ingest_one(
                file_path,
                args.category,
                args.template_name,
                args.source_url,
                blob_service,
                vision_service,
                openai_service,
                cosmos_service,
            )
        except ImageValidationError as exc:
            print(f"skipped {file_path.name}: {exc}", file=sys.stderr)
            exit_code = 1
        except Exception as exc:  # noqa: BLE001 - surface and continue batch ingestion
            print(f"error {file_path.name}: {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(prog="memedb")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest one image or a directory of images")
    ingest_parser.add_argument("path", help="Path to an image file or a directory of images")
    ingest_parser.add_argument("--category", required=True, choices=VALID_CATEGORIES)
    ingest_parser.add_argument("--template-name", default=None, help="Override the auto-detected template name")
    ingest_parser.add_argument("--source-url", default="")
    ingest_parser.set_defaults(func=cmd_ingest)

    search_text_parser = subparsers.add_parser("search-text", help="Search memes by text query")
    search_text_parser.add_argument("query", help="Text to search for")
    search_text_parser.add_argument("--top-k", type=int, default=10)
    search_text_parser.add_argument("--category", default=None, choices=VALID_CATEGORIES)
    search_text_parser.set_defaults(func=cmd_search_text)

    search_image_parser = subparsers.add_parser("search-image", help="Search memes by example image")
    search_image_parser.add_argument("path", help="Path to a query image")
    search_image_parser.add_argument("--top-k", type=int, default=10)
    search_image_parser.add_argument("--category", default=None, choices=VALID_CATEGORIES)
    search_image_parser.set_defaults(func=cmd_search_image)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
