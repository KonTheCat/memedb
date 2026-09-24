# memedb

Web app (FastAPI backend + Next.js frontend, plus a CLI) that ingests meme
images and makes them searchable. Ingestion uploads each image to Blob
Storage, generates a 1024-dim visual embedding (Azure AI Vision), extracts
OCR text/caption/tags (Azure OpenAI), and stores a document in Cosmos DB
(vector + full-text indexed). Search supports both a text query and a
query-by-example image, using Cosmos DB hybrid search (RRF of vector
similarity + BM25 full-text) or pure vector similarity.

See `docs/MEME_DB_CLAUDE_CODE.md` for the full application spec this project
is being built from.

## 1. Provision infrastructure

Requires: Azure CLI logged in (`az login`), [OpenTofu](https://opentofu.org/)
(`tofu`), and the target resource group already created — `memedb` for prod,
`dev-memedb` for the dev environment.

The same OpenTofu config deploys both environments; which one you get is
controlled by `-var-file` (resource group + naming) and `-backend-config`
(state file). Prod and dev are otherwise identical, and safe to run side by
side — every resource name includes the environment, so nothing collides.

```powershell
# One-time: bootstrap the storage account that holds tofu's remote state,
# and write infra/envs/<environment>.backend.hcl. The state storage account
# itself lives in the `memedb` resource group for both environments.
./infra/bootstrap/init.ps1                    # prod (default)
./infra/bootstrap/init.ps1 -Environment dev   # dev

cd infra
tofu init -backend-config=envs/prod.backend.hcl -reconfigure
tofu plan -var-file=envs/prod.tfvars
tofu apply -var-file=envs/prod.tfvars
```

Swap `prod` for `dev` in all three commands to work against the dev
environment instead. `tofu init -reconfigure` is what switches which state
file a given `infra/` checkout is pointed at — run it whenever you switch
environments in the same shell/checkout.

`entra_tenant_id`, `entra_tenant_subdomain`, and `entra_client_id` are required
variables with no default, set after creating the Entra External ID tenant
and SPA app registration manually in the Entra admin center (see "Auth"
below) — pass them via `-var` or a `*.tfvars` file (not secrets, safe to
commit).

This creates, inside the target resource group:

- A Storage Account + `memes` blob container (East US 2) for raw images
- A serverless Cosmos DB account/database/container with vector search
  (DiskANN) and full-text search enabled (East US 2)
- An Azure AI Vision (Computer Vision) resource for multimodal embeddings
  (East US — required, Vision isn't available in East US 2)
- An Azure OpenAI resource with a `gpt-5.1` deployment (East US 2)
- A Linux App Service (Python) running the API, and a Linux App Service
  (Node) running the frontend — see "Deploying the web app" below

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

## 6. Run the API

```powershell
uvicorn memedb.api.app:app --reload
```

Interactive docs at `http://127.0.0.1:8000/docs`. Endpoints:

| Endpoint | Description |
|---|---|
| `POST /memes` | multipart: `image`, `category`, `templateName?`, `sourceUrl?` — 201 with `{id, blobUrl}`, or 409 with the existing id on duplicate |
| `GET /memes/{id}` | full document, excluding `visualEmbedding` — 404 if not found |
| `GET /memes/{id}/image` | streams the meme's image bytes through the API (the `memes` blob container is private, so the frontend loads images through this proxy instead of `blobUrl` directly) |
| `GET /memes?category=&limit=20&offset=0` | paginated listing, excluding `visualEmbedding` |
| `GET /memes/count?category=` | `{count}` — total number of memes (optionally filtered by category), used by the frontend to show total page count |
| `PATCH /memes/{id}` | JSON body with any of `category`, `templateName`, `caption`, `ocrText`, `tags`, `sourceUrl` — updates only the given fields (recomputing `searchableText`) and returns the updated document; 404 if not found |
| `DELETE /memes/{id}` | deletes the Cosmos DB document and the blob — 204, or 404 if not found |
| `POST /search/text` | JSON body `{query, topK?, category?}` — hybrid search |
| `POST /search/image` | multipart: `image`, `topK?`, `category?` — vector-only search |
| `POST /memes/{id}/view` | 204, increments the meme's view count |

### Auth

Browsing and searching (`GET`/`POST` routes above other than upload/edit/
delete) require no authentication at all. `POST /memes`, `PATCH /memes/{id}`,
and `DELETE /memes/{id}` require a bearer token from Entra External ID
(CIAM) whose `roles` claim includes `Admin`:

1. Create an External (customer) tenant in the Entra admin center, register
   a SPA app (redirect URI matching the deployed origin), add a sign-up/
   sign-in user flow, and add an `Admin` app role assigned to your own
   account.
2. Set `ENTRA_TENANT_ID`/`ENTRA_TENANT_SUBDOMAIN`/`ENTRA_CLIENT_ID` for the
   backend (in `.env` locally, or the Terraform variables above for prod)
   and `NEXT_PUBLIC_ENTRA_CLIENT_ID`/`NEXT_PUBLIC_ENTRA_AUTHORITY` for the
   frontend build (`frontend/.env.local` locally; passed as Docker build
   args in CI — see `.github/workflows/deploy.yml`).

The frontend uses `@azure/msal-browser`/`@azure/msal-react` to sign in and
attach the resulting access token as `Authorization: Bearer <token>` on
upload/edit/delete requests only.

CORS is enabled for `http://localhost:3000` (the frontend's dev origin).

The CLI (`python -m memedb ...`) and the API share the same underlying
pipeline (`memedb/pipeline.py`) and services, so both stay in sync.

## 7. Run the frontend

A Next.js (TypeScript, App Router) single-page app in `frontend/`: a search
bar with a text/image toggle, drag-and-drop image search, a results grid
(image, template name, OCR text/caption, tags), category filter buttons, and
an upload accordion with a category selector.

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. It talks to the API at the URL in
`frontend/.env.local` (`NEXT_PUBLIC_API_BASE_URL`, defaults to
`http://127.0.0.1:8000`) — make sure the API (step 6) is running first.

## 8. Deploying the web app

Step 1's `tofu apply` provisions two Linux App Services per environment:
one running the API (Python 3.11, `gunicorn` + `uvicorn` workers) and one
running the frontend (Node 20, `next start`). Both build from source on
deploy (Oryx), so no Docker images or registry are involved. Relevant
`tofu output`s: `api_url`, `api_app_name`, `frontend_url`, `frontend_app_name`.

The API's `ALLOWED_ORIGINS` app setting and the frontend's
`NEXT_PUBLIC_API_BASE_URL` app setting are wired to each other's deployed URL
automatically, so the two only need pointing at real Azure resources, not at
each other, by hand.

### Manual deploy

```powershell
# API - zip memedb/ + requirements.txt, deploy to the API app
Compress-Archive -Path memedb, requirements.txt -DestinationPath api.zip -Force
az webapp deploy --resource-group <rg> --name <api_app_name> --src-path api.zip --type zip

# Frontend - zip the frontend/ source (excluding node_modules/.next), deploy to the web app
Compress-Archive -Path frontend\* -DestinationPath frontend.zip -Force -Exclude node_modules,.next
az webapp deploy --resource-group <rg> --name <frontend_app_name> --src-path frontend.zip --type zip
```

### GitHub Actions

`.github/workflows/deploy.yml` does the same thing on every push: pushing to
`main` deploys `prod`, pushing to any other branch deploys `dev`. Manual
dispatch (choose `dev` or `prod`) is also available. It finds each
environment's API/frontend app by resource-group + tag rather than a
hardcoded name, so it doesn't need updating when `tofu apply` is rerun.

One-time setup, once GitHub Environments named `dev` and `prod` exist in the
repo (Settings → Environments):

```powershell
./infra/bootstrap/setup-github-oidc.ps1 -GitHubRepo "yourorg/memedb"
```

This creates an Azure AD app registration federated to this repo's `dev` and
`prod` GitHub Environments (OIDC — no Azure secret is stored in GitHub) and
grants it Contributor on each environment's resource group, then prints the
`gh secret set` / `gh variable set` commands to finish wiring it up. Since
every push to `main` now deploys prod automatically, consider adding a
required-reviewer rule on the `prod` GitHub Environment so those deploys
(and manual dispatches to prod) pause for approval before running.
