import os

os.environ["HF_HOME"] = os.getenv("HF_HOME", "D:/wumpus_cache")

from sentence_transformers import SentenceTransformer

model_name = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
cache_folder = os.getenv("EMBEDDING_CACHE_DIR") or None
try:
    SentenceTransformer(model_name, cache_folder=cache_folder, local_files_only=False, device="cpu")
except Exception as exc:
    raise SystemExit(
        f"Could not download or load '{model_name}'. "
        "Run this setup command with internet access, then retry."
    ) from exc
print(f"Downloaded or verified local embedding model: {model_name}")
