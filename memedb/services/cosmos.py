import json

from azure.cosmos import CosmosClient

from memedb.config import Settings
from memedb.models import MemeDocument


def _escape_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# Every field except visualEmbedding — the doc's schema explicitly calls out
# excluding the 1024-float array from API responses to keep them small.
_PUBLIC_FIELDS = (
    "c.id, c.category, c.blobUrl, c.fileHash, c.uploadedAt, c.originalFilename, "
    "c.ocrText, c.caption, c.templateName, c.tags, c.sourceUrl, c.searchableText, "
    "c.embeddingModel, c.embeddingDimensions"
)


class CosmosService:
    def __init__(self, settings: Settings):
        client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        database = client.get_database_client(settings.cosmos_database)
        self._container = database.get_container_client(settings.cosmos_container)

    def get_by_id(self, doc_id: str) -> dict | None:
        query = f"SELECT {_PUBLIC_FIELDS} FROM c WHERE c.id = @id"
        items = list(
            self._container.query_items(
                query=query,
                parameters=[{"name": "@id", "value": doc_id}],
                enable_cross_partition_query=True,
            )
        )
        return items[0] if items else None

    def list_memes(self, category: str | None, limit: int, offset: int) -> list[dict]:
        where_clause = "WHERE c.category = @category" if category is not None else ""
        query = f"SELECT {_PUBLIC_FIELDS} FROM c {where_clause} OFFSET @offset LIMIT @limit"
        parameters = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        if category is not None:
            parameters.append({"name": "@category", "value": category})
        return list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )

    def count_memes(self, category: str | None) -> int:
        where_clause = "WHERE c.category = @category" if category is not None else ""
        query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
        parameters = [{"name": "@category", "value": category}] if category is not None else []
        results = list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        return results[0] if results else 0

    def delete_meme(self, doc_id: str, category: str) -> None:
        self._container.delete_item(item=doc_id, partition_key=category)

    def get_full_by_id(self, doc_id: str, category: str) -> dict:
        return self._container.read_item(item=doc_id, partition_key=category)

    def replace_meme(self, doc: dict, previous_category: str) -> None:
        # `category` is the partition key, which Cosmos DB treats as
        # immutable on an item — moving an item to a new partition key
        # value requires deleting it under the old key and recreating it
        # under the new one rather than an in-place replace.
        if doc["category"] != previous_category:
            self._container.create_item(doc)
            self._container.delete_item(item=doc["id"], partition_key=previous_category)
        else:
            self._container.replace_item(item=doc["id"], body=doc)

    def find_by_hash(self, file_hash: str) -> dict | None:
        query = "SELECT c.id, c.blobUrl FROM c WHERE c.fileHash = @hash"
        items = list(
            self._container.query_items(
                query=query,
                parameters=[{"name": "@hash", "value": file_hash}],
                enable_cross_partition_query=True,
            )
        )
        return items[0] if items else None

    def upsert_meme(self, doc: MemeDocument) -> None:
        self._container.upsert_item(doc.to_dict())

    def search_hybrid(
        self,
        query_vector: list[float],
        words: list[str],
        category: str | None,
        top_k: int,
    ) -> list[dict]:
        # Cosmos DB's query engine silently drops the WHERE filter (and can
        # return null projections) when a bind parameter is used anywhere in
        # a query that also has an ORDER BY RANK RRF(...) clause. Confirmed
        # empirically: identical queries return correct results with inline
        # literals but 0 rows / null columns with @-parameters in the same
        # positions. So the vector, category, and search words are inlined
        # as literals here; only TOP (unaffected) stays parameterized. The
        # vector is our own service's float output (safe to inline); the
        # category and words are escaped since they come from user input.
        vector_literal = json.dumps(query_vector)
        word_literals = ", ".join(f'"{_escape_string_literal(w)}"' for w in words)
        where_clause = ""
        if category is not None:
            where_clause = f'WHERE c.category = "{_escape_string_literal(category)}"'
        query = f"""
        SELECT TOP @topK
          c.id, c.blobUrl, c.ocrText, c.caption, c.templateName,
          c.tags, c.category, c.uploadedAt,
          VectorDistance(c.visualEmbedding, {vector_literal}) AS similarity
        FROM c
        {where_clause}
        ORDER BY RANK RRF(
          VectorDistance(c.visualEmbedding, {vector_literal}),
          FullTextScore(c.searchableText, {word_literals})
        )
        """
        parameters = [{"name": "@topK", "value": top_k}]
        return list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )

    def search_vector(
        self,
        query_vector: list[float],
        category: str | None,
        top_k: int,
    ) -> list[dict]:
        query = """
        SELECT TOP @topK
          c.id, c.blobUrl, c.ocrText, c.caption, c.templateName,
          c.tags, c.category, c.uploadedAt,
          VectorDistance(c.visualEmbedding, @queryVec) AS similarity
        FROM c
        WHERE (@category = null OR c.category = @category)
        ORDER BY VectorDistance(c.visualEmbedding, @queryVec)
        """
        parameters = [
            {"name": "@topK", "value": top_k},
            {"name": "@queryVec", "value": query_vector},
            {"name": "@category", "value": category},
        ]
        return list(
            self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
