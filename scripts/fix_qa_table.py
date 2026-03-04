import re
from pathlib import Path
from typing import List, Tuple

SRC = Path("data/panchakarma_qa_pairs.md")
DST = Path("data/panchakarma_qa_pairs_checked_fixed.md")

HEADER = "| no | question | answer | source |\n|---:|---|---|---|\n"

# タグ検出用の簡易ルール
PHASE_RULES = {
    "#前処置": r"(前処置|プールヴァカルマ|アーマ・パーチャナ|スネーハナ|スウェーダナ)",
    "#中心処置": r"(中心処置|ヴァマナ|ヴィレーチャナ|バスティ|ナスヤ|ラクタ|瀉血法)",
    "#後処置": r"(後処置|パシュチャートカルマ|サムサルジャナ|ラサーヤナ)",
}
DOSHA_RULES = {
    "#ヴァータ": r"(ヴァータ|乾燥|冷え|不安|関節痛|ガス|神経|夜|夕方)",
    "#ピッタ": r"(ピッタ|炎症|発熱|怒り|酸|肝|胆|灼熱|正午|昼)",
    "#カパ": r"(カパ|重さ|粘|粘性|むくみ|浮腫|倦怠|呼吸|鼻|たん|痰|朝)",
}
SITUATION_RULES = {
    "#禁忌": r"(禁忌|禁じ|してはならない|適さない|避けるべき)",
    "#推奨": r"(推奨|おすすめ|適している|適当|勧め|推奨される)",
}

TAG_PATTERNS = [
    ("#前処置", r"(前処置|プールヴァカルマ|アーマ・パーチャナ|スネーハナ|スウェーダナ)"),
    ("#中心処置", r"(中心処置|ヴァマナ|ヴィレーチャナ|バスティ|ナスヤ|ラクタ)"),
    ("#後処置", r"(後処置|パシュチャートカルマ|サムサルジャナ|ラサーヤナ)"),
    ("#ドーシャ", r"(ドーシャ|ヴァータ|ピッタ|カパ)"),
]


def split_row(line: str) -> List[str]:
    raw = line.strip().strip("|")
    parts = [p.strip() for p in raw.split("|")]
    return parts


def parse_table(text: str) -> Tuple[List[str], List[List[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = lines[0]
    assert header.startswith("|"), "not a table"
    rows = []
    for ln in lines[2:]:  # skip header + separator
        if not ln.strip().startswith("|"):
            continue
        rows.append(split_row(ln))
    return split_row(header), rows


def normalize_sources(source: str, answer: str) -> Tuple[str, str]:
    # extract $$...$$ tokens from answer
    tokens = re.findall(r"\$\$([^$]+)\$\$", answer)
    answer = re.sub(r"\$\$[^$]+\$\$", "", answer)
    # add existing source tokens (strip [] and spaces)
    if source:
        cleaned = source.strip().strip("[]")
        if cleaned:
            tokens.extend([t.strip() for t in cleaned.split(",") if t.strip()])
    # normalize duplicates and spacing
    norm = []
    for t in tokens:
        t = t.replace(" ", "")
        if t and t not in norm:
            norm.append(t)
    src = f"[{', '.join(norm)}]" if norm else ""
    return src, answer


def clean_answer(ans: str) -> str:
    if not ans:
        return ans
    # remove spaces before punctuation
    ans = re.sub(r"\s+([。、「」、，．\.])", r"\1", ans)
    # fix trailing '。-' -> '。'
    ans = re.sub(r"。-*\s*$", "。", ans)
    # ensure terminal punctuation
    if not re.search(r"[。.!!？?]$", ans):
        ans += "。"
    return ans


def detect_tags(text: str) -> list:
    tags = []
    for tag, pat in PHASE_RULES.items():
        if re.search(pat, text):
            tags.append(tag)
    for tag, pat in DOSHA_RULES.items():
        if re.search(pat, text):
            tags.append(tag)
    for tag, pat in SITUATION_RULES.items():
        if re.search(pat, text):
            tags.append(tag)
    # ユニーク順序維持
    uniq = []
    for t in tags:
        if t not in uniq:
            uniq.append(t)
    return uniq


def ensure_tags(ans: str, base_text: str) -> str:
    tags = detect_tags(base_text)
    if not tags:
        return ans
    # 既存タグは保持
    for t in list(tags):
        if t in ans:
            tags.remove(t)
    if not tags:
        return ans
    suffix = " ".join(tags)
    if not ans:
        return suffix
    if ans.endswith("。"):
        return ans + " " + suffix
    return ans + " " + suffix


def main():
    text = SRC.read_text(encoding="utf-8")
    header_cols, rows = parse_table(text)
    out_lines = [HEADER]
    for r in rows:
        if len(r) < 4:
            r += [""] * (4 - len(r))
        no, q, a, s = r[0], r[1], r[2], r[3]
        s, a = normalize_sources(s, a)
        a = clean_answer(a)
        a = ensure_tags(a, q + " " + a)
        out_lines.append(f"| {no} | {q} | {a} | {s} |\n")
    DST.write_text("".join(out_lines), encoding="utf-8")
    print(f"Wrote {DST}")


if __name__ == "__main__":
    main()
