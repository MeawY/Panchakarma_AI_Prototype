import re

def fix_markdown_table(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_lines = []
    for line in lines:
        # 空行や見出し行以外の行にパイプを補う
        if re.match(r'^\s*\|', line):
            fixed_lines.append(line.strip())
        elif re.match(r'^\s*No\.', line):
            # ヘッダー行にパイプ追加
            header = '| ' + line.strip().replace('\t', ' | ').replace('  ', ' ') + ' |'
            fixed_lines.append(header)
            fixed_lines.append('|-----|-----|-----|-----|')  # 区切り行を追加
        else:
            # 通常データ行
            row = '| ' + line.strip().replace('\t', ' | ').replace('  ', ' ') + ' |'
            fixed_lines.append(row)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(fixed_lines))

if __name__ == "__main__":
    fix_markdown_table("data/panchakarma_qa_pairs", "data/panchakarma_qa_pairs_fixed.md")
    print("✅ 修正版を書き出しました → data/panchakarma_qa_pairs_fixed.md")
