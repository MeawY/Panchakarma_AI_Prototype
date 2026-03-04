import argparse
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
import chromadb


def get_topk_openai(query: str, k: int, db_path: str, collection: str, embed_model: str, base_url: str | None) -> tuple[list[str], list[dict]]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)
    # embed query
    emb = client.embeddings.create(model=embed_model, input=[query]).data[0].embedding
    # query chroma
    coll = chromadb.PersistentClient(path=db_path).get_or_create_collection(collection)
    res = coll.query(query_embeddings=[emb], n_results=k, include=["documents", "metadatas", "distances"])  # type: ignore
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return docs, metas


def summarize_for_practitioner(openai_client: OpenAI, docs: List[str], metas: List[dict], chat_model: str, query: str) -> str:
    context_blocks = []
    for i, (d, m) in enumerate(zip(docs, metas), start=1):
        context_blocks.append(f"[DOC {i}]\n{d}\nMETA: {m}\n")
    context = "\n\n".join(context_blocks)

    system = (
        "あなたはアーユルヴェーダの臨床家向けアシスタントです。"
        "安全性・禁忌を最優先し、手順は簡潔に、判断基準は明確に示してください。"
    )
    user = f"""
<質問>
{query}

<コンテキスト（上位ヒット）>
{context}

<出力フォーマット（日本語、箇条書き中心）>
- 目的/臨床意図:
- フェーズ分類:（#前処置/#中心処置/#後処置）
- 推奨介入:（具体手順 3–6項目）
- 禁忌・注意:（必ず記載）
- ドーシャ関連:（#ヴァータ/#ピッタ/#カパ 該当あれば）
- 参考（出典/タグ）:（ META の source と +tags を列挙 ）

制約:
- コンテキストから根拠が取れない内容は推測せず「不明」と書く。
- 数字・用量は根拠がある場合のみ。
"""
    msg = openai_client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return msg.choices[0].message.content or ""


def main():
    p = argparse.ArgumentParser(description="Practitioner-facing RAG answer (JA)")
    p.add_argument("--q", required=True, help="query text")
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

    docs, metas = get_topk_openai(
        query=args.q,
        k=args.k,
        db_path=args.db,
        collection=args.collection,
        embed_model=args.embed_model,
        base_url=(args.base or None),
    )

    if not docs:
        print("該当なし（コレクション/クエリを確認してください）")
        return

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=(args.base or None))
    answer = summarize_for_practitioner(client, docs, metas, args.chat_model, args.q)
    print(answer)


if __name__ == "__main__":
    main()




