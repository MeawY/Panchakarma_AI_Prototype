import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import chromadb


def main():
    p = argparse.ArgumentParser(description="Query ChromaDB with OpenAI embeddings")
    p.add_argument("--q", required=True, help="query text")
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--db", default=str(Path(".chroma")))
    p.add_argument("--collection", default="panchakarma_qa_openai")
    p.add_argument("--model", default="text-embedding-3-small")
    p.add_argument("--base", default=os.getenv("OPENAI_BASE_URL", ""))
    args = p.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=api_key, base_url=(args.base or None))

    # Embed query
    resp = client.embeddings.create(model=args.model, input=[args.q])
    q_vec = resp.data[0].embedding

    coll = chromadb.PersistentClient(path=args.db).get_or_create_collection(args.collection)
    res = coll.query(query_embeddings=[q_vec], n_results=args.k, include=["documents", "metadatas", "distances"])  # type: ignore

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), start=1):
        print(f"#{i} distance={dist:.4f}")
        print(doc)
        print(meta)
        print("----")


if __name__ == "__main__":
    main()





