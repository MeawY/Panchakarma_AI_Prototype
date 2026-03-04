import argparse
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
import chromadb

DEF_INPUT = Path("data/panchakarma_facts.md")
DEF_DB = Path(".chroma")
DEF_COLLECTION = "panchakarma_qa_openai"  # same collection to enable cross-search
DEF_MODEL = "text-embedding-3-small"


def parse_facts_table(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines = [ln for ln in lines if ln.strip().startswith("|") and ln.strip().endswith("|")]
    if len(table_lines) < 3:
        raise SystemExit(f"Not enough table rows in {path}")
    headers = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
    rows = []
    for ln in table_lines[2:]:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        # pad to headers len
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        rows.append(cells)
    return headers, rows


def build_doc(headers: List[str], cells: List[str]) -> str:
    parts = []
    for h, v in zip(headers, cells):
        if v:
            parts.append(f"{h}: {v}")
    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser(description="Register facts table into Chroma (OpenAI embeddings)")
    p.add_argument("--input", "-i", default=str(DEF_INPUT))
    p.add_argument("--db", default=str(DEF_DB))
    p.add_argument("--collection", "-c", default=DEF_COLLECTION)
    p.add_argument("--model", "-m", default=DEF_MODEL)
    p.add_argument("--base", default=os.getenv("OPENAI_BASE_URL", ""))
    args = p.parse_args()

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=api_key, base_url=(args.base or None))

    headers, rows = parse_facts_table(Path(args.input))

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []
    for idx, cells in enumerate(rows, start=1):
        ids.append(f"facts-{idx}")
        docs.append(build_doc(headers, cells))
        metas.append({"type": "facts"})

    # Embed in batches
    embeddings: List[List[float]] = []
    batch = 128
    for i in range(0, len(docs), batch):
        chunk = docs[i:i+batch]
        resp = client.embeddings.create(model=args.model, input=chunk)
        embeddings.extend([d.embedding for d in resp.data])

    chroma = chromadb.PersistentClient(path=str(Path(args.db)))
    coll = chroma.get_or_create_collection(args.collection)

    # delete existing fact ids for upsert
    try:
        coll.delete(ids=ids)
    except Exception:
        pass

    coll.add(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
    print(f"✅ Facts 登録完了(OpenAI): {coll.count()} items -> {args.collection}")


if __name__ == "__main__":
    main()




