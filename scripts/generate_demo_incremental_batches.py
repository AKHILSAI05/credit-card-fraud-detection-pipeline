"""Create balanced synthetic credit-card transaction batches for pipeline demos.

The output matches the Kaggle CSV schema used by the project:
Time, V1-V28, Amount, Class.
Class is included only as a historical validation label; it is not used by the
pipeline to decide review priority.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


ROWS_PER_FILE = 100_000
BATCH_COUNT = 5
LARGE_BATCH_ROWS = 200_000
LARGE_BATCH_NUMBERS = (9, 10, 11)
BASE_TIMESTAMP = datetime(2026, 8, 19)
BASE_TIME_SECONDS = 18 * 86_400  # 2026-08-19 when Silver starts at 2026-08-01.
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "test-data" / "demo_incremental_batches"

COLUMNS = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class"]


def amount_for_row(index: int, rng: random.Random) -> float:
    """Use the same controlled range mix in every batch for readable analytics."""
    segment = index % 100
    if segment < 10:
        return rng.uniform(0.50, 10.00)
    if segment < 45:
        return rng.uniform(10.00, 100.00)
    if segment < 80:
        return rng.uniform(100.00, 500.00)
    if segment < 95:
        return rng.uniform(500.00, 2_000.00)
    return rng.uniform(2_000.00, 8_000.00)


def transaction_time(batch_index: int, row_index: int) -> float:
    """Spread each batch across one day with controlled short bursts."""
    day_start = BASE_TIME_SECONDS + batch_index * 86_400
    # Twenty percent of rows are in intentional short bursts for rapid-repeat
    # behaviour; all remaining rows cover the full day.
    if row_index % 5 == 0:
        burst_number = row_index // 5
        return day_start + (burst_number % 3_600) * 20 + (row_index % 3)
    return day_start + ((row_index * 37) % 86_400)


def historical_label(index: int, amount: float, rng: random.Random) -> int:
    """Create a small, mixed historical fraud sample across amount ranges."""
    # Roughly 2.5%, deliberately not based only on high amount.
    base = index % 40 == 0
    low_amount_case = amount < 20 and index % 67 == 0
    high_amount_case = amount > 2_000 and index % 31 == 0
    return int(base or low_amount_case or high_amount_case or rng.random() < 0.001)


def write_batch(batch_number: int, row_count: int = ROWS_PER_FILE) -> dict[str, object]:
    rng = random.Random(20_260_800 + batch_number)
    name = f"creditcard_batch_{batch_number:03d}_demo.csv"
    target = OUTPUT_DIR / name
    fraud_count = 0
    amount_total = 0.0

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row_index in range(row_count):
            amount = round(amount_for_row(row_index, rng), 2)
            label = historical_label(row_index, amount, rng)
            fraud_count += label
            amount_total += amount

            row = {
                "Time": f"{transaction_time(batch_number - 1, row_index):.3f}",
                "Amount": f"{amount:.2f}",
                "Class": label,
            }
            for feature_number in range(1, 29):
                # Deterministic, non-identifying values compatible with the
                # anonymized V1-V28 columns in the source dataset.
                value = rng.gauss(0, 1)
                if label and feature_number in (4, 10, 12, 14, 17):
                    value += rng.choice((-2.5, 2.5))
                row[f"V{feature_number}"] = f"{value:.6f}"
            writer.writerow(row)

    return {
        "file": name,
        "rows": row_count,
        "date_window": f"{(BASE_TIMESTAMP + timedelta(days=batch_number - 1)).date()} (synthetic)",
        "historical_fraud_rows": fraud_count,
        "total_amount": round(amount_total, 2),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = [write_batch(number) for number in range(4, 4 + BATCH_COUNT)]
    manifest.extend(
        write_batch(number, LARGE_BATCH_ROWS) for number in LARGE_BATCH_NUMBERS
    )

    # This file is deliberately byte-identical to batch 009. It belongs in a
    # separate folder so it cannot be accidentally loaded during normal demos.
    # Upload it only AFTER batch 009 has succeeded to demonstrate the pipeline's
    # content-SHA256 duplicate check and reject routing.
    duplicate_dir = OUTPUT_DIR / "duplicate_test_only"
    duplicate_dir.mkdir(exist_ok=True)
    source = OUTPUT_DIR / "creditcard_batch_009_demo.csv"
    duplicate = duplicate_dir / "creditcard_batch_009_same_content_different_name.csv"
    duplicate.write_bytes(source.read_bytes())

    manifest.append(
        {
            "file": str(duplicate.relative_to(OUTPUT_DIR)),
            "rows": LARGE_BATCH_ROWS,
            "purpose": "duplicate-content rejection test; upload only after batch 009 succeeds",
        }
    )
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created {len(manifest)} CSV files in: {OUTPUT_DIR}")
    for item in manifest:
        if "historical_fraud_rows" in item:
            print(
                f"{item['file']}: {item['rows']:,} rows; "
                f"historical fraud labels={item['historical_fraud_rows']:,}"
            )
        else:
            print(f"{item['file']}: duplicate-content test file; {item['purpose']}")


if __name__ == "__main__":
    main()
