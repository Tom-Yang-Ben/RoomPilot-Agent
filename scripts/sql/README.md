# PostgreSQL development boundary

The public full profile starts from the generic schema in `docker_postgresql/init/001_roompilot.sql`. It intentionally contains no catalog rows, product assets, embeddings or dump.

```powershell
Copy-Item .env.example .env
# set ROOMPILOT_PROFILE=full and DB_PASSWORD
docker compose --env-file .env -f docker_postgresql/docker-compose.yml up -d
```

Each developer-supplied furniture row must include a stable `item_id`, positive centimeter dimensions, `source_license` and activation state. URLs are optional and remain the data provider's licensing, CORS, availability and retention responsibility.

Files whose names contain `official_catalog`, `embeddings`, or an earlier PostgreSQL phase document a private migration pipeline whose source files are not public. They are not executable public setup instructions and have no fixed public record-count contract. New public ingestion work should target the generic schema, provide a dry-run, use transactions/UPSERT, and include a disposable PostgreSQL integration test.
