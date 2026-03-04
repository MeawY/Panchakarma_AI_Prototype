import argparse
import os
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI
import chromadb


def get_topk(query: str, k: int, db_path: str, collection: str, embed_model: str, base_url: str | None):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)
    emb = client.embeddings.create(model=embed_model, input=[query]).data[0].embedding
    coll = chromadb.PersistentClient(path=db_path).get_or_create_collection(collection)
    res = coll.query(query_embeddings=[emb], n_results=k, include=["documents", "metadatas", "distances"])  # type: ignore
    docs: List[str] = res.get("documents", [[]])[0]
    metas: List[Dict] = res.get("metadatas", [[]])[0]
    return docs, metas


def generate_summary(client: OpenAI, chat_model: str, query: str, docs: List[str], metas: List[Dict]) -> str:
    ctx_blocks = []
    for i, (d, m) in enumerate(zip(docs, metas), start=1):
        ctx_blocks.append(f"[DOC {i}]\n{d}\nMETA: {m}\n")
    context = "\n\n".join(ctx_blocks)

    system = (
        "あなたはアーユルヴェーダの臨床家向けアシスタントです。"
        "根拠は与えられたコンテキストのみを使用し、安全性と禁忌を優先します。"
    )
    user = f"""
質問: {query}

コンテキスト: 
{context}

出力要件:
- 専門×やさしさトーンで、要点を日本語で簡潔にまとめる（5〜8行程度）
- 必要な場合は禁忌/注意も含める
"""
    msg = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return msg.choices[0].message.content or ""


def uniq(seq: List[str]) -> List[str]:
    out: List[str] = []
    for s in seq:
        if s and s not in out:
            out.append(s)
    return out


def main():
    p = argparse.ArgumentParser(description="RAG answer with fixed template (JA)")
    p.add_argument("--q", required=True, help="user query")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--db", default=str(Path(".chroma")))
    p.add_argument("--collection", default="panchakarma_qa_openai")
    p.add_argument("--embed_model", default="text-embedding-3-small")
    p.add_argument("--chat_model", default="gpt-4o-mini")
    p.add_argument("--base", default=os.getenv("OPENAI_BASE_URL", ""))
    args = p.parse_args()

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set in .env")

    docs, metas = get_topk(
        query=args.q,
        k=args.k,
        db_path=args.db,
        collection=args.collection,
        embed_model=args.embed_model,
        base_url=(args.base or None),
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=(args.base or None))
    summary = generate_summary(client, args.chat_model, args.q, docs, metas)

    sources = uniq([str(m.get("source", "")).strip() for m in metas if str(m.get("source", "")).strip()])
    tags = uniq([str(m.get("+tags", "")).strip() for m in metas if str(m.get("+tags", "")).strip()])

    # Template output
    print(f"🩺 質問: {args.q}\n")
    print("🧠 回答（専門×やさしさトーン）\n")
    print(summary.strip())
    print("\n\n📚 根拠・出典:\n")
    if sources:
        for s in sources:
            print(f"- {s}")
    else:
        print("- 参照なし")
    print("\n\n🏷️ 関連タグ:\n")
    if tags:
        for t in tags:
            print(f"- {t}")
    else:
        print("- なし")
    print("\n\n💬 補足コメント（任意）\n")
    print("必要に応じて主治医に相談し、患者の体力・消化力・禁忌を再確認してください。")


if __name__ == "__main__":
    main()


