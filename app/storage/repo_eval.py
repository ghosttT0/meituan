import json

from app.storage.db import Database


class EvaluationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_json(self, run_id: str, payload: dict) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_run(run_id, payload)
                VALUES (?, ?)
                """,
                (run_id, json.dumps(payload, ensure_ascii=False)),
            )

    def get_json(self, run_id: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM evaluation_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None
