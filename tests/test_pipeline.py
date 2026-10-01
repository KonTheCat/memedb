import pytest

from memedb.pipeline import (
    DuplicateMemeError,
    blob_name_from_url,
    build_searchable_text,
    ingest_image,
    search_by_image,
    search_by_text,
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


def _doc(doc_id: str, similarity: float, **overrides) -> dict:
    doc = {
        "id": doc_id,
        "blobUrl": f"https://example.com/{doc_id}.png",
        "ocrText": "",
        "caption": "",
        "templateName": "",
        "tags": [],
        "category": "reaction",
        "uploadedAt": "2026-01-01T00:00:00Z",
        "similarity": similarity,
    }
    doc.update(overrides)
    return doc


def test_search_by_text_attaches_bucket_and_matched_terms():
    cosmos_service = FakeCosmosService()
    cosmos_service.hybrid_results = [_doc("meme-1", 0.9, ocrText="such wow very dog")]

    results, no_strong_matches = search_by_text("dog", None, 5, FakeVisionService(), cosmos_service)

    assert results[0]["bucket"] == "strong"
    assert results[0]["matchedTerms"] == ["dog"]
    assert no_strong_matches is False


def test_search_by_text_no_strong_matches_when_all_weak():
    cosmos_service = FakeCosmosService()
    cosmos_service.hybrid_results = [_doc("meme-1", 0.01, ocrText="completely unrelated")]

    results, no_strong_matches = search_by_text("dog", None, 5, FakeVisionService(), cosmos_service)

    assert results[0]["bucket"] == "weak"
    assert no_strong_matches is True


def test_search_by_image_omits_matched_terms_and_uses_image_buckets():
    cosmos_service = FakeCosmosService()
    cosmos_service.vector_results = [_doc("meme-1", 0.95)]

    results, no_strong_matches = search_by_image(b"fake-bytes", None, 5, FakeVisionService(), cosmos_service)

    assert results[0]["bucket"] == "near_duplicate"
    assert results[0]["matchedTerms"] == []
    assert no_strong_matches is False
