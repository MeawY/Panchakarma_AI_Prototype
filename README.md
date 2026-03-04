# 環境変数の設定

1. 雛形をコピー

   ```bash
   cp env.example .env
   ```

2. `.env` を開いて、前プロジェクトの API キーや接続情報を貼り付け
   - 例: `OPENAI_API_KEY=...`, `DATABASE_URL=...`, `SUPABASE_URL=...` など

3. `.env` はすでに `.gitignore` 済み。機密情報はコミットしないでください。

4. よく使うキー例
   - AI: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `AZURE_OPENAI_API_KEY`
   - DB: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - Vector/Search: `PINECONE_API_KEY`, `WEAVIATE_*`, `QDRANT_*`
   - Others: `HF_TOKEN`, `SERPAPI_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`

前プロジェクトに `.env` がある場合は、以下で一括移行できます（中身を確認してから上書き推奨）。

```bash
cp /path/to/old/project/.env /Users/yoko/Desktop/Panchakarma_AI_Prototype/.env
```

---

# Python + SQLAlchemy セットアップ

1. 仮想環境を作成・有効化

```bash
cd /Users/yoko/Desktop/Panchakarma_AI_Prototype
python3 -m venv .venv
source .venv/bin/activate
```

2. 依存関係をインストール

```bash
pip install -r requirements.txt
```

3. 接続テスト（`.env` の `DATABASE_URL` を使用）

```bash
python -m scripts.test_db
```

- 成功時: `DB OK`
- 失敗時: `.env` の `DATABASE_URL` を確認（`?sslmode=require` を付与）

---

# Markdown 表データのインポート

- GitHub フレーバーの Markdown 表（ヘッダ行 + 区切り行 `---` + データ行）を取り込み可能です。
- 初回はテーブルを自動作成します（全カラム TEXT 型）。

```bash
# 例: data/patients.md を public.patients に取り込む
python -m scripts.markdown_import data/patients.md -t patients -s public
```

- 既存テーブルがなければ作成します。
- カラム名はヘッダから自動で `snake_case` 化されます。
- 型はすべて TEXT で作成（まずは取り込みを優先）。必要になったら型変更・制約は後で調整します。

