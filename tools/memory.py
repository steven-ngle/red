import atexit
import logging
import os
import warnings

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

from pathlib import Path as _Path
import config as _config

_model_cache_dir = "models--" + _config.EMBEDDING_MODEL.replace("/", "--")
if (_Path.home() / ".cache" / "huggingface" / "hub" / _model_cache_dir).exists():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("MEM0_TELEMETRY", "False")

logging.getLogger("mem0").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=FutureWarning, module="mem0")

from mem0 import Memory

import config
from ui import warn

_memory = None


def _mem(): #lazy
    global _memory
    if _memory is None:
        _memory = Memory.from_config(config.MEM0_CONFIG)
    return _memory


def _close():
    if _memory is not None:
        try:
            _memory.vector_store.client.close()
        except Exception:
            pass


atexit.register(_close)


def get_relevant(query, user_id, limit=8):
    try:
        hits = _mem().search(query=query, filters={"user_id": user_id}, top_k=limit)
    except Exception as e:
        warn(f"Mem0 Suche fehlgeschlagen, fahre ohne Gedächtnis fort: {e}")
        return []
    return [h["memory"] for h in hits.get("results", []) if h.get("memory")]


def add_memory(question, report, user_id):
    messages = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": report},
    ]
    try:
        result = _mem().add(messages, user_id=user_id)
    except Exception as e:
        warn(f"Mem0 Schreiben fehlgeschlagen: {e}")
        return []
    return [
        f"[{r.get('event', '?')}] {r.get('memory', '')}"
        for r in result.get("results", [])
        if r.get("memory")
    ]


def get_all(user_id):
    try:
        hits = _mem().get_all(filters={"user_id": user_id}, top_k=100)
    except Exception as e:
        warn(f"Mem0 get_all fehlgeschlagen: {e}")
        return []
    return [h["memory"] for h in hits.get("results", []) if h.get("memory")]
