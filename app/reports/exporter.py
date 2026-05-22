import csv
from pathlib import Path


def export_batch_summary(rows: list[dict], destination: str) -> str:
    path = Path(destination)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["run_id", "conversation_id", "overall_score", "hard_fail", "confidence"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return str(path)
