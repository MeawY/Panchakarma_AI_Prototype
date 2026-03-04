import { NextResponse } from "next/server";
import { getDocCount } from "@/lib/db";

export async function GET() {
  try {
    const count = await getDocCount();
    return NextResponse.json({ count });
  } catch (e) {
    return NextResponse.json({ count: null, error: String(e) });
  }
}
