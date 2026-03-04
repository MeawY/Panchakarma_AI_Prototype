import argparse
import re
from pathlib import Path
from typing import List, Tuple

# Defaults
DEFAULT_IN = Path("data/panchakarma_qa_pairs.md")
DEFAULT_OUT = Path("data/panchakarma_qa_pairs_tagged.md")

HEADER = "| no | question | answer | source | tag |\n|---:|---|---|---|---|\n"

# Phase rules
PHASE_RULES = [
    ("#前処置", r"(前処置|プールヴァカルマ|アーマ・パーチャナ|スネーハナ|スネーハ|スウェーダナ|発汗法)"),
    ("#中心処置", r"(中心処置|主処置|ヴァマナ|催吐法|ヴィレーチャナ|瀉下法|バスティ|浣腸法|ナスヤ|経鼻法|ラクタ|瀉血法|ラクタ・モークシャナ)"),
    ("#後処置", r"(後処置|パシュチャートカルマ|サムサルジャナ|食餌法|ラサーヤナ|強壮剤法)")
]

# Dosha rules - include symptom hints and time-of-day
DOSHA_RULES = [
    ("#ヴァータ", r"(ヴァータ|乾燥|冷え|不安|関節痛|ガス|神経|夜|夕方)"),
    ("#ピッタ", r"(ピッタ|炎症|発熱|怒り|酸|肝|胆|灼熱|正午|昼)"),
    ("#カパ", r"(カパ|重さ|粘|粘性|むくみ|浮腫|倦怠|呼吸|鼻|たん|痰|朝)")
]

# Situation rules (extended synonyms)
SITUATION_RULES = [
    ("#禁忌", r"(禁忌|してはならない|禁止|適さない|避けるべき)"),
    ("#推奨", r"(推奨|おすすめ|適している|適当|勧め|推奨される)")
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


def detect_tags(payload: str) -> List[str]:
    tags: List[str] = []
    for tag, pat in PHASE_RULES:
        if re.search(pat, payload):
            tags.append(tag)
    for tag, pat in DOSHA_RULES:
        if re.search(pat, payload):
            tags.append(tag)
    for tag, pat in SITUATION_RULES:
        if re.search(pat, payload):
            tags.append(tag)
    # unique, stable order
    uniq: List[str] = []
    for t in tags:
        if t not in uniq:
            uniq.append(t)
    return uniq


def main():
    p = argparse.ArgumentParser(description="Add Tag column to QA markdown using phase/dosha/situation rules")
    p.add_argument("--input", "-i", default=str(DEFAULT_IN), help="Input QA markdown path")
    p.add_argument("--output", "-o", default=str(DEFAULT_OUT), help="Output tagged markdown path")
    args = p.parse_args()

    inp = Path(args.input)
    outp = Path(args.output)

    text = inp.read_text(encoding="utf-8")
    header_cols, rows = parse_table(text)

    # header is assumed: no | question | answer | source |
    out_lines: List[str] = [HEADER]
    for r in rows:
        # pad to 4 cols
        if len(r) < 4:
            r += [""] * (4 - len(r))
        no, q, a, s = r[0], r[1], r[2], r[3]
        payload = f"{q} {a} {s}"
        tags = detect_tags(payload)
        tag_str = " ".join(tags)
        out_lines.append(f"| {no} | {q} | {a} | {s} | {tag_str} |\n")

    outp.write_text("".join(out_lines), encoding="utf-8")
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()
