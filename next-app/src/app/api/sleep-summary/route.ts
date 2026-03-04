import { NextRequest, NextResponse } from "next/server";

type SleepRecord = {
  calendarDate?: string;
  deepSleepSeconds?: number;
  lightSleepSeconds?: number;
  remSleepSeconds?: number;
  awakeSleepSeconds?: number;
  unmeasurableSeconds?: number;
  sleepScores?: { overallScore?: number };
};

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function buildSleepSummary(records: SleepRecord[]) {
  const dates = records.map((r) => r.calendarDate).filter(Boolean) as string[];
  const sleepSecondsList: number[] = [];
  const timeInBedList: number[] = [];
  const efficiencies: number[] = [];
  const deepPct: number[] = [];
  const lightPct: number[] = [];
  const remPct: number[] = [];
  const overallScores: number[] = [];

  for (const r of records) {
    const deep = r.deepSleepSeconds;
    const light = r.lightSleepSeconds;
    const rem = r.remSleepSeconds;
    const awake = r.awakeSleepSeconds;
    const unmeasurable = r.unmeasurableSeconds;
    if (deep == null || light == null || rem == null) continue;

    const sleepSeconds = deep + light + rem;
    sleepSecondsList.push(sleepSeconds);

    if (awake != null && unmeasurable != null) {
      const timeInBed = sleepSeconds + awake + unmeasurable;
      timeInBedList.push(timeInBed);
      if (timeInBed > 0) efficiencies.push(sleepSeconds / timeInBed);
    }
    if (sleepSeconds > 0) {
      deepPct.push(deep / sleepSeconds);
      lightPct.push(light / sleepSeconds);
      remPct.push(rem / sleepSeconds);
    }
    const score = r.sleepScores?.overallScore;
    if (score != null) overallScores.push(Number(score));
  }

  return {
    recordCount: records.length,
    dateStart: dates.length ? Math.min(...dates) : null,
    dateEnd: dates.length ? Math.max(...dates) : null,
    avgSleepHours: sleepSecondsList.length ? mean(sleepSecondsList.map((s) => s / 3600)) : 0,
    avgTimeInBedHours: timeInBedList.length ? mean(timeInBedList.map((t) => t / 3600)) : 0,
    avgSleepEfficiency: mean(efficiencies),
    avgDeepPercent: mean(deepPct),
    avgLightPercent: mean(lightPct),
    avgRemPercent: mean(remPct),
    avgOverallScore: mean(overallScores),
  };
}

function formatSleepSummary(summary: ReturnType<typeof buildSleepSummary>): string {
  const s = summary;
  const pct = (v: number | null) => (v == null ? "不明" : `${(v * 100).toFixed(1)}%`);
  const scoreText =
    typeof s.avgOverallScore === "number" ? s.avgOverallScore.toFixed(1) : "不明";
  return [
    "Garmin睡眠サマリー",
    `- 期間: ${s.dateStart ?? "不明"} 〜 ${s.dateEnd ?? "不明"} (${s.recordCount}日)`,
    `- 平均睡眠時間: ${s.avgSleepHours.toFixed(2)}h / 平均就床: ${s.avgTimeInBedHours.toFixed(2)}h`,
    `- 睡眠効率: ${pct(s.avgSleepEfficiency)}`,
    `- 深睡眠: ${pct(s.avgDeepPercent)} / 浅睡眠: ${pct(s.avgLightPercent)} / REM: ${pct(s.avgRemPercent)}`,
    `- 睡眠スコア平均: ${scoreText}`,
  ].join("\n");
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const records: SleepRecord[] = Array.isArray(body) ? body : body?.records ?? [];
    const summary = buildSleepSummary(records);
    const formatted = formatSleepSummary(summary);
    return NextResponse.json({ summary, formatted });
  } catch (e) {
    console.error(e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Sleep summary failed" },
      { status: 500 }
    );
  }
}
