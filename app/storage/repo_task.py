from app.domain.eval_spec import EvalSpec
from app.storage.db import Database


class SpecRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, spec: EvalSpec) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO eval_spec(spec_id, instruction_id, version, payload)
                VALUES (?, ?, ?, ?)
                """,
                (spec.spec_id, spec.instruction_id, spec.version, spec.model_dump_json()),
            )

    def get(self, spec_id: str) -> EvalSpec | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM eval_spec WHERE spec_id = ?",
                (spec_id,),
            ).fetchone()
        return EvalSpec.model_validate_json(row["payload"]) if row else None
