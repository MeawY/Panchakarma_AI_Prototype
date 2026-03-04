import argparse
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from sentence_transformers.util import batch_to_device  # not used, but keeps s-transformers optional

DEF_INPUT = Path("data/panchakarma_qa_pairs_tagged.md")
DEF_DB = Path(".chroma")
DEF_COLLECTION = "panchakarma_qa_openai"
DEF_MODEL = "text-embedding-3-small"  # or text-embedding-3-large


def parse_markdown(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines = [ln for ln in lines if ln.strip().startswith("|") and ln.strip().endswith("|")]
    if len(table_lines) < 3:
        raise SystemExit(f"Not enough table rows in {path}")
    rows = []
    for ln in table_lines[2:]:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 5:
            cells += [""] * (5 - len(cells))
        no, q, a, s, tag = cells[:5]
        rows.append((no, q, a, s, tag))
    return rows


def main():
    p = argparse.ArgumentParser(description="Register QA to Chroma using OpenAI embeddings")
    p.add_argument("--input", "-i", default=str(DEF_INPUT))
    p.add_argument("--db", default=str(DEF_DB))
    p.add_argument("--collection", "-c", default=DEF_COLLECTION)
    p.add_argument("--model", "-m", default=DEF_MODEL)
    p.add_argument("--base", default=os.getenv("OPENAI_BASE_URL", ""), help="Custom base URL (e.g., Azure)")
    args = p.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=api_key, base_url=(args.base or None))

    rows = parse_markdown(Path(args.input))

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []
    for no, q, a, s, tag in rows:
        ids.append(str(no))
        docs.append(f"Q: {q}\nA: {a}")
        metas.append({"source": s, "+tags": tag, "model": args.model})

    # Embed in small batches
    embeddings: List[List[float]] = []
    batch_size = 128
    for i in range(0, len(docs), batch_size):
        chunk = docs[i:i+batch_size]
        resp = client.embeddings.create(model=args.model, input=chunk)
        embeddings.extend([d.embedding for d in resp.data])

    # Upsert into Chroma
    client_chroma = chromadb.PersistentClient(path=str(Path(args.db)))
    coll = client_chroma.get_or_create_collection(args.collection)

    # delete existing ids to upsert
    try:
        coll.delete(ids=ids)
    except Exception:
        pass

    coll.add(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
    print(f"✅ 登録完了(OpenAI): {coll.count()} items -> {args.collection}")


if __name__ == "__main__":
    main()





