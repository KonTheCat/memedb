import os
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from memedb.api.schemas import IngestResponse, MemeResponse, SearchResultItem, TextSearchRequest, UpdateMemeRequest
from memedb.config import Settings, load_settings
from memedb.models import VALID_CATEGORIES
from memedb.pipeline import (
    DuplicateMemeError,
    blob_name_from_url,
    ingest_image,
    search_by_image,
    search_by_text,
    update_meme_fields,
)
from memedb.services.blob import BlobService
from memedb.services.cosmos import CosmosService
from memedb.services.openai_client import OpenAIMetadataService
from memedb.services.vision import ImageValidationError, VisionService


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def verify_password(x_app_password: str | None = Header(None), settings: Settings = Depends(get_settings)) -> None:
    if x_app_password != settings.app_password:
        raise HTTPException(status_code=401, detail="invalid or missing password")


app = FastAPI(title="MemeDB API", dependencies=[Depends(verify_password)])

_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_blob_service() -> BlobService:
    return BlobService(get_settings())


@lru_cache
def get_vision_service() -> VisionService:
    return VisionService(get_settings())


@lru_cache
def get_openai_service() -> OpenAIMetadataService:
    return OpenAIMetadataService(get_settings())


@lru_cache
def get_cosmos_service() -> CosmosService:
    return CosmosService(get_settings())


def _validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"invalid category: {category}")


@app.get("/auth/check")
def auth_check() -> dict:
    # if this handler runs at all, the `verify_password` app-level dependency already
    # confirmed the caller's X-App-Password header is correct
    return {"ok": True}


@app.post("/memes", response_model=IngestResponse, status_code=201)
async def create_meme(
    image: UploadFile = File(...),
    category: str = Form(...),
    templateName: str | None = Form(None),
    sourceUrl: str = Form(""),
    blob_service: BlobService = Depends(get_blob_service),
    vision_service: VisionService = Depends(get_vision_service),
    openai_service: OpenAIMetadataService = Depends(get_openai_service),
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> IngestResponse:
    _validate_category(category)
    data = await image.read()

    try:
        doc = ingest_image(
            data,
            image.filename or "upload",
            category,
            templateName,
            sourceUrl,
            blob_service,
            vision_service,
            openai_service,
            cosmos_service,
        )
    except DuplicateMemeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "duplicate image", "id": exc.existing_id},
        ) from exc
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IngestResponse(id=doc.id, blobUrl=doc.blobUrl)


@app.post("/search/text", response_model=list[SearchResultItem])
def search_text(
    body: TextSearchRequest,
    vision_service: VisionService = Depends(get_vision_service),
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> list[dict]:
    if body.category is not None:
        _validate_category(body.category)
    return search_by_text(body.query, body.category, body.topK, vision_service, cosmos_service)


@app.post("/search/image", response_model=list[SearchResultItem])
async def search_image(
    image: UploadFile = File(...),
    topK: int = Form(10),
    category: str | None = Form(None),
    vision_service: VisionService = Depends(get_vision_service),
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> list[dict]:
    if category is not None:
        _validate_category(category)
    data = await image.read()

    try:
        return search_by_image(data, category, topK, vision_service, cosmos_service)
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/memes/count")
def count_memes(
    category: str | None = None,
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> dict:
    if category is not None:
        _validate_category(category)
    return {"count": cosmos_service.count_memes(category)}


@app.post("/memes/{meme_id}/view", status_code=204)
def record_view(
    meme_id: str,
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> Response:
    doc = cosmos_service.get_by_id(meme_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="meme not found")
    cosmos_service.increment_view_count(meme_id, doc["category"])
    return Response(status_code=204)


@app.get("/memes/{meme_id}", response_model=MemeResponse)
def get_meme(
    meme_id: str,
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> dict:
    doc = cosmos_service.get_by_id(meme_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="meme not found")
    return doc


@app.get("/memes/{meme_id}/image")
def get_meme_image(
    meme_id: str,
    blob_service: BlobService = Depends(get_blob_service),
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> Response:
    doc = cosmos_service.get_by_id(meme_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="meme not found")

    data, content_type = blob_service.download_image(blob_name_from_url(doc["blobUrl"]))
    return Response(content=data, media_type=content_type)


@app.get("/memes", response_model=list[MemeResponse])
def list_memes(
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> list[dict]:
    if category is not None:
        _validate_category(category)
    return cosmos_service.list_memes(category, limit, offset)


@app.patch("/memes/{meme_id}", response_model=MemeResponse)
def update_meme(
    meme_id: str,
    body: UpdateMemeRequest,
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> dict:
    doc = cosmos_service.get_by_id(meme_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="meme not found")
    if body.category is not None:
        _validate_category(body.category)

    updates = body.model_dump(exclude_unset=True)
    return update_meme_fields(meme_id, doc["category"], updates, cosmos_service)


@app.delete("/memes/{meme_id}", status_code=204)
def delete_meme(
    meme_id: str,
    blob_service: BlobService = Depends(get_blob_service),
    cosmos_service: CosmosService = Depends(get_cosmos_service),
) -> Response:
    doc = cosmos_service.get_by_id(meme_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="meme not found")

    cosmos_service.delete_meme(meme_id, doc["category"])
    blob_service.delete_image(blob_name_from_url(doc["blobUrl"]))
    return Response(status_code=204)
