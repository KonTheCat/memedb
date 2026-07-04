import json

from azure.cosmos import CosmosClient

from memedb.config import Settings
from memedb.models import MemeDocument


def _escape_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class CosmosService:
    def __init__(self, settings: Settings):
        client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        database = client.get_database_client(settings.cosmos_database)
        self._container = database.get_container_client(settings.cosmos_container)

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
