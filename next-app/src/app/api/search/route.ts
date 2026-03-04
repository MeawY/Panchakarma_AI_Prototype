import { NextRequest, NextResponse } from "next/server";
import { embedQuery } from "@/lib/openai";
import { searchSimilar } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const { query, k = 5 } = (await req.json()) as { query?: string; k?: number };
    if (!query || typeof query !== "string") {
      return NextResponse.json({ error: "query is required" }, { status: 400 });
    }
    const topK = Math.min(Math.max(Number(k) || 5, 1), 12);
    const embedding = await embedQuery(query);
    const rows = await searchSimilar(embedding, topK);
    const docs = rows.map((r) => r.content);
    const metas = rows.map((r) => r.metadata);
    const distances = rows.map((r) => r.distance);
    return NextResponse.json({ docs, metas, distances });
  } catch (e) {
    console.error(e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Search failed" },
      { status: 500 }
    );
  }
}
