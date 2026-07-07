from pydantic import BaseModel


class MemeResponse(BaseModel):
    id: str
    category: str
    blobUrl: str
    fileHash: str
    uploadedAt: str
    originalFilename: str
    ocrText: str
    caption: str
    templateName: str
    tags: list[str]
    sourceUrl: str
    searchableText: str
    embeddingModel: str
    embeddingDimensions: int


class IngestResponse(BaseModel):
    id: str
    blobUrl: str


class SearchResultItem(BaseModel):
    id: str
    blobUrl: str
    caption: str
    templateName: str
    tags: list[str]
    category: str
    uploadedAt: str
    similarity: float


class TextSearchRequest(BaseModel):
    query: str
    topK: int = 10
    category: str | None = None


class UpdateMemeRequest(BaseModel):
    category: str | None = None
    templateName: str | None = None
    caption: str | None = None
    ocrText: str | None = None
    tags: list[str] | None = None
    sourceUrl: str | None = None
