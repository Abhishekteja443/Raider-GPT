import json
import math
import os
import re
import threading

import ollama
from sqlalchemy import text

from src import logger

# ---------------------------------------------------------------- config
KG_PATH = r"C:\Users\gabhi\Projects\RaiderGPT\KG_RAG\Opus5.5\query_results.json"
EMBED_MODEL = "nomic-embed-text"   # run once: ollama pull nomic-embed-text
MATCH_THRESHOLD = 0.72             # tune by printing scores on real queries
MAX_KG_CHARS = 8000                # ~2000 tokens (CQ11 alone is ~14.5k chars)

# ---------------------------------------------------------------- state
_cqs = []
_vecs = []
_loaded = False
_lock = threading.Lock()

_STOP = {
    "the", "and", "for", "are", "what", "which", "who", "how", "does", "that",
    "this", "with", "from", "have", "has", "was", "were", "can", "about",
    "give", "show", "tell", "list", "all", "any", "under", "into", "their",
}


def _embed(text: str):
    return ollama.embeddings(model=EMBED_MODEL, prompt=text)["embedding"]


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _STOP}


def _load():
    """Load the KG file once and embed each non-empty CQ question."""
    global _cqs, _vecs, _loaded
    with _lock:
        if _loaded:
            return
        with open(KG_PATH, encoding="utf-8") as f:
            data = json.load(f)

        cqs, vecs = [], []
        for cq in data:
            if cq.get("count", 0) > 0 and cq.get("bindings"):  # skip empty CQs
                cqs.append(cq)
                vecs.append(_embed(cq["question"]))

        _cqs, _vecs, _loaded = cqs, vecs, True
        logger.info(f"KG loaded: {len(_cqs)} non-empty CQs from {KG_PATH}")


def _format_cq(cq: dict, query: str) -> str:
    """Compact 'var: value | var: value' rows. If too large, keep the rows
    most relevant to the user's query (original order preserved)."""
    variables = cq["variables"]
    rows = [
        " | ".join(f"{v}: {r[v]['value']}" for v in variables if v in r)
        for r in cq["bindings"]
    ]
    total = len(rows)
    text = "\n".join(rows)

    note = ""
    if len(text) > MAX_KG_CHARS:
        q_tokens = _tokens(query)
        ranked = sorted(range(total),
                        key=lambda i: -len(q_tokens & _tokens(rows[i])))
        keep, used = set(), 0
        for i in ranked:
            cost = len(rows[i]) + 1
            if used + cost > MAX_KG_CHARS:
                continue
            keep.add(i)
            used += cost
        rows = [rows[i] for i in sorted(keep)]
        text = "\n".join(rows)
        note = "" 

    return f"{text}{note}"


def retrieve_kg_context(query: str):
    """Return (formatted_text, cq_id), or ("", None) if no CQ matches."""
    try:
        _load()
        if not _cqs:
            return "", None

        q_vec = _embed(query)
        scores = [_cosine(q_vec, v) for v in _vecs]
        best = max(range(len(scores)), key=scores.__getitem__)

        if scores[best] < MATCH_THRESHOLD:
            logger.info(f"KG: no match (best={scores[best]:.2f})")
            return "", None

        cq = _cqs[best]
        logger.info(f"KG match {cq['id']} (score={scores[best]:.2f})")
        return _format_cq(cq, query), cq["id"]
    except Exception as e:
        logger.error(f"KG lookup error: {e}", exc_info=True)
        return "", None