import argparse
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


def main():
    p = argparse.ArgumentParser(description="Query ChromaDB collection")
    p.add_argument("--q", required=True, help="query text")
    p.add_argument("--k", type=int, default=3, help="top-k")
    p.add_argument("--db", default=str(Path(".chroma")), help="chroma persistent dir")
    p.add_argument("--collection", default="panchakarma_qa", help="collection name")
    p.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model")
    args = p.parse_args()

    client = chromadb.PersistentClient(path=args.db)
    coll = client.get_or_create_collection(args.collection)

    model = SentenceTransformer(args.model)
    q_vec = model.encode(args.q).tolist()

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





