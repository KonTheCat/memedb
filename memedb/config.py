import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    cosmos_endpoint: str
    cosmos_key: str
    cosmos_database: str
    cosmos_container: str

    vision_endpoint: str
    vision_key: str
    vision_model_version: str

    openai_endpoint: str
    openai_key: str
    openai_deployment: str

    blob_account_name: str
    blob_account_key: str
    blob_container: str

    app_password: str


def load_settings() -> Settings:
    return Settings(
        cosmos_endpoint=_require("COSMOS_ENDPOINT"),
        cosmos_key=_require("COSMOS_KEY"),
        cosmos_database=_require("COSMOS_DATABASE"),
        cosmos_container=_require("COSMOS_CONTAINER"),
        vision_endpoint=_require("AZURE_VISION_ENDPOINT"),
        vision_key=_require("AZURE_VISION_KEY"),
        vision_model_version=_require("AZURE_VISION_MODEL_VERSION"),
        openai_endpoint=_require("AZURE_OPENAI_ENDPOINT"),
        openai_key=_require("AZURE_OPENAI_KEY"),
        openai_deployment=_require("AZURE_OPENAI_DEPLOYMENT"),
        blob_account_name=_require("BLOB_ACCOUNT_NAME"),
        blob_account_key=_require("BLOB_ACCOUNT_KEY"),
        blob_container=_require("BLOB_CONTAINER"),
        app_password=_require("APP_PASSWORD"),
    )
