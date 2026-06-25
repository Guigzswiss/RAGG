from pathlib import Path

# ── Infomaniak AI ─────────────────────────────────────────────────────────────
_TOKEN_FILE = Path(__file__).resolve().parent / "token.txt"

def _load_token() -> str:
    if not _TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"token.txt introuvable dans {_TOKEN_FILE.parent}. "
            "Crée ce fichier et colle ton token Infomaniak dedans."
        )
    token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("token.txt est vide.")
    return token

INFOMANIAK_TOKEN: str = _load_token()
INFOMANIAK_BASE_URL: str = "https://api.infomaniak.com/2/ai/108639/openai/v1"
MODEL_CHAT: str = "google/gemma-4-31B-it"
MODEL_EMBED: str = "Qwen/Qwen3-Embedding-8B"

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_DIR: str = "./data/chroma"
COLLECTION_NAME: str = "swiss_law"

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K_DENSE: int = 15
TOP_K_BM25: int = 15
TOP_K_FINAL: int = 12
RRF_K: int = 60

# ── Fedlex ────────────────────────────────────────────────────────────────────
FEDLEX_SPARQL: str = "https://fedlex.data.admin.ch/sparqlendpoint"
