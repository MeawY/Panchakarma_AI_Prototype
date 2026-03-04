import argparse
import re
from pathlib import Path
from typing import List, Tuple

HEADER = "| no | question | answer | source |\n|---:|---|---|---|\n"


def split_entries(text: str) -> List[Tuple[int, str]]:
    """Split big one-line text into [(no, chunk_text)].
    Accepts cases like "-Q10" and ensures Q numbering is detected.
    """
    # Normalize hyphen-prefixed Q labels and collapse whitespace
    norm = text.replace("-Q", " Q").replace("\n", " ")
    # Find the first Q-number start; drop preface like "No." header
    m_first = re.search(r"Q(\d+)", norm)
    if not m_first:
        return []
    norm = norm[m_first.start():]

    entries: List[Tuple[int, str]] = []
    for m in re.finditer(r"Q(\d+)", norm):
        entries.append((int(m.group(1)), m.start()))
    # Append sentinel end index
    indices = [idx for _, idx in entries] + [len(norm)]
    nos = [no for no, _ in entries]

    out: List[Tuple[int, str]] = []
    for i, no in enumerate(nos):
        start = indices[i]
        end = indices[i + 1]
        chunk = norm[start:end].strip()
        # remove leading Qn label
        chunk = re.sub(r"^Q\d+", "", chunk).strip()
        out.append((no, chunk))
    return out


def split_qa(chunk: str) -> Tuple[str, str, str]:
    """Split a chunk into question, answer, source.
    - Question ends at first Japanese '？' or ASCII '?'.
    - Source tokens are like $$CH$$ or $$CH, 84$$ → collect, then remove from answer.
    """
    # Question/Answer split
    qm = re.search(r"[？?]", chunk)
    if qm:
        q = chunk[: qm.end()].strip()
        a = chunk[qm.end():].strip()
    else:
        q = chunk.strip()
        a = ""

    # Extract sources like $$CH$$ or $$CH, 84$$
    sources = re.findall(r"\$\$([^$]+)\$\$", a)
    # Remove the $$...$$ markers from answer
    a = re.sub(r"\$\$[^$]+\$\$", "", a)

    # Tidy spaces (compress)
    def tidy(s: str) -> str:
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    q = tidy(q)
    a = tidy(a)
    src = ", ".join(dict.fromkeys([tidy(s) for s in sources])) if sources else ""
    return q, a, src


def normalize_file(input_path: Path, output_path: Path) -> int:
    text = input_path.read_text(encoding="utf-8")
    entries = split_entries(text)
    rows: List[str] = [HEADER]
    for no, chunk in entries:
        q, a, src = split_qa(chunk)
        # Escape vertical bars inside cells
        q = q.replace("|", "\\|")
        a = a.replace("|", "\\|")
        src = src.replace("|", "\\|")
        rows.append(f"| {no} | {q} | {a} | {src} |\n")

    output_path.write_text("".join(rows), encoding="utf-8")
    return len(entries)


def main():
    p = argparse.ArgumentParser(description="Normalize concatenated QA text into a Markdown table")
    p.add_argument("input", help="input text file (concatenated Qn...) ")
    p.add_argument("output", help="output markdown path")
    args = p.parse_args()

    inp = Path(args.input)
    outp = Path(args.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    n = normalize_file(inp, outp)
    print(f"Wrote {outp} with {n} rows")


if __name__ == "__main__":
    main()
