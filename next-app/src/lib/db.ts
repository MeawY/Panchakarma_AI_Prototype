import { neon } from "@neondatabase/serverless";

function getSql() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL が未設定です。.env.local に Neon の接続文字列を設定してください。");
  }
  return neon(connectionString);
}

export type DocRow = {
  id: number;
  content: string;
  metadata: Record<string, unknown>;
  embedding: number[];
};

/** Cosine distance: ORDER BY embedding <=> $1 LIMIT k */
export async function searchSimilar(
  embedding: number[],
  k: number
): Promise<{ content: string; metadata: Record<string, unknown>; distance: number }[]> {
  const sql = getSql();
  const embeddingStr = `[${embedding.join(",")}]`;
  const rows = await sql`
    SELECT content, metadata, (embedding <=> ${embeddingStr}::vector) AS distance
    FROM panchakarma_docs
    ORDER BY embedding <=> ${embeddingStr}::vector
    LIMIT ${k}
  `;
  return (rows as { content: string; metadata: Record<string, unknown>; distance: number }[]) || [];
}

export async function getDocCount(): Promise<number> {
  const sql = getSql();
  const rows = await sql`SELECT COUNT(*)::int AS count FROM panchakarma_docs`;
  return (rows[0] as { count: number })?.count ?? 0;
}
