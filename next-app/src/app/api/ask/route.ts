import { NextRequest, NextResponse } from "next/server";
import { embedQuery, chat } from "@/lib/openai";
import { searchSimilar } from "@/lib/db";

const GARMIN_TRACKING_LIST = `【アクティビティ系】
- 距離（GPS/フットポッド）
- 速度/ペース（現在・平均・最大）

【生体・健康系】
- 心拍数（現在・平均・最大）
- 心拍変動（HRV）

【ストレス・リカバリー系】
- ストレスレベル
- Body Battery`;

function formatSources(metas: Record<string, unknown>[]): string[] {
  return metas.map((m) => {
    const source = (m?.source as string) ?? "source=なし";
    const tags = (m?.["+tags"] as string) ?? "";
    return tags ? `${source} / tags=${tags}` : source;
  });
}

function garminInsight(notes: string, results: string): string {
  const text = `${notes}\n${results}`.toLowerCase();
  const insights: string[] = [];
  if (text.includes("hrv")) {
    if (/上|↑|上昇/.test(text)) insights.push("HRV上昇は回復モードが働いているサインになりやすい。");
    if (/下|↓|低下/.test(text)) insights.push("HRV低下は負荷や回復不足のサインになりやすい。");
  }
  if (text.includes("心拍")) {
    if (text.includes("低下") || text.includes("↓")) insights.push("夜間心拍の低下はリカバリーが進んでいる可能性。");
    if (text.includes("上昇") || text.includes("↑")) insights.push("夜間心拍の上昇は交感神経優位の可能性。");
  }
  if (text.includes("深睡眠")) {
    if (/増|増加|↑/.test(text)) insights.push("深睡眠の増加は回復の質が上がっている可能性。");
    if (/減|低下|↓/.test(text)) insights.push("深睡眠の低下は回復効率の低下が疑われる。");
  }
  if (text.includes("中途覚醒")) {
    if (/増|増加|↑/.test(text)) insights.push("中途覚醒の増加は睡眠の質低下サイン。");
    if (/減|低下|↓/.test(text)) insights.push("中途覚醒の減少は睡眠の安定化を示唆。");
  }
  if (text.includes("呼吸") || text.includes("呼吸数")) {
    if (text.includes("低下") || text.includes("↓")) insights.push("夜間呼吸数の低下はリラックス傾向の可能性。");
    if (text.includes("上昇") || text.includes("↑")) insights.push("夜間呼吸数の上昇はストレスや炎症の可能性。");
  }
  if (insights.length === 0) {
    insights.push("入力された観察項目から自動解釈できる傾向が少ないため、手動での臨床解釈を推奨。");
  }
  return insights.map((i) => `- ${i}`).join("\n");
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      query,
      k = 5,
      mode = "簡易回答",
      clinicalIntake = "",
      garminNotes = "",
      garminResults = "",
      garminSleepSummary = "",
      includeGarminList = false,
      autoGenerateSleepNotes = true,
      autoAttachSleep = true,
    } = body as {
      query?: string;
      k?: number;
      mode?: string;
      clinicalIntake?: string;
      garminNotes?: string;
      garminResults?: string;
      garminSleepSummary?: string;
      includeGarminList?: boolean;
      autoGenerateSleepNotes?: boolean;
      autoAttachSleep?: boolean;
    };

    if (!query || typeof query !== "string") {
      return NextResponse.json({ error: "query is required" }, { status: 400 });
    }

    const topK = Math.min(Math.max(Number(k) || 5, 1), 12);
    const embedding = await embedQuery(query);
    const rows = await searchSimilar(embedding, topK);
    const docs = rows.map((r) => r.content);
    const metas = rows.map((r) => r.metadata);

    let notes = (garminNotes || "").trim();
    let results = (garminResults || "").trim();
    const sleepSummaryText = (garminSleepSummary || "").trim();

    if (
      mode === "レポート形式" &&
      autoGenerateSleepNotes &&
      sleepSummaryText &&
      !notes &&
      !results
    ) {
      const system =
        "あなたは睡眠指標の要約を臨床向けに整形するアシスタントです。与えられた睡眠サマリー以外の推測はしません。数値の誇張や診断的断定は避けます。";
      const user = `目的:
睡眠サマリーから「観察項目」と「改善測定（変化メモ）」を短く作る。

睡眠サマリー:
${sleepSummaryText}

質問:
${query}

出力要件:
- 日本語
- 2セクションのみ出力（観察項目 / 改善測定）
- 観察項目は箇条書き3〜6行
- 改善測定は「変化が分かる表現」を優先。判断不能な場合は「変化不明」と明記`;
      const text = await chat(system, user);
      const sections = text.split("\n\n").map((s) => s.trim()).filter(Boolean);
      for (const s of sections) {
        if (s.startsWith("観察項目")) notes = s.replace(/^観察項目\s*[：:]\s*/, "").trim();
        else if (s.startsWith("改善測定")) results = s.replace(/^改善測定\s*[：:]\s*/, "").trim();
      }
    }

    const ctx = docs
      .map((d, i) => `[DOC ${i + 1}]\n${d}\nMETA: ${JSON.stringify(metas[i] || {})}\n`)
      .join("\n\n");
    const system =
      "あなたはアーユルヴェーダ/ヘルスケアの臨床家向けアシスタントです。根拠は与えられたコンテキストのみを使用し、安全性と禁忌を優先します。診断名の断定や検査値の外挿は行いません。";

    let user: string;
    if (mode === "レポート形式") {
      const garminBlock = notes || "（入力なし）";
      const garminResultBlock = results || "（入力なし）";
      const garminListBlock = includeGarminList ? GARMIN_TRACKING_LIST : "（希望時に提示）";
      const garminSleepBlock = autoAttachSleep ? sleepSummaryText || "（入力なし）" : "（入力なし）";
      const intakeBlock = clinicalIntake.trim() || "（入力なし）";
      user = `質問: ${query}

コンテキスト:
${ctx}

臨床インテーク:
${intakeBlock}

Garmin等の観察項目:
${garminBlock}

Garmin等の改善測定:
${garminResultBlock}

Garmin睡眠サマリー:
${garminSleepBlock}

Garminで推奨するトラッキング項目:
${garminListBlock}

出力要件:
- Health Scan Only Protocol に準拠
- 軽度/重度のみを抽出（安定は書かない）
- 連鎖モデルとCore Patternは最大3つ
- 介入はPhase1〜4の順序固定、サプリ名の断定は避ける
- 医療者向け/本人向けの2段階を明確に分ける
- 日本語で、見出し付きのレポート形式
- Garmin等の観察項目/改善測定/睡眠サマリー/推奨リストがすべて「入力なし or 希望時に提示」の場合は 6 を出力しない

レポート固定フォーマット:
1. 軽度・重度項目リスト（系統別）
2. 体のつながり方（どこから影響が広がっているか）
3. 今の一番の土台（最大3）
4. 段階的ロードマップ（Phase1〜4）
5. 本人向け説明（やさしい版）
6. （必要時）Garmin等の観察項目と改善判定
`;
    } else {
      user = `質問: ${query}\n\nコンテキスト:\n${ctx}\n\n出力要件:\n- 日本語で5〜8行に要点\n- 必要に応じて禁忌/注意`;
    }

    let answer = await chat(system, user);
    if (
      mode === "レポート形式" &&
      includeGarminList &&
      !answer.includes("Garmin") &&
      !answer.includes("推奨トラッキング項目")
    ) {
      answer += `\n\n6. Garmin等の観察項目と改善判定\n- 推奨トラッキング項目\n${GARMIN_TRACKING_LIST}`;
    }

    const sources = formatSources(metas);
    const garminInsightText =
      mode === "レポート形式" && (notes || results) ? garminInsight(notes, results) : undefined;

    return NextResponse.json({
      answer,
      sources,
      garminInsight: garminInsightText,
      garminTrackingList: includeGarminList ? GARMIN_TRACKING_LIST : undefined,
    });
  } catch (e) {
    console.error(e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Ask failed" },
      { status: 500 }
    );
  }
}
