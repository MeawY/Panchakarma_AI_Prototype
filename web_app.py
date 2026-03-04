# web_app.py
import os
import json
import re
from statistics import mean
from pathlib import Path
from typing import List, Dict, Tuple

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

DB_PATH = str((Path(__file__).resolve().parent / ".chroma"))
COLLECTION = "panchakarma_qa_openai"
EMB_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

GARMIN_TRACKING_LIST = (
    "【アクティビティ系】\n"
    "- 距離（GPS/フットポッド）\n- 速度/ペース（現在・平均・最大）\n\n"
    "【生体・健康系】\n"
    "- 心拍数（現在・平均・最大）\n- 心拍変動（HRV）\n\n"
    "【ストレス・リカバリー系】\n"
    "- ストレスレベル\n- Body Battery"
)

def load_keys() -> Tuple[str | None, str | None]:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
    api = os.getenv("OPENAI_API_KEY", "").strip() or None
    base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    return api, base

def get_topk(query: str, k: int, client: OpenAI) -> Tuple[List[str], List[Dict], List[float]]:
    emb = client.embeddings.create(model=EMB_MODEL, input=[query]).data[0].embedding
    coll = chromadb.PersistentClient(path=DB_PATH).get_or_create_collection(COLLECTION)
    res = coll.query(query_embeddings=[emb], n_results=k, include=["documents", "metadatas", "distances"])  # type: ignore
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    return docs, metas, dists

def summarize(
    client: OpenAI,
    q: str,
    docs: List[str],
    metas: List[Dict],
    mode: str,
    garmin_notes: str,
    garmin_results: str,
    garmin_sleep_summary: str,
    clinical_intake: str,
    include_garmin_list: bool,
) -> str:
    ctx = "\n\n".join([f"[DOC {i}]\n{d}\nMETA: {m}\n" for i, (d, m) in enumerate(zip(docs, metas), start=1)])
    system = (
        "あなたはアーユルヴェーダ/ヘルスケアの臨床家向けアシスタントです。"
        "根拠は与えられたコンテキストのみを使用し、安全性と禁忌を優先します。"
        "診断名の断定や検査値の外挿は行いません。"
    )
    if mode == "レポート形式":
        garmin_block = garmin_notes.strip() or "（入力なし）"
        garmin_result_block = garmin_results.strip() or "（入力なし）"
        garmin_list_block = GARMIN_TRACKING_LIST if include_garmin_list else "（希望時に提示）"
        garmin_sleep_block = garmin_sleep_summary.strip() or "（入力なし）"
        intake_block = clinical_intake.strip() or "（入力なし）"
        user = f"""質問: {q}

コンテキスト:
{ctx}

臨床インテーク:
{intake_block}

Garmin等の観察項目:
{garmin_block}

Garmin等の改善測定:
{garmin_result_block}

Garmin睡眠サマリー:
{garmin_sleep_block}

Garminで推奨するトラッキング項目:
{garmin_list_block}

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
"""
    else:
        user = f"質問: {q}\n\nコンテキスト:\n{ctx}\n\n出力要件:\n- 日本語で5〜8行に要点\n- 必要に応じて禁忌/注意"
    msg = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    return msg.choices[0].message.content or ""


def generate_garmin_notes_results(client: OpenAI, q: str, sleep_summary: str) -> Tuple[str, str]:
    system = (
        "あなたは睡眠指標の要約を臨床向けに整形するアシスタントです。"
        "与えられた睡眠サマリー以外の推測はしません。"
        "数値の誇張や診断的断定は避けます。"
    )
    user = f"""目的:
睡眠サマリーから「観察項目」と「改善測定（変化メモ）」を短く作る。

睡眠サマリー:
{sleep_summary}

質問:
{q}

出力要件:
- 日本語
- 2セクションのみ出力（観察項目 / 改善測定）
- 観察項目は箇条書き3〜6行
- 改善測定は「変化が分かる表現」を優先。判断不能な場合は「変化不明」と明記
"""
    msg = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    text = msg.choices[0].message.content or ""
    sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    notes = ""
    results = ""
    for s in sections:
        if s.startswith("観察項目"):
            notes = s.replace("観察項目", "", 1).strip("：:\n ")
        elif s.startswith("改善測定"):
            results = s.replace("改善測定", "", 1).strip("：:\n ")
    return notes, results


def garmin_insight(notes: str, results: str) -> str:
    text = f"{notes}\n{results}".lower()
    insights = []
    if "hrv" in text:
        if "上" in text or "↑" in text or "上昇" in text:
            insights.append("HRV上昇は回復モードが働いているサインになりやすい。")
        if "下" in text or "↓" in text or "低下" in text:
            insights.append("HRV低下は負荷や回復不足のサインになりやすい。")
    if "心拍" in text:
        if "低下" in text or "↓" in text:
            insights.append("夜間心拍の低下はリカバリーが進んでいる可能性。")
        if "上昇" in text or "↑" in text:
            insights.append("夜間心拍の上昇は交感神経優位の可能性。")
    if "深睡眠" in text:
        if "増" in text or "増加" in text or "↑" in text:
            insights.append("深睡眠の増加は回復の質が上がっている可能性。")
        if "減" in text or "低下" in text or "↓" in text:
            insights.append("深睡眠の低下は回復効率の低下が疑われる。")
    if "中途覚醒" in text:
        if "増" in text or "増加" in text or "↑" in text:
            insights.append("中途覚醒の増加は睡眠の質低下サイン。")
        if "減" in text or "低下" in text or "↓" in text:
            insights.append("中途覚醒の減少は睡眠の安定化を示唆。")
    if "呼吸" in text or "呼吸数" in text:
        if "低下" in text or "↓" in text:
            insights.append("夜間呼吸数の低下はリラックス傾向の可能性。")
        if "上昇" in text or "↑" in text:
            insights.append("夜間呼吸数の上昇はストレスや炎症の可能性。")
    if not insights:
        insights.append("入力された観察項目から自動解釈できる傾向が少ないため、手動での臨床解釈を推奨。")
    return "\n".join(f"- {i}" for i in insights)


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return mean(values)


def build_sleep_summary(records: List[Dict]) -> Dict[str, float | str | int | None]:
    dates = [r.get("calendarDate") for r in records if r.get("calendarDate")]
    sleep_seconds_list = []
    time_in_bed_list = []
    efficiencies = []
    deep_pct = []
    light_pct = []
    rem_pct = []
    overall_scores = []

    for r in records:
        deep = r.get("deepSleepSeconds")
        light = r.get("lightSleepSeconds")
        rem = r.get("remSleepSeconds")
        awake = r.get("awakeSleepSeconds")
        unmeasurable = r.get("unmeasurableSeconds")
        if deep is None or light is None or rem is None:
            continue
        sleep_seconds = float(deep) + float(light) + float(rem)
        sleep_seconds_list.append(sleep_seconds)

        if awake is not None and unmeasurable is not None:
            time_in_bed = sleep_seconds + float(awake) + float(unmeasurable)
            time_in_bed_list.append(time_in_bed)
            if time_in_bed:
                efficiencies.append(sleep_seconds / time_in_bed)

        if sleep_seconds:
            deep_pct.append(float(deep) / sleep_seconds)
            light_pct.append(float(light) / sleep_seconds)
            rem_pct.append(float(rem) / sleep_seconds)

        scores = r.get("sleepScores") or {}
        if "overallScore" in scores and scores.get("overallScore") is not None:
            overall_scores.append(float(scores.get("overallScore")))

    return {
        "recordCount": len(records),
        "dateStart": min(dates) if dates else None,
        "dateEnd": max(dates) if dates else None,
        "avgSleepHours": _mean([s / 3600 for s in sleep_seconds_list]) if sleep_seconds_list else 0.0,
        "avgTimeInBedHours": _mean([t / 3600 for t in time_in_bed_list]) if time_in_bed_list else 0.0,
        "avgSleepEfficiency": _mean(efficiencies),
        "avgDeepPercent": _mean(deep_pct),
        "avgLightPercent": _mean(light_pct),
        "avgRemPercent": _mean(rem_pct),
        "avgOverallScore": _mean([float(s) for s in overall_scores if s is not None]),
    }


def format_sleep_summary(summary: Dict) -> str:
    if not summary:
        return ""
    date_start = summary.get("dateStart") or "不明"
    date_end = summary.get("dateEnd") or "不明"
    record_count = summary.get("recordCount") or 0
    avg_sleep_hours = summary.get("avgSleepHours") or 0.0
    avg_time_bed = summary.get("avgTimeInBedHours") or 0.0
    avg_eff = summary.get("avgSleepEfficiency")
    avg_deep = summary.get("avgDeepPercent")
    avg_light = summary.get("avgLightPercent")
    avg_rem = summary.get("avgRemPercent")
    avg_score = summary.get("avgOverallScore")

    def pct(value: float | None) -> str:
        if value is None:
            return "不明"
        return f"{value * 100:.1f}%"

    score_text = f"{avg_score:.1f}" if isinstance(avg_score, (int, float)) else "不明"
    lines = [
        "Garmin睡眠サマリー",
        f"- 期間: {date_start} 〜 {date_end} ({record_count}日)",
        f"- 平均睡眠時間: {avg_sleep_hours:.2f}h / 平均就床: {avg_time_bed:.2f}h",
        f"- 睡眠効率: {pct(avg_eff)}",
        f"- 深睡眠: {pct(avg_deep)} / 浅睡眠: {pct(avg_light)} / REM: {pct(avg_rem)}",
        f"- 睡眠スコア平均: {score_text}",
    ]
    return "\n".join(lines)


def format_sources(metas: List[Dict]) -> List[str]:
    lines = []
    for m in metas:
        source = m.get("source", "") or "source=なし"
        tags = m.get("+tags", "")
        if tags:
            lines.append(f"{source} / tags={tags}")
        else:
            lines.append(f"{source}")
    return lines


def split_report_sections(text: str) -> List[str]:
    pattern = re.compile(r"(?m)^\d+\.\s")
    matches = list(pattern.finditer(text))
    if not matches:
        return [text.strip()]
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[start:end].strip())
    return [s for s in sections if s]

st.set_page_config(page_title="Panchakarma Clinic Assistant", page_icon="🪷", layout="wide")
st.markdown(
    """
<style>
    .main { background: #fbfaf7; }
    .block-container { padding-top: 2.2rem; padding-bottom: 2.2rem; }
    .pc-title { font-size: 2.1rem; font-weight: 700; color: #2f2f2f; margin-bottom: 0.25rem; }
    .pc-sub { color: #6c6c6c; margin-bottom: 1.2rem; }
    .pc-card { background: #ffffff; border: 1px solid #eee7df; border-radius: 16px;
               padding: 1.1rem 1.2rem; box-shadow: 0 1px 6px rgba(0,0,0,0.04); }
    .pc-pill { display: inline-block; padding: 0.2rem 0.6rem; background: #f3efe9;
               border-radius: 999px; margin-right: 0.35rem; font-size: 0.85rem; }
    .pc-banner { background: #fff3cd; border: 1px solid #ffeeba; color: #7a5a00;
                 padding: 0.6rem 0.9rem; border-radius: 10px; margin-bottom: 1rem; }
    .pc-label { font-size: 0.9rem; color: #7c6f62; margin-bottom: 0.2rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="pc-title">Panchakarma Clinic Assistant 🪷</div>', unsafe_allow_html=True)

api_key, base_url = load_keys()
if not api_key:
    st.error("OPENAI_API_KEY が .env にありません。設定してから再読み込みしてください。")
    st.stop()

st.markdown('<div class="pc-banner">※ 本デモは教育/参考用途です。臨床判断は必ず専門家が行ってください。</div>', unsafe_allow_html=True)
st.info(
    "AI Role & Boundary Declaration\n\n"
    "This AI does not diagnose, prescribe, or make treatment decisions.\n"
    "Its role is limited to:\n"
    "- Supporting practitioner’s thinking\n"
    "- Translating medical concepts for patient understanding\n"
    "- Offering general lifestyle directions (non-prescriptive)\n\n"
    "Any medical judgment must be deferred to a qualified practitioner."
)
with st.expander("パンチャカルマAIの位置づけ（要約）", expanded=False):
    st.markdown(
        """
**基本スタンス**
- 施術や治療の決定はしない（判断は医師）
- AIは「整理・翻訳・補助」に特化

**いまの位置づけ**
- ② 設計補助GPT ＋ ③ 患者説明GPT が中心
- ④ 生活・セルフケアが「補助的に」混ざる構成

**なぜ混ざるのか**
- パンチャカルマは「設計・説明・生活」が分離できないため

**境界線（重要）**
- 診断・処方・施術判断は必ず人間

**対象ユーザー**
- 医師・セラピスト（臨床判断の補助）

**品質ガード（重要）**
- 不明確な場合は保留し、確認事項を提示
- 断定ではなく可能性表現を使用
- 安全性/禁忌を優先表示
"""
    )

with st.container():
    st.markdown('<div class="pc-card">', unsafe_allow_html=True)
    st.markdown('<div class="pc-label">質問</div>', unsafe_allow_html=True)
    q = st.text_input("質問を入力", value="バスティの禁忌は？", label_visibility="collapsed")
    mode = st.selectbox("出力モード", ["簡易回答", "レポート形式"], index=0)
    garmin_notes = ""
    garmin_results = ""
    with st.expander("臨床インテーク（任意）", expanded=True):
        st.markdown("**① 主ドーシャ（複数可）**")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            primary_vata = st.checkbox("ヴァータ（優位）", value=False)
        with col_b:
            primary_pitta = st.checkbox("ピッタ（優位）", value=False)
        with col_c:
            primary_kapha = st.checkbox("カパ（優位）", value=False)

        st.markdown("**①-2 副次ドーシャ（複数可）**")
        col_d, col_e, col_f = st.columns(3)
        with col_d:
            secondary_vata = st.checkbox("ヴァータ（副次）", value=False)
        with col_e:
            secondary_pitta = st.checkbox("ピッタ（副次）", value=False)
        with col_f:
            secondary_kapha = st.checkbox("カパ（副次）", value=False)
        dosha_other = st.text_input("その他/メモ", value="")

        st.markdown("**② 現在の主訴**")
        chief_complaints = st.text_area(
            "主訴",
            placeholder="例）慢性的な疲労感\n睡眠が浅い\n胃腸の不快感",
            height=110,
            label_visibility="collapsed",
        )

        st.markdown("**③ 消化力（主観）**")
        digestion = st.text_area(
            "消化力",
            placeholder="例）弱〜中等度\n朝は食欲が出にくい\n冷たいもの・不規則な食事で悪化",
            height=90,
            label_visibility="collapsed",
        )

        st.markdown("**④ 精神状態（短文）**")
        mental_state = st.text_area(
            "精神状態",
            placeholder="例）不安傾向あり\n緊張が抜けにくい\n責任感が強い",
            height=90,
            label_visibility="collapsed",
        )

        st.markdown("**⑤ 医師の自由メモ（臨床所見 / 方針）**")
        clinician_notes = st.text_area(
            "医師メモ",
            placeholder=(
                "臨床所見：ヴァータ過剰が神経系に強く出ている印象。\n"
                "方針：Purva Karmaを十分に取り、アグニと神経系の安定を優先。"
            ),
            height=140,
            label_visibility="collapsed",
        )

        primary_parts = []
        if primary_vata:
            primary_parts.append("ヴァータ")
        if primary_pitta:
            primary_parts.append("ピッタ")
        if primary_kapha:
            primary_parts.append("カパ")

        secondary_parts = []
        if secondary_vata:
            secondary_parts.append("ヴァータ")
        if secondary_pitta:
            secondary_parts.append("ピッタ")
        if secondary_kapha:
            secondary_parts.append("カパ")

        dosha_parts = []
        primary_line = "優位: " + (" / ".join(primary_parts) if primary_parts else "入力なし")
        secondary_line = "副次: " + (" / ".join(secondary_parts) if secondary_parts else "入力なし")
        dosha_parts.append(primary_line)
        dosha_parts.append(secondary_line)
        if dosha_other.strip():
            dosha_parts.append(f"メモ: {dosha_other.strip()}")
        clinical_intake = "\n".join(
            [
                "① 主ドーシャ（複数可）",
                "- " + "\n- ".join(dosha_parts),
                "",
                "② 現在の主訴",
                chief_complaints.strip() or "入力なし",
                "",
                "③ 消化力（主観）",
                digestion.strip() or "入力なし",
                "",
                "④ 精神状態（短文）",
                mental_state.strip() or "入力なし",
                "",
                "⑤ 医師の自由メモ（臨床所見 / 方針）",
                clinician_notes.strip() or "入力なし",
            ]
        )

    with st.expander("Garmin等の観察項目（任意）", expanded=False):
        st.markdown("**推奨トラッキング項目（例）**")
        st.write(
            "- HRV（夜間）\n- 睡眠：深睡眠 / 中途覚醒\n- 夜間呼吸数\n- 朝の安静時心拍\n- 活動量（歩数）"
        )
        include_garmin_list = st.checkbox("レポートにGarmin推奨項目リストを含める", value=True)
        garmin_notes = st.text_area(
            "観察項目",
            placeholder="例）HRV: 28→32 / 夜間心拍: 65→60 / 深睡眠: 45分 / 中途覚醒: 2回",
            height=110,
        )
        garmin_results = st.text_area(
            "改善測定（変化メモ）",
            placeholder="例）HRVは上昇傾向、夜間心拍は低下、深睡眠は増加",
            height=90,
        )
        st.markdown("**Garmin睡眠データ（JSON）**")
        st.caption("sleepData JSON もしくは *_summary.json のどちらでもOK")
        garmin_sleep_summary_text = ""
        sleep_upload = st.file_uploader(
            "Garmin睡眠JSONをアップロード",
            type=["json"],
            label_visibility="collapsed",
        )
        auto_attach_sleep = st.checkbox(
            "睡眠サマリーをレポートに自動挿入",
            value=True,
        )
        auto_generate_sleep_notes = st.checkbox(
            "睡眠サマリーから観察項目/改善測定を自動生成",
            value=True,
        )
        if sleep_upload is not None:
            try:
                sleep_payload = json.load(sleep_upload)
                if isinstance(sleep_payload, list):
                    sleep_summary = build_sleep_summary(sleep_payload)
                elif isinstance(sleep_payload, dict):
                    sleep_summary = sleep_payload
                else:
                    sleep_summary = {}
                garmin_sleep_summary_text = format_sleep_summary(sleep_summary)
                if garmin_sleep_summary_text:
                    st.markdown("**読み込み結果（プレビュー）**")
                    st.write(garmin_sleep_summary_text)
            except Exception as e:
                st.warning(f"睡眠JSONの読み込みに失敗しました: {e}")
    if mode != "レポート形式":
        include_garmin_list = False
    st.markdown('<div class="pc-label" style="margin-top:0.6rem;">検索レンジ</div>', unsafe_allow_html=True)
    k = st.slider("Top-K", 3, 12, 5, label_visibility="collapsed")
    run = st.button("検索して回答を生成")
    st.markdown("</div>", unsafe_allow_html=True)

if run:
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        docs, metas, dists = get_topk(q, k, client)
        if not docs:
            st.warning("該当なし。データ登録や質問文の見直しを試してください。")
        else:
            if (
                mode == "レポート形式"
                and auto_generate_sleep_notes
                and garmin_sleep_summary_text
                and not (garmin_notes.strip() or garmin_results.strip())
            ):
                auto_notes, auto_results = generate_garmin_notes_results(
                    client, q, garmin_sleep_summary_text
                )
                garmin_notes = auto_notes or garmin_notes
                garmin_results = auto_results or garmin_results
            ans = summarize(
                client,
                q,
                docs,
                metas,
                mode,
                garmin_notes,
                garmin_results,
                garmin_sleep_summary_text if auto_attach_sleep else "",
                clinical_intake,
                include_garmin_list,
            )
            if mode == "レポート形式" and include_garmin_list:
                if "Garmin" not in ans and "推奨トラッキング項目" not in ans:
                    ans = (
                        f"{ans}\n\n6. Garmin等の観察項目と改善判定\n"
                        f"- 推奨トラッキング項目\n{GARMIN_TRACKING_LIST}"
                    )
            st.subheader("🧠 回答")
            sources_lines = format_sources(metas)
            trimmed = sources_lines[:3]
            more_count = max(len(sources_lines) - len(trimmed), 0)
            sources_block = "出典:\n" + "\n".join([f"- {line}" for line in trimmed])
            if more_count:
                sources_block += f"\n- ほか{more_count}件"
            if mode == "レポート形式":
                for section in split_report_sections(ans):
                    st.markdown(section)
            else:
                st.write(ans)
            with st.expander("出典（クリックで表示）", expanded=False):
                st.caption(sources_block)
            if mode == "レポート形式":
                st.subheader("🧭 Garmin観察の整理")
                if include_garmin_list:
                    st.markdown("**推奨トラッキング項目（表示）**")
                    st.write(GARMIN_TRACKING_LIST)
                if garmin_sleep_summary_text:
                    st.markdown("**睡眠サマリー**")
                    st.write(garmin_sleep_summary_text)
                if garmin_notes.strip() or garmin_results.strip():
                    st.markdown("**入力された観察項目**")
                    st.write(garmin_notes.strip() or "（入力なし）")
                    st.markdown("**入力された改善測定**")
                    st.write(garmin_results.strip() or "（入力なし）")
                    st.markdown("**観察項目/改善測定の解説**")
                    st.write(garmin_insight(garmin_notes, garmin_results))
                else:
                    st.write("観察項目と改善測定が未入力。必要に応じて入力してください。")
    except Exception as e:
        st.exception(e)
        # DBの状態を表示
try:
    import chromadb
    from pathlib import Path
    DB_PATH = str((Path(__file__).resolve().parent / ".chroma"))  # 念のため絶対パス
    coll = chromadb.PersistentClient(path=DB_PATH).get_or_create_collection("panchakarma_qa_openai")
    st.caption(f"DB: {DB_PATH} | count={coll.count()}")
except Exception as e:
    st.caption(f"DB error: {e}")