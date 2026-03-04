import argparse
import os
import re
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import MetaData, Table, Column, Text, insert
from sqlalchemy.engine import Engine

from app.db import engine


def to_snake_case(name: str) -> str:
    name = name.strip().strip("`\"'")
    name = re.sub(r"[^0-9A-Za-z]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_").lower()
    if not name:
        name = "col"
    if name[0].isdigit():
        name = f"c_{name}"
    return name


def parse_markdown_table(md_path: Path) -> Tuple[List[str], List[List[str]]]:
    """Parse the first GitHub-flavored Markdown table found in the file.

    Returns (headers, rows). Raises ValueError if no table is found.
    """
    lines = md_path.read_text(encoding="utf-8").splitlines()

    # Normalize: keep only lines that look like table rows
    table_lines = [ln for ln in lines if ln.strip().startswith("|") and ln.strip().endswith("|")]
    if len(table_lines) < 2:
        raise ValueError("No markdown table found (need header and separator lines)")

    # Find header + separator (---) pair
    header_idx = None
    for i in range(len(table_lines) - 1):
        sep = table_lines[i + 1].strip()
        if set(sep.replace("|", "").replace(":", "").replace(" ", "")) <= {"-"} and "-" in sep:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find header separator line (---) in markdown table")

    def split_row(ln: str) -> List[str]:
        # Remove leading/trailing pipe and split; keep empty cells
        raw = ln.strip().strip("|")
        parts = [cell.strip() for cell in raw.split("|")]
        return parts

    # Build unique, valid headers
    raw_headers = split_row(table_lines[header_idx])
    # Map to snake_case with fallbacks and ensure uniqueness
    seen_counts = {}
    headers: List[str] = []
    for i, h in enumerate(raw_headers):
        base = h or f"col_{i}"
        name = to_snake_case(base)
        count = seen_counts.get(name, 0)
        unique = f"{name}_{count}" if count else name
        seen_counts[name] = count + 1
        headers.append(unique)

    data_lines = table_lines[header_idx + 2 :]
    rows: List[List[str]] = []
    for ln in data_lines:
        parts = split_row(ln)
        # pad/truncate to header length
        if len(parts) < len(headers):
            parts += [""] * (len(headers) - len(parts))
        elif len(parts) > len(headers):
            parts = parts[: len(headers)]
        rows.append(parts)

    return headers, rows


def validate_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    issues: List[str] = []
    # Empty/auto headers
    auto_headers = [h for h in headers if re.match(r"^col(\_\d+)?$", h)]
    if auto_headers:
        issues.append(f"empty header names normalized → {', '.join(auto_headers)}")
    # Duplicate-like headers (after normalization they are numbered)
    dup_like = [h for h in headers if re.match(r"^.+_\d+$", h)]
    if dup_like:
        issues.append(f"duplicate headers normalized → {', '.join(dup_like)}")
    # Missing cells per row
    for i, r in enumerate(rows, start=1):
        missing = [headers[j] for j, cell in enumerate(r) if cell == ""]
        if missing:
            issues.append(f"row {i}: missing cells → {', '.join(missing)}")
            if len(issues) > 50:  # cap output
                issues.append("... more issues truncated ...")
                break
    if not rows:
        issues.append("no data rows found")
    return issues


def ensure_table(engine: Engine, schema: str, table_name: str, headers: List[str]) -> Table:
    metadata = MetaData(schema=schema)
    columns = [Column(h, Text, nullable=True) for h in headers]
    tbl = Table(table_name, metadata, *columns)
    metadata.create_all(engine, checkfirst=True)
    return tbl


def import_markdown(md_file: Path, schema: str, table_name: str, strict: bool = False, validate_only: bool = False) -> int:
    headers, rows = parse_markdown_table(md_file)
    issues = validate_table(headers, rows)
    if issues:
        print("Validation issues:")
        for msg in issues:
            print(" -", msg)
        if strict:
            raise SystemExit(1)
    if validate_only:
        return 0

    tbl = ensure_table(engine, schema=schema, table_name=table_name, headers=headers)

    dict_rows = [dict(zip(headers, r)) for r in rows]
    if not dict_rows:
        return 0

    with engine.begin() as conn:
        conn.execute(insert(tbl), dict_rows)
    return len(dict_rows)


def main():
    parser = argparse.ArgumentParser(description="Import a Markdown table into Postgres (TEXT columns)")
    parser.add_argument("file", help="Path to markdown (.md)")
    parser.add_argument("--table", "-t", help="Destination table name. Default: file name")
    parser.add_argument("--schema", "-s", default="public", help="Target schema (default: public)")
    parser.add_argument("--validate", action="store_true", help="Validate only (no writes)")
    parser.add_argument("--strict", action="store_true", help="Fail (exit 1) if validation issues exist")
    args = parser.parse_args()

    md_path = Path(args.file).expanduser().resolve()
    if not md_path.exists():
        raise SystemExit(f"File not found: {md_path}")

    table_name = args.table or to_snake_case(md_path.stem)

    count = import_markdown(md_path, schema=args.schema, table_name=table_name, strict=args.strict, validate_only=args.validate)
    if args.validate:
        print("Validation finished")
    else:
        print(f"Imported {count} rows into {args.schema}.{table_name}")


if __name__ == "__main__":
    main()
