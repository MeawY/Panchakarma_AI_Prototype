import re
from pathlib import Path
from typing import List, Tuple

SRC = Path("data/panchakarma_facts.md")
DST = Path("data/panchakarma_facts_checked_fixed.md")

PHASE_KEYS = ["前処置", "プールヴァカルマ", "アーマ・パーチャナ", "スネーハ", "スウェーダ", "中心処置", "主処置", "ヴァマナ", "ヴィレーチャナ", "バスティ", "ナスヤ", "ラクタ", "後処置", "パシュチャートカルマ", "サムサルジャナ", "ラサーヤナ"]

TAG_ORDER = [
    ("#前処置", ["前処置", "プールヴァカルマ", "スネーハ", "スウェーダ"]),
    ("#中心処置", ["主処置", "ヴァマナ", "ヴィレーチャナ", "バスティ", "ナスヤ", "ラクタ"]),
    ("#後処置", ["後処置", "パシュチャートカルマ", "サムサルジャナ", "ラサーヤナ"]) ,
    ("#ドーシャ", ["ドーシャ", "ヴァータ", "ピッタ", "カパ"]) ,
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


def tidy_cell(s: str) -> str:
    if not s:
        return s
    # remove spaces before punctuation
    s = re.sub(r"\s+([。、「」、，．\.])", r"\1", s)
    # ensure terminal punctuation for Japanese sentences (heuristic)
    if re.search(r"[ぁ-んァ-ン一-龥]", s) and not re.search(r"[。.!?！？]$", s):
        s += "。"
    return s


def choose_tags(cells_by_header: dict) -> list:
    text_blob = " ".join(cells_by_header.values())
    tags = []
    # phase
    if re.search(r"(前処置|プールヴァカルマ|アーマ・パーチャナ|スネーハ|スウェーダ)", text_blob):
        tags.append("#前処置")
    if re.search(r"(中心処置|主処置|ヴァマナ|ヴィレーチャナ|バスティ|ナスヤ|ラクタ|瀉血法)", text_blob):
        tags.append("#中心処置")
    if re.search(r"(後処置|パシュチャートカルマ|サムサルジャナ|ラサーヤナ)", text_blob):
        tags.append("#後処置")
    # dosha
    if "ヴァータ" in text_blob:
        tags.append("#ヴァータ")
    if "ピッタ" in text_blob:
        tags.append("#ピッタ")
    if "カパ" in text_blob:
        tags.append("#カパ")
    # situation
    if re.search(r"(禁忌|禁じ|してはならない|適さない)", text_blob):
        tags.append("#禁忌")
    if re.search(r"(推奨|おすすめ|適している|適当|勧め)", text_blob):
        tags.append("#推奨")
    uniq = []
    for t in tags:
        if t not in uniq:
            uniq.append(t)
    return uniq


def build_row(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |\n"


def main():
    text = SRC.read_text(encoding="utf-8")
    headers, rows = parse_table(text)

    # Normalize header names to use as dictionary keys
    header_keys = [h.strip() for h in headers]

    out_lines = ["| " + " | ".join(header_keys) + " |\n", "|" + "|".join(["---"] * len(header_keys)) + "|\n"]

    for r in rows:
        # pad/truncate
        if len(r) < len(header_keys):
            r += [""] * (len(header_keys) - len(r))
        elif len(r) > len(header_keys):
            r = r[: len(header_keys)]

        cells_by_header = {header_keys[i]: r[i] for i in range(len(header_keys))}

        # tidy text cells
        for i, key in enumerate(header_keys):
            cells_by_header[key] = tidy_cell(cells_by_header[key])

        # append tag into "目的/効果" column if present, otherwise into the last column
        tags = choose_tags(cells_by_header)
        target_col = None
        for idx, key in enumerate(header_keys):
            if "目的" in key:
                target_col = idx
                break
        if target_col is None:
            target_col = len(header_keys) - 1
        current = cells_by_header[header_keys[target_col]]
        for t in tags:
            if t not in current:
                current = (current + " " + t).strip()
        cells_by_header[header_keys[target_col]] = current

        fixed_row = [cells_by_header[k] for k in header_keys]
        out_lines.append(build_row(fixed_row))

    DST.write_text("".join(out_lines), encoding="utf-8")
    print(f"Wrote {DST}")


if __name__ == "__main__":
    main()
