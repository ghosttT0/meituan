from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.pipeline.evaluation_runner import EvaluationRunner
from app.reports.exporter import export_batch_summary
from app.storage.repo_eval import EvaluationRepository


class EvaluationRequest(BaseModel):
    spec: EvalSpec
    conversation: Conversation


class BatchEvaluationRequest(BaseModel):
    items: list[EvaluationRequest] = Field(default_factory=list)


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run")
def run_evaluation(payload: EvaluationRequest, request: Request) -> dict:
    result = EvaluationRunner().run(payload.spec, payload.conversation)
    repo = EvaluationRepository(request.app.state.db)
    repo.save_json(result.run_id, result.model_dump())
    return result.model_dump()


@router.post("/batch")
def run_batch(payload: BatchEvaluationRequest, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    results = []
    for item in payload.items:
        result = EvaluationRunner().run(item.spec, item.conversation)
        repo.save_json(result.run_id, result.model_dump())
        results.append(result.model_dump())
    export_path = export_batch_summary(
        [
            {
                "run_id": item["run_id"],
                "conversation_id": item["conversation_id"],
                "overall_score": item["overall_score"],
                "hard_fail": item["hard_fail"],
                "confidence": item["confidence"],
            }
            for item in results
        ],
        "batch_summary.csv",
    )
    return {"results": results, "export_path": export_path}


@router.get("/{run_id}")
def get_evaluation(run_id: str, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    payload = repo.get_json(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return payload
