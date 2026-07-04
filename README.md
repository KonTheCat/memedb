# memedb

Console app that ingests meme images and makes them searchable. Ingestion
uploads each image to Blob Storage, generates a 1024-dim visual embedding
(Azure AI Vision), extracts OCR text/caption/tags (Azure OpenAI), and stores a
document in Cosmos DB (vector + full-text indexed). Search supports both a
text query and a query-by-example image, using Cosmos DB hybrid search (RRF
of vector similarity + BM25 full-text) or pure vector similarity.

See `docs/MEME_DB_CLAUDE_CODE.md` for the full application spec this project
is being built from.

## 1. Provision infrastructure

Requires: Azure CLI logged in (`az login`), [OpenTofu](https://opentofu.org/)
(`tofu`), resource group `memedb` already created.

```powershell
# One-time: bootstrap the storage account that holds tofu's remote state
./infra/bootstrap/init.ps1

cd infra
tofu init -backend-config=backend.hcl
tofu plan
tofu apply
```

This creates, all inside the `memedb` resource group:

- A Storage Account + `memes` blob container (East US 2) for raw images
- A serverless Cosmos DB account/database/container with vector search
  (DiskANN) and full-text search enabled (East US 2)
- An Azure AI Vision (Computer Vision) resource for multimodal embeddings
  (East US — required, Vision isn't available in East US 2)
- An Azure OpenAI resource with a `gpt-5.1` deployment (East US 2)

## 2. Generate `.env`

```powershell
python scripts/write_env.py
```

Reads `tofu output -json` and writes a repo-root `.env` with all the
credentials/endpoints the app needs (see `.env.example` for the shape).

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

## 4. Ingest memes

```powershell
# single file
python -m memedb ingest sample_input_data/aLv8oXx_460swp.webp --category other

# a whole directory (all images share the given category)
python -m memedb ingest sample_input_data --category other
```

Each image is deduplicated by SHA-256 — re-ingesting the same file is a no-op
and reports the existing document ID instead of creating a duplicate.

Valid `--category` values: `reaction`, `advice-animal`, `surreal`,
`political`, `wholesome`, `dark`, `meta`, `other`.

## 5. Search memes

```powershell
# text query — hybrid search (vector similarity + BM25 full-text via RRF)
python -m memedb search-text "surprised pikachu face" --top-k 10 --category reaction

# query by example image — pure vector similarity
python -m memedb search-image path/to/query.jpg --top-k 10
```

`--category` is optional on both and filters results to a single category.
Results are printed ranked by relevance, each showing id, category,
similarity score, caption, template name, tags, and blob URL.
