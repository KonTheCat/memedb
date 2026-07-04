# Meme Database Application — Claude Code Project Brief

## What we're building

A web application that stores a searchable library of memes. Users can search by typing text ("distracted boyfriend") or uploading an image, and the app returns the most visually and semantically similar memes from the database. New memes can be ingested via an upload endpoint.

---

## Azure services to provision

Before writing any code, the following Azure resources must exist. Confirm each one is created and that the relevant keys/endpoints are available as environment variables.

| Resource | Purpose | Notes |
|---|---|---|
| **Azure App Service (Web App)** | Hosts the Python/Node API | Linux, at least B2 tier |
| **Azure Blob Storage** | Stores raw meme image files | Create a container named `memes` |
| **Azure AI Vision (Foundry)** | Generates 1024-dim embeddings for images and text | Must be in a supported region: East US, West Europe, Korea Central, North Europe, Southeast Asia, or France Central |
| **Azure OpenAI** | GPT-4o for OCR + metadata extraction | Deploy `gpt-4o` in the same subscription |
| **Azure Cosmos DB for NoSQL** | Document store with DiskANN vector index + BM25 full-text index | Enable the "Vector Search for NoSQL API" feature flag on the account before creating containers |

### Required environment variables

```
COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
COSMOS_KEY=<primary key>
COSMOS_DATABASE=memedb
COSMOS_CONTAINER=memes

AZURE_VISION_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_VISION_KEY=<key>
AZURE_VISION_MODEL_VERSION=2023-04-15

AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o

BLOB_ACCOUNT_NAME=<storage account name>
BLOB_ACCOUNT_KEY=<key>
BLOB_CONTAINER=memes
```

---

## Cosmos DB setup (run once before any ingestion)

### 1. Enable vector search on the account

In the Azure portal → your Cosmos DB account → Settings → Features → enable **"Vector Search for NoSQL API"**.

### 2. Create the database and container

Database name: `memedb`  
Container name: `memes`  
Partition key: `/category`

### 3. Apply the vector embedding policy

```json
{
  "vectorEmbeddings": [
    {
      "path": "/visualEmbedding",
      "dataType": "float32",
      "distanceFunction": "cosine",
      "dimensions": 1024
    }
  ]
}
```

### 4. Apply the full-text policy

```json
{
  "defaultLanguage": "en-US",
  "fullTextPaths": [
    {
      "path": "/searchableText",
      "language": "en-US"
    }
  ]
}
```

### 5. Apply the indexing policy

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [{ "path": "/*" }],
  "excludedPaths": [
    { "path": "/\"_etag\"/?" },
    { "path": "/visualEmbedding/*" }
  ],
  "fullTextIndexes": [
    { "path": "/searchableText" }
  ],
  "vectorIndexes": [
    { "path": "/visualEmbedding", "type": "DiskANN" }
  ]
}
```

> **Important:** Vector policies and vector indexes are immutable after creation. Get these right before ingesting any data. If you need to change them, you must delete and recreate the container.

---

## Cosmos DB document schema

Every meme is stored as a single document:

```json
{
  "id": "<uuid-v4>",
  "category": "reaction",

  "blobUrl": "https://<account>.blob.core.windows.net/memes/<filename>",
  "fileHash": "<sha256 of image bytes>",
  "uploadedAt": "<ISO 8601 timestamp>",
  "originalFilename": "boromir.jpg",

  "ocrText": "One does not simply walk into Mordor",
  "caption": "Boromir from Lord of the Rings making a serious point about difficulty",
  "templateName": "one-does-not-simply",
  "tags": ["lotr", "boromir", "impossibility", "sarcasm", "fantasy"],
  "sourceUrl": "",

  "searchableText": "One does not simply walk into Mordor Boromir Lord of the Rings reaction sarcasm impossibility one-does-not-simply",

  "visualEmbedding": [-0.094, 0.012, "...1024 floats total..."],
  "embeddingModel": "2023-04-15",
  "embeddingDimensions": 1024
}
```

The `searchableText` field is a denormalized concatenation of `ocrText`, `caption`, `templateName`, and `tags` joined by spaces. This is the field targeted by BM25 full-text search.

Valid `category` values (the partition key): `reaction`, `advice-animal`, `surreal`, `political`, `wholesome`, `dark`, `meta`, `other`

---

## API endpoints to implement

### POST /memes — ingest a new meme

**Request:** `multipart/form-data` with:
- `image` — the image file (JPG, PNG, GIF, WebP)
- `category` — one of the valid category values above
- `templateName` (optional) — human-readable template identifier
- `sourceUrl` (optional)

**Processing pipeline (in order):**

1. Compute SHA-256 of image bytes. Check Cosmos DB for an existing document with that `fileHash`. If found, return `409 Conflict` with the existing document ID — do not re-ingest duplicates.

2. Generate a UUID for the new document. Upload the image to Blob Storage at path `<uuid>.<ext>`. Capture the full blob URL.

3. Call Azure AI Vision `vectorizeImage` with the image bytes (or blob URL):
   ```
   POST {AZURE_VISION_ENDPOINT}/computervision/retrieval:vectorizeImage
       ?api-version=2024-02-01&model-version={AZURE_VISION_MODEL_VERSION}
   Content-Type: application/octet-stream
   Ocp-Apim-Subscription-Key: {AZURE_VISION_KEY}
   Body: <raw image bytes>
   ```
   Extract `response.vector` — this is the 1024-dim float array.

4. Call Azure OpenAI GPT-4o with the image (base64-encoded) and this system prompt:
   ```
   You are a meme metadata extractor. Given a meme image, return ONLY a JSON object
   with these exact fields:
   - ocrText: string — the exact text visible in the image, preserving original spelling/casing
   - caption: string — one sentence describing what is happening in the image
   - templateName: string — the common meme template name in kebab-case (e.g. "distracted-boyfriend"), or "" if unknown
   - tags: array of strings — 3-8 relevant tags (topic, emotion, format, cultural reference)

   Return only the JSON object. No markdown, no explanation.
   ```
   Parse the JSON response. Build `searchableText` by joining `ocrText`, `caption`, `templateName`, and `tags` with spaces.

5. Write the Cosmos DB document with all fields assembled. Return `201 Created` with the document ID and blob URL.

---

### POST /search/text — search by text query

**Request body:**
```json
{
  "query": "surprised pikachu face",
  "topK": 10,
  "category": null
}
```

**Processing:**

1. Call Azure AI Vision `vectorizeText`:
   ```
   POST {AZURE_VISION_ENDPOINT}/computervision/retrieval:vectorizeText
       ?api-version=2024-02-01&model-version={AZURE_VISION_MODEL_VERSION}
   Content-Type: application/json
   Body: { "text": "<query>" }
   ```
   Extract `response.vector`.

2. Run Cosmos DB hybrid search (split query into individual words for FullTextScore):
   ```sql
   SELECT TOP @topK
     c.id, c.blobUrl, c.ocrText, c.caption, c.templateName,
     c.tags, c.category, c.uploadedAt,
     VectorDistance(c.visualEmbedding, @queryVec) AS similarity
   FROM c
   WHERE (@category = null OR c.category = @category)
   ORDER BY RANK RRF(
     VectorDistance(c.visualEmbedding, @queryVec),
     FullTextScore(c.searchableText, @word1, @word2, @word3)
   )
   ```

3. Return results array sorted by relevance, each item including `id`, `blobUrl`, `caption`, `templateName`, `tags`, `similarity`.

---

### POST /search/image — search by uploaded image

**Request:** `multipart/form-data` with:
- `image` — the query image file
- `topK` (optional, default 10)
- `category` (optional filter)

**Processing:**

1. Call `vectorizeImage` on the uploaded bytes (same as ingestion step 3).
2. Run the same Cosmos DB `VectorDistance` query as above, but without `FullTextScore` (vector-only search).
3. Return results in the same format as text search.

---

### GET /memes/:id — get a single meme by ID

Return the full document for the given ID (excluding `visualEmbedding` to keep response size small).

### GET /memes — list memes

Support `?category=reaction&limit=20&offset=0` for paginated browsing. Simple `SELECT` query with `WHERE c.category = @category` and `OFFSET @offset LIMIT @limit`.

### DELETE /memes/:id — remove a meme

Delete the Cosmos DB document and the corresponding blob from storage.

---

## Frontend (optional, implement after API is working)

A simple single-page app with:

- A search bar at the top with a toggle for "text search" vs "image search"
- For image search: a drag-and-drop area that accepts an image file
- Results grid: each meme shown as a card with the image, template name, OCR text, and tags
- An upload section (accordion or separate page) with category selector
- Category filter buttons above the results grid

Technology: plain HTML + vanilla JS + CSS, or React if preferred. No framework requirement.

---

## Project structure

```
meme-db/
├── api/
│   ├── main.py               # FastAPI (or Express) entry point
│   ├── routes/
│   │   ├── ingest.py         # POST /memes
│   │   └── search.py         # POST /search/text, POST /search/image
│   ├── services/
│   │   ├── blob.py           # Azure Blob Storage client
│   │   ├── vision.py         # Azure AI Vision embedding calls
│   │   ├── openai_client.py  # GPT-4o metadata extraction
│   │   └── cosmos.py         # Cosmos DB client + queries
│   └── models.py             # Pydantic/dataclass schemas
├── frontend/
│   └── index.html            # Search UI
├── scripts/
│   └── setup_cosmos.py       # One-time DB + container + index creation
├── .env.example
├── requirements.txt          # or package.json
└── README.md
```

Preferred language: **Python** with FastAPI. If the developer prefers Node.js/TypeScript, use Express + the `@azure/cosmos` SDK.

---

## Python dependencies

```
fastapi
uvicorn
python-multipart
azure-cosmos
azure-storage-blob
openai
requests
python-dotenv
httpx
pydantic
```

---

## Implementation notes and gotchas

**Model version pinning is critical.** All calls to `vectorizeImage` and `vectorizeText` must use the same `model-version` parameter (use `2023-04-15`). Vectors from different model versions are not compatible. Store the model version in every Cosmos DB document so you know what to re-embed if the model ever changes.

**Azure AI Vision region availability.** The multimodal embeddings API is only available in: East US, France Central, Korea Central, North Europe, Southeast Asia, West Europe, West US. The Cosmos DB account and the Web App do not need to be in the same region as Vision, but co-locating everything in East US or West Europe simplifies networking and reduces latency.

**Cosmos DB full-text search word splitting.** The `FullTextScore` function takes individual word arguments, not a phrase. When building the Cosmos DB query dynamically, split the search query on whitespace and pass each word as a separate parameter. Maximum ~10 words is sufficient — truncate longer queries.

**Image size limits for Azure AI Vision.** Images must be between 10×10 and 16,000×16,000 pixels, and under 20MB. Validate and optionally resize before calling the API.

**Do not store `visualEmbedding` in GET response payloads.** The 1024-float array is large. Exclude it from all API responses — it's only needed inside Cosmos DB queries. Use `SELECT c.id, c.blobUrl, ... (no visualEmbedding)` in your projection.

**Deduplication via fileHash.** Before ingesting, query `SELECT c.id FROM c WHERE c.fileHash = @hash`. If a result comes back, skip ingestion and return the existing document. This prevents duplicate embeddings for the same image.

**SAS tokens vs public blob access.** For development, set the `memes` blob container to public read access — simplest approach. For production, keep blobs private and generate short-lived SAS URLs (15-minute expiry) server-side when returning search results. Never expose the storage account key to the frontend.

**Cosmos DB RU provisioning.** Start with 1000 RU/s (manual) or use serverless for development. DiskANN index build consumes RUs proportional to the number of vectors. For initial bulk ingestion of a large library, temporarily increase RU/s to avoid throttling, then scale back down.

**Vector index build is asynchronous.** After inserting documents, the DiskANN index is built in the background. New documents may not appear in vector search results immediately (typically within seconds to a few minutes for small batches). This is expected behavior — plan for eventual consistency in the index.

---

## First steps in Claude Code

1. Create the project directory structure above
2. Set up `.env` from `.env.example` with real values
3. Run `scripts/setup_cosmos.py` to create the database, container, and indexes
4. Implement `services/vision.py` first and test embedding generation in isolation
5. Implement `services/blob.py` and test image upload
6. Implement `services/openai_client.py` and test metadata extraction
7. Implement `services/cosmos.py` with write and hybrid-search query
8. Wire everything together in `routes/ingest.py` and `routes/search.py`
9. Implement the frontend last
10. Deploy to Azure App Service via `az webapp up` or GitHub Actions

---

## Validation checklist before deploying

- [ ] `POST /memes` returns `409` for a duplicate image (same file uploaded twice)
- [ ] `POST /memes` stores a document with all fields including a 1024-element `visualEmbedding` array
- [ ] `POST /search/text` with "surprised pikachu" returns visually relevant memes
- [ ] `POST /search/image` with a cropped version of a stored meme returns the original as top result
- [ ] `GET /memes/:id` response does **not** include `visualEmbedding`
- [ ] All Azure credentials are in environment variables, not hardcoded
- [ ] Blob container access and SAS URL generation work correctly
- [ ] Cosmos DB query correctly excludes `visualEmbedding` from the vector index exclusion path
