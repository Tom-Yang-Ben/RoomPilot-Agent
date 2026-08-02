# RoomPilot Official Catalog and Vector Handoff

This directory contains Kai's portable handoff for the official 8,675-item
furniture catalog and matching asset manifests, plus the RAG metadata and
vector delivery maintained by Django.

## Official Files

| Path | Rows | Purpose |
|---|---:|---|
| `furniture/furniture_official_catagory.json` | 8,675 | Official furniture identity, dimensions, product URLs, six-style/VLM annotations and RAG metadata |
| `manifests/glb_upload_manifest.csv` | 8,675 | GLB upload manifest keyed by `item_id` |
| `manifests/glb_upload_all_result.csv` | 8,675 | Verified S3/CloudFront GLB upload results |
| `manifests/image_upload_manifest.csv` | 26,025 | Front, side and 45-degree product-image upload manifest |
| `manifests/image_upload_all_result.csv` | 26,025 | Verified S3/CloudFront product-image upload results |
| `RAG/furniture_embeddings_bge_m3.jsonl` | 8,076 | BGE-M3 vectors generated and delivered by Django for database persistence |

The spelling of `furniture_official_catagory.json` follows the delivered source
filename. Its 8,675 unique IDs must exactly match both GLB files and the 8,675
item IDs represented by the image files. Every official item has one `front`,
one `side`, and one `angle-45` image.

The JSON includes raw VLM enrichment such as `style_primary`,
`style_secondary`, `description`, `room_types`, `shape_tags`, `features`,
`search_keywords`, and `rag_text`. These annotations enrich retrieval; they do
not replace the validated six-style mapping or furniture-engine legality.
All 8,675 catalog items carry VLM/RAG description fields, so general catalog
metadata coverage uses the full 8,675-item count. The separate 8,076 figure is
the current active, `rag_indexable` BGE-M3 vector set; the remaining 599 items
stay outside the official API and vector RAG pending review.

## RAG Ownership Boundary

- Django owns RAG metadata and text, vector generation, retrieval, and quality.
- Kai's only RAG responsibility is persisting Django's delivered vectors to
  PostgreSQL/pgvector. Catalog and asset maintenance remain Kai's separate data
  responsibility.
- RAG supplies retrieval evidence only; furniture placement legality remains in
  `backend/engine/`.

`original_glb_path` and `original_image_path` are producer-relative provenance,
not repository runtime paths. Do not replace them with machine-specific
absolute paths. Runtime delivery uses the verified `object_key` and HTTPS
`delivery_url`. Large GLB and product-image assets remain outside Git.

## Legacy Data Policy

The legacy 10,550-item and 9,349-item payloads are not retained in this project.
The legacy PostgreSQL importer has also been removed from `scripts/sql/`.
Appliances are not part of the current product; legacy rows must not enter the
API, Agent, official furniture set, database, or scene. Validate the current
8,675-item official set with:

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all `
  --dry-run
```
