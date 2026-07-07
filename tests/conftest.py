import pytest
from httpx import ASGITransport, AsyncClient

from memedb.api.app import (
    app,
    get_blob_service,
    get_cosmos_service,
    get_openai_service,
    get_settings,
    get_vision_service,
)
from memedb.config import Settings
from tests.fakes import FakeBlobService, FakeCosmosService, FakeOpenAIMetadataService, FakeVisionService

TEST_SETTINGS = Settings(
    cosmos_endpoint="https://fake-cosmos.example.com",
    cosmos_key="fake-cosmos-key",
    cosmos_database="fake-db",
    cosmos_container="fake-container",
    vision_endpoint="https://fake-vision.example.com",
    vision_key="fake-vision-key",
    vision_model_version="fake-vision-v1",
    openai_endpoint="https://fake-openai.example.com",
    openai_key="fake-openai-key",
    openai_deployment="fake-deployment",
    blob_account_name="fakeaccount",
    blob_account_key="fake-blob-key",
    blob_container="memes",
    app_password="test-password",
)


@pytest.fixture
def cosmos_service():
    return FakeCosmosService()


@pytest.fixture
def blob_service():
    return FakeBlobService()


@pytest.fixture
def app_client(cosmos_service, blob_service):
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    app.dependency_overrides[get_blob_service] = lambda: blob_service
    app.dependency_overrides[get_vision_service] = lambda: FakeVisionService()
    app.dependency_overrides[get_openai_service] = lambda: FakeOpenAIMetadataService()
    app.dependency_overrides[get_cosmos_service] = lambda: cosmos_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-App-Password": TEST_SETTINGS.app_password},
    ) as ac:
        yield ac
