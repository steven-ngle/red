import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

MODEL_THINKING = "deepseek-v4-flash"
MODEL_FAST = "deepseek-v4-flash"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_MAX_RESULTS = 5

MAX_SUBQUESTIONS = 3
MAX_ROUNDS = 5

QDRANT_PATH = str(Path(__file__).parent / "qdrant_data")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMS = 384

MEM0_CONFIG = {
    "llm": {
        "provider": "deepseek",
        "config": {
            "model": MODEL_FAST,
            "api_key": DEEPSEEK_API_KEY,
            "deepseek_base_url": DEEPSEEK_BASE_URL,
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {"model": EMBEDDING_MODEL},
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "research_agent_memory",
            "path": QDRANT_PATH,
            "embedding_model_dims": EMBEDDING_DIMS,
        },
    },
}


def check_env():
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    return missing
