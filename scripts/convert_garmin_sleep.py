#!/usr/bin/env python3
import argparse
import csv
import json
import os
from datetime import datetime
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional


BASE_FIELDS = [
    "sleepStartTimestampGMT",
    "sleepEndTimestampGMT",
    "calendarDate",
    "sleepWindowConfirmationType",
    "deepSleepSeconds",
    "lightSleepSeconds",
    "remSleepSeconds",
    "awakeSleepSeconds",
    "unmeasurableSeconds",
    "averageRespiration",
    "lowestRespiration",
    "highestRespiration",
    "retro",
    "awakeCount",
    "avgSleepStress",
    "restlessMomentCount",
]

DERIVED_FIELDS = [
    "sleepSeconds",
    "timeInBedSeconds",
    "sleepHours",
    "timeInBedHours",
    "sleepEfficiency",
    "deepPercent",
    "lightPercent",
    "remPercent",
]


def _safe_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def flatten_record(record: Dict[str, Any], score_keys: List[str]) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for key in BASE_FIELDS:
        row[key] = record.get(key)

    deep = _safe_number(record.get("deepSleepSeconds")) or 0.0
    light = _safe_number(record.get("lightSleepSeconds")) or 0.0
    rem = _safe_number(record.get("remSleepSeconds")) or 0.0
    awake = _safe_number(record.get("awakeSleepSeconds")) or 0.0
    unmeasurable = _safe_number(record.get("unmeasurableSeconds")) or 0.0

    sleep_seconds = deep + light + rem
    time_in_bed = sleep_seconds + awake + unmeasurable

    row["sleepSeconds"] = int(sleep_seconds)
    row["timeInBedSeconds"] = int(time_in_bed)
    row["sleepHours"] = round(sleep_seconds / 3600.0, 3) if sleep_seconds else 0.0
    row["timeInBedHours"] = (
        round(time_in_bed / 3600.0, 3) if time_in_bed else 0.0
    )
    row["sleepEfficiency"] = (
        round(sleep_seconds / time_in_bed, 4) if time_in_bed else None
    )
    row["deepPercent"] = round(deep / sleep_seconds, 4) if sleep_seconds else None
    row["lightPercent"] = round(light / sleep_seconds, 4) if sleep_seconds else None
    row["remPercent"] = round(rem / sleep_seconds, 4) if sleep_seconds else None

    scores = record.get("sleepScores") or {}
    for key in score_keys:
        row[f"score_{key}"] = scores.get(key)

    return row


def build_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    dates = [row.get("calendarDate") for row in rows if row.get("calendarDate")]

    summary["recordCount"] = len(rows)
    summary["dateStart"] = min(dates) if dates else None
    summary["dateEnd"] = max(dates) if dates else None

    summary["avgSleepHours"] = _mean(row.get("sleepHours") for row in rows)
    summary["avgTimeInBedHours"] = _mean(row.get("timeInBedHours") for row in rows)
    summary["avgSleepEfficiency"] = _mean(row.get("sleepEfficiency") for row in rows)
    summary["avgDeepPercent"] = _mean(row.get("deepPercent") for row in rows)
    summary["avgLightPercent"] = _mean(row.get("lightPercent") for row in rows)
    summary["avgRemPercent"] = _mean(row.get("remPercent") for row in rows)

    summary["avgOverallScore"] = _mean(
        row.get("score_overallScore") for row in rows
    )
    summary["avgQualityScore"] = _mean(
        row.get("score_qualityScore") for row in rows
    )
    summary["avgDurationScore"] = _mean(
        row.get("score_durationScore") for row in rows
    )
    summary["avgRecoveryScore"] = _mean(
        row.get("score_recoveryScore") for row in rows
    )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Garmin sleep JSON to analysis-ready CSV."
    )
    parser.add_argument(
        "input",
        help="Path to Garmin sleepData JSON file",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to write CSV and summary JSON (default: outputs)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = os.path.expanduser(args.input)
    output_dir = os.path.expanduser(args.output_dir)

    with open(input_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Expected a JSON array of sleep records.")

    score_keys = sorted(
        {key for record in payload for key in (record.get("sleepScores") or {})}
    )

    rows = [flatten_record(record, score_keys) for record in payload]

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    csv_path = os.path.join(output_dir, f"{base_name}_sleep.csv")
    summary_path = os.path.join(output_dir, f"{base_name}_summary.json")

    fieldnames = BASE_FIELDS + DERIVED_FIELDS + [f"score_{k}" for k in score_keys]
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = build_summary(rows)
    summary["generatedAt"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    summary["sourceFile"] = os.path.abspath(input_path)
    summary["outputCsv"] = os.path.abspath(csv_path)

    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print(f"Wrote CSV: {csv_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
