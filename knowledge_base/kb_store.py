"""
Простое хранилище базы знаний на основе OpenAI embeddings + numpy.
Не требует сторонних баз данных — всё хранится в одном JSON-файле.
"""

import json
import os
import hashlib
from pathlib import Path
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_FILE = Path(__file__).parent / "db" / "knowledge.json"


def _load_db() -> dict:
    if DB_FILE.exists():
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": [], "embeddings": [], "metadata": []}


def _save_db(db: dict):
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _embed(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        input=texts,
        model="text-embedding-3-small",
    )
    return [item.embedding for item in response.data]


def _doc_id(source: str, index: int) -> str:
    h = hashlib.md5(source.encode()).hexdigest()[:8]
    return f"{h}_{index}"


def add_chunks(chunks: list[str], source: str, source_type: str):
    db = _load_db()
    existing_ids = {m["id"] for m in db["metadata"]}

    new_chunks, new_metas = [], []
    for i, chunk in enumerate(chunks):
        did = _doc_id(source, i)
        if did not in existing_ids:
            new_chunks.append(chunk)
            new_metas.append({"id": did, "source": source, "type": source_type})

    if not new_chunks:
        print(f"  = «{source}» уже в базе, пропускаем")
        return

    # Считаем эмбеддинги батчами по 100
    all_embeddings = []
    for i in range(0, len(new_chunks), 100):
        batch = new_chunks[i:i+100]
        all_embeddings.extend(_embed(batch))

    db["chunks"].extend(new_chunks)
    db["embeddings"].extend(all_embeddings)
    db["metadata"].extend(new_metas)
    _save_db(db)
    print(f"  + добавлено {len(new_chunks)} фрагментов из «{source}»")


def search(query: str, n_results: int = 5) -> list[dict]:
    db = _load_db()
    if not db["chunks"]:
        return []

    query_emb = np.array(_embed([query])[0])
    embeddings = np.array(db["embeddings"])

    # Косинусное сходство
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_emb)
    norms = np.where(norms == 0, 1e-10, norms)
    scores = embeddings @ query_emb / norms

    top_indices = np.argsort(scores)[::-1][:n_results]
    results = []
    for idx in top_indices:
        results.append({
            "text": db["chunks"][idx],
            "source": db["metadata"][idx]["source"],
            "score": float(scores[idx]),
        })
    return results


def count() -> int:
    return len(_load_db()["chunks"])
