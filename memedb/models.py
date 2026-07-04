from dataclasses import dataclass, field

VALID_CATEGORIES = [
    "reaction",
    "advice-animal",
    "surreal",
    "political",
    "wholesome",
    "dark",
    "meta",
    "other",
]


@dataclass
class MemeDocument:
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

    visualEmbedding: list[float]
    embeddingModel: str
    embeddingDimensions: int = field(default=1024)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "blobUrl": self.blobUrl,
            "fileHash": self.fileHash,
            "uploadedAt": self.uploadedAt,
            "originalFilename": self.originalFilename,
            "ocrText": self.ocrText,
            "caption": self.caption,
            "templateName": self.templateName,
            "tags": self.tags,
            "sourceUrl": self.sourceUrl,
            "searchableText": self.searchableText,
            "visualEmbedding": self.visualEmbedding,
            "embeddingModel": self.embeddingModel,
            "embeddingDimensions": self.embeddingDimensions,
        }
