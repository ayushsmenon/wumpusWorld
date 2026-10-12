## Knowledge embeddings

Knowledge indexing uses local Sentence Transformers embeddings by default:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model produces 384-dimensional vectors, matching the `VECTOR(384)` column
in `backend/database/schema.sql`. Download the model once during setup, then
keep `EMBEDDING_LOCAL_FILES_ONLY=true` for normal offline inference. If the
model is not present in the local cache, the Knowledge module raises an
explicit error; it never falls back to a paid provider.

One-time setup, with internet access:

```powershell
pip install -r requirements.txt
python scripts/download_embedding_model.py
```

After the model is cached, normal indexing and querying do not contact the
model hub. Do not run the setup command in an offline environment until the
model cache has been populated.

Required configuration is documented in `.env.example`. OpenAI remains
available only when `EMBEDDING_PROVIDER=openai` is selected explicitly.
PostgreSQL is still required for persistent vector storage, and any tutor
model or other hosted application service may still require internet access.

The schema change is for fresh databases only. Existing databases containing
1536-dimensional vectors must not be altered or reindexed automatically.