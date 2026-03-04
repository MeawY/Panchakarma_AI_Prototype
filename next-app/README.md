# Panchakarma Clinic Assistant（Next.js + Neon）

Streamlit + ChromaDB 版を **Next.js** と **Neon（Postgres + pgvector）** で作り直したフロント／API です。

## 必要なもの

- **Node.js** 18+
- **Neon** アカウント（[neon.tech](https://neon.tech)）
- **OpenAI API Key**（または互換 API）

## セットアップ

### 1. Neon で DB 作成

1. [Neon Console](https://console.neon.tech) でプロジェクトを作成
2. **SQL Editor** で `schema.sql` の内容を実行（pgvector 拡張と `panchakarma_docs` テーブル作成）

### 2. 環境変数

```bash
cp .env.local.example .env.local
```

`.env.local` を編集:

- `DATABASE_URL`: Neon の接続文字列（Connection string）
- `OPENAI_API_KEY`: OpenAI（または互換）の API キー
- `OPENAI_BASE_URL`: 任意（省略時は OpenAI 本番）

### 3. 依存関係と起動

```bash
cd next-app
npm install
npm run dev
```

ブラウザで [http://localhost:3000](http://localhost:3000) を開く。

## ChromaDB から Neon へのデータ移行

既存の `.chroma` の RAG ドキュメントを Neon に移行する場合:

1. `next-app/.env.local` に `DATABASE_URL` を設定
2. プロジェクトルートに `.chroma` がある前提で:

```bash
cd next-app
pip install 'psycopg[binary]' chromadb  # 未インストールの場合
python scripts/migrate-chroma-to-neon.py
```

Chroma のパスを変えたい場合は環境変数で指定:

```bash
CHROMA_PATH=/path/to/.chroma python scripts/migrate-chroma-to-neon.py
```

## 主な構成

| 役割       | 技術 |
|------------|------|
| フロント   | Next.js 14 (App Router), React |
| DB         | Neon (Serverless Postgres) |
| ベクトル検索 | pgvector（同一 DB） |
| AI         | OpenAI API（埋め込み + チャット） |

- **API**
  - `POST /api/ask` … 質問・臨床インテーク・Garmin を送り、回答・出典・Garmin 観察の整理を返す
  - `POST /api/search` … 質問でベクトル検索のみ
  - `POST /api/sleep-summary` … 睡眠 JSON からサマリー生成
  - `GET /api/db-status` … RAG ドキュメント件数

## 注意

- 本デモは教育・参考用です。臨床判断は専門家が行ってください。
- RAG 用ドキュメントは Neon の `panchakarma_docs` に格納します。新規ドキュメントの投入は別スクリプトまたは管理画面で行う想定です。
