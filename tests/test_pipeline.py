import pytest

from memedb.pipeline import (
    DuplicateMemeError,
    blob_name_from_url,
    build_searchable_text,
    ingest_image,
    update_meme_fields,
)
from tests.fakes import FakeBlobService, FakeCosmosService, FakeOpenAIMetadataService, FakeVisionService


def test_build_searchable_text_joins_nonempty_parts():
    result = build_searchable_text("such wow", "a dog", "doge", ["dog", "meme"])
    assert result == "such wow a dog doge dog meme"


def test_build_searchable_text_skips_empty_parts():
    result = build_searchable_text("", "a dog", "", [])
    assert result == "a dog"


def test_blob_name_from_url_takes_last_path_segment():
    assert blob_name_from_url("https://acct.blob.core.windows.net/memes/abc123.png") == "abc123.png"


def _ingest(data: bytes, filename: str, cosmos_service, blob_service):
    return ingest_image(
        data,
        filename,
        "reaction",
        None,
        "https://example.com/src",
        blob_service,
        FakeVisionService(),
        FakeOpenAIMetadataService(),
        cosmos_service,
    )


def test_ingest_image_stores_and_returns_document():
    cosmos_service = FakeCosmosService()
    blob_service = FakeBlobService()

    doc = _ingest(b"fake-image-bytes", "doge.png", cosmos_service, blob_service)

    assert doc.category == "reaction"
    assert doc.templateName == "doge"
    assert doc.tags == ["dog", "meme"]
    assert doc.blobUrl.endswith(f"{doc.id}.png")
    assert cosmos_service.get_by_id(doc.id) is not None


def test_ingest_image_raises_on_duplicate_hash():
    cosmos_service = FakeCosmosService()
    blob_service = FakeBlobService()
    data = b"same-bytes"

    first = _ingest(data, "a.png", cosmos_service, blob_service)

    with pytest.raises(DuplicateMemeError) as exc_info:
        _ingest(data, "b.png", cosmos_service, blob_service)
    assert exc_info.value.existing_id == first.id


def test_update_meme_fields_merges_updates_and_rebuilds_searchable_text():
    cosmos_service = FakeCosmosService()
    blob_service = FakeBlobService()
    doc = _ingest(b"some-bytes", "a.png", cosmos_service, blob_service)

    updated = update_meme_fields(
        doc.id,
        doc.category,
        {"caption": "new caption", "tags": ["updated"]},
        cosmos_service,
    )

    assert updated["caption"] == "new caption"
    assert updated["tags"] == ["updated"]
    assert "new caption" in updated["searchableText"]
