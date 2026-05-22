from pathlib import Path

from app.domain.eval_spec import EvalSpec
from app.storage.db import Database
from app.storage.repo_eval import EvaluationRepository
from app.storage.repo_task import SpecRepository


def test_spec_repository_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init()
    repo = SpecRepository(db)

    spec = EvalSpec(
        spec_id="spec_roundtrip",
        instruction_id="instr_1",
        version="v1",
        task_goal="确认地址",
    )
    repo.save(spec)

    loaded = repo.get("spec_roundtrip")

    assert loaded is not None
    assert loaded.spec_id == "spec_roundtrip"


def test_evaluation_repository_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init()
    repo = EvaluationRepository(db)

    payload = {
        "run_id": "run_1",
        "conversation_id": "conv_1",
        "spec_id": "spec_1",
        "overall_score": 88.0,
    }
    repo.save_json("run_1", payload)

    assert repo.get_json("run_1")["overall_score"] == 88.0
