#!/usr/bin/env python3
"""
ChromaDB の panchakarma_qa_openai コレクションを Neon (pgvector) に移行します。
事前に schema.sql を Neon で実行し、.env.local に DATABASE_URL を設定してください。

使い方（プロジェクトルートで）:
  python scripts/migrate-chroma-to-neon.py

または Chroma の .chroma パスを環境変数で指定:
  CHROMA_PATH=/path/to/.chroma python scripts/migrate-chroma-to-neon.py
"""
import os
import json
from pathlib import Path

try:
    import chromadb
except ImportError:
    print("chromadb が必要です: pip install chromadb")
    raise

try:
    import psycopg
except ImportError:
    print("psycopg が必要です: pip install 'psycopg[binary]'")
    raise

def load_dotenv_local():
    # プロジェクトルートの .env.local
    env_path = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

def main():
    load_dotenv_local()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL が未設定です。.env.local に Neon の接続文字列を設定してください。")
        return 1

    chroma_path = os.environ.get("CHROMA_PATH")
    if not chroma_path:
        chroma_path = str(Path(__file__).resolve().parent.parent / ".chroma")
    if not Path(chroma_path).exists():
        print(f"Chroma パスが存在しません: {chroma_path}")
        return 1

    client = chromadb.PersistentClient(path=chroma_path)
    coll = client.get_or_create_collection("panchakarma_qa_openai")
    data = coll.get(include=["documents", "metadatas", "embeddings"])
    ids = data.get("ids") or []
    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []
    embeddings = data.get("embeddings") or []

    if not ids:
        print("Chroma にドキュメントがありません。")
        return 0

    print(f"移行対象: {len(ids)} 件")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            inserted = 0
            for i, (doc_id, content, meta, emb) in enumerate(
                zip(ids, documents, metadatas, embeddings)
            ):
                if not content or not emb:
                    continue
                meta_json = json.dumps(meta or {}, ensure_ascii=False)
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                cur.execute(
                    """
                    INSERT INTO panchakarma_docs (content, metadata, embedding)
                    VALUES (%s, %s::jsonb, %s::vector)
                    """,
                    (content, meta_json, emb_str),
                )
                inserted += 1
            conn.commit()
    print(f"Neon に {inserted} 件を挿入しました。")
    return 0

if __name__ == "__main__":
    exit(main())
