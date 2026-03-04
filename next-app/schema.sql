-- Run this in Neon SQL Editor: https://console.neon.tech
-- 1. Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. RAG documents table (replaces ChromaDB collection)
-- text-embedding-3-small = 1536 dimensions
CREATE TABLE IF NOT EXISTS panchakarma_docs (
  id BIGSERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  embedding VECTOR(1536) NOT NULL
);

-- 3. Index for fast similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS panchakarma_docs_embedding_idx
  ON panchakarma_docs
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
