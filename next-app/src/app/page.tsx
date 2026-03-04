"use client";

import { useState, useCallback } from "react";

type AskResult = {
  answer: string;
  sources: string[];
  garminInsight?: string;
  garminTrackingList?: string;
};

function splitReportSections(text: string): string[] {
  return text.split(/\n(?=\d+\.\s)/).filter(Boolean);
}

export default function Home() {
  const [query, setQuery] = useState("バスティの禁忌は？");
  const [mode, setMode] = useState<"簡易回答" | "レポート形式">("簡易回答");
  const [k, setK] = useState(5);
  const [clinicalIntake, setClinicalIntake] = useState("");
  const [garminNotes, setGarminNotes] = useState("");
  const [garminResults, setGarminResults] = useState("");
  const [garminSleepSummary, setGarminSleepSummary] = useState("");
  const [includeGarminList, setIncludeGarminList] = useState(true);
  const [autoAttachSleep, setAutoAttachSleep] = useState(true);
  const [autoGenerateSleepNotes, setAutoGenerateSleepNotes] = useState(true);
  const [intakeExpanded, setIntakeExpanded] = useState(true);
  const [garminExpanded, setGarminExpanded] = useState(false);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dbCount, setDbCount] = useState<number | null>(null);

  const onSleepFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(reader.result as string);
        const records = Array.isArray(payload) ? payload : payload?.records ?? payload;
        if (!Array.isArray(records) || records.length === 0) {
          setGarminSleepSummary("（有効な睡眠データがありません）");
          return;
        }
        fetch("/api/sleep-summary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(records),
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.formatted) setGarminSleepSummary(data.formatted);
            else setError(data.error || "サマリー取得に失敗");
          })
          .catch((err) => setError(String(err)));
      } catch {
        setError("JSONの解析に失敗しました");
      }
    };
    reader.readAsText(file);
  }, []);

  const runAsk = useCallback(async () => {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          k,
          mode,
          clinicalIntake,
          garminNotes,
          garminResults,
          garminSleepSummary,
          includeGarminList: mode === "レポート形式" && includeGarminList,
          autoAttachSleep,
          autoGenerateSleepNotes,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  }, [
    query,
    k,
    mode,
    clinicalIntake,
    garminNotes,
    garminResults,
    garminSleepSummary,
    includeGarminList,
    autoAttachSleep,
    autoGenerateSleepNotes,
  ]);

  const loadDbStatus = useCallback(() => {
    fetch("/api/db-status")
      .then((r) => r.json())
      .then((data) => setDbCount(data.count ?? null))
      .catch(() => setDbCount(null));
  }, []);

  return (
    <main className="main" style={{ maxWidth: 960, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <h1 style={{ fontSize: "2.1rem", fontWeight: 700, color: "#2f2f2f", marginBottom: "0.25rem" }}>
        Panchakarma Clinic Assistant 🪷
      </h1>
      <div style={{ background: "#fff3cd", border: "1px solid #ffeeba", color: "#7a5a00", padding: "0.6rem 0.9rem", borderRadius: 10, marginBottom: "1rem" }}>
        ※ 本デモは教育/参考用途です。臨床判断は必ず専門家が行ってください。
      </div>
      <div className="pc-card" style={{ marginBottom: "1rem" }}>
        <p style={{ margin: 0, fontSize: "0.95rem" }}>
          <strong>AI Role &amp; Boundary Declaration</strong>
          <br />
          This AI does not diagnose, prescribe, or make treatment decisions. It supports
          practitioner’s thinking, translates medical concepts, and offers general
          lifestyle directions. Any medical judgment must be deferred to a qualified
          practitioner.
        </p>
      </div>

      <div className="pc-card">
        <div className="pc-label">質問</div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="質問を入力"
          style={{ marginBottom: "0.75rem" }}
        />
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
          <label>
            <span className="pc-label">出力モード</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "簡易回答" | "レポート形式")}
            >
              <option value="簡易回答">簡易回答</option>
              <option value="レポート形式">レポート形式</option>
            </select>
          </label>
          <label>
            <span className="pc-label">Top-K</span>
            <input
              type="range"
              min={3}
              max={12}
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
            />
            <span> {k}</span>
          </label>
        </div>

        <div className="expander">
          <button
            type="button"
            className="expander-head"
            onClick={() => setIntakeExpanded((b) => !b)}
          >
            {intakeExpanded ? "▼" : "▶"} 臨床インテーク（任意）
          </button>
          {intakeExpanded && (
            <div className="expander-body">
              <div className="pc-label">主ドーシャ・副次ドーシャ・主訴・消化力・精神状態・医師メモ</div>
              <textarea
                value={clinicalIntake}
                onChange={(e) => setClinicalIntake(e.target.value)}
                placeholder="例）主ドーシャ: ヴァータ優位&#10;主訴: 慢性的な疲労感、睡眠が浅い&#10;消化力: 弱〜中等度&#10;..."
                rows={8}
              />
            </div>
          )}
        </div>

        <div className="expander">
          <button
            type="button"
            className="expander-head"
            onClick={() => setGarminExpanded((b) => !b)}
          >
            {garminExpanded ? "▼" : "▶"} Garmin等の観察項目（任意）
          </button>
          {garminExpanded && (
            <div className="expander-body">
              <label>
                <input
                  type="checkbox"
                  checked={includeGarminList}
                  onChange={(e) => setIncludeGarminList(e.target.checked)}
                />
                レポートにGarmin推奨項目リストを含める
              </label>
              <div className="pc-label">観察項目</div>
              <textarea
                value={garminNotes}
                onChange={(e) => setGarminNotes(e.target.value)}
                placeholder="例）HRV: 28→32 / 夜間心拍: 65→60 / 深睡眠: 45分"
                rows={3}
              />
              <div className="pc-label">改善測定（変化メモ）</div>
              <textarea
                value={garminResults}
                onChange={(e) => setGarminResults(e.target.value)}
                placeholder="例）HRVは上昇傾向、夜間心拍は低下"
                rows={2}
              />
              <div className="pc-label">Garmin睡眠データ（JSON）</div>
              <input type="file" accept=".json" onChange={onSleepFile} />
              <label>
                <input
                  type="checkbox"
                  checked={autoAttachSleep}
                  onChange={(e) => setAutoAttachSleep(e.target.checked)}
                />
                睡眠サマリーをレポートに自動挿入
              </label>
              <label style={{ display: "block" }}>
                <input
                  type="checkbox"
                  checked={autoGenerateSleepNotes}
                  onChange={(e) => setAutoGenerateSleepNotes(e.target.checked)}
                />
                睡眠サマリーから観察項目/改善測定を自動生成
              </label>
              {garminSleepSummary && (
                <div style={{ marginTop: "0.5rem" }}>
                  <div className="pc-label">読み込み結果（プレビュー）</div>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem" }}>
                    {garminSleepSummary}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        <div style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="primary"
            onClick={runAsk}
            disabled={loading}
          >
            {loading ? "生成中…" : "検索して回答を生成"}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="pc-card answer-section" style={{ marginTop: "1.5rem" }}>
          <h2>🧠 回答</h2>
          {mode === "レポート形式"
            ? splitReportSections(result?.answer ?? "").map((section, i) => (
                <div key={i} className="section-block">
                  {section}
                </div>
              ))
            : (result?.answer ?? "")}
          {result.sources.length > 0 && (
            <details style={{ marginTop: "1rem" }}>
              <summary>出典（クリックで表示）</summary>
              <ul className="sources-list">
                {result.sources.slice(0, 5).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
                {result.sources.length > 5 && (
                  <li>ほか{result.sources.length - 5}件</li>
                )}
              </ul>
            </details>
          )}
          {result.garminInsight && (
            <div style={{ marginTop: "1rem" }}>
              <h3>🧭 Garmin観察の整理</h3>
              {result.garminTrackingList && (
                <>
                  <div className="pc-label">推奨トラッキング項目</div>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem" }}>
                    {result.garminTrackingList}
                  </pre>
                </>
              )}
              <div className="pc-label">観察項目/改善測定の解説</div>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem" }}>
                {result.garminInsight}
              </pre>
            </div>
          )}
        </div>
      )}

      <div className="db-footer">
        <button type="button" onClick={loadDbStatus} style={{ marginRight: "0.5rem" }}>
          DB件数表示
        </button>
        {dbCount !== null && <span>Neon panchakarma_docs: {dbCount} 件</span>}
      </div>
    </main>
  );
}
