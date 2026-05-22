from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.conversation import Conversation
from app.domain.eval_spec import EvalSpec
from app.pipeline.evaluation_runner import EvaluationRunner
from app.storage.repo_eval import EvaluationRepository


class EvaluationRequest(BaseModel):
    spec: EvalSpec
    conversation: Conversation


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/run")
def run_evaluation(payload: EvaluationRequest, request: Request) -> dict:
    result = EvaluationRunner().run(payload.spec, payload.conversation)
    repo = EvaluationRepository(request.app.state.db)
    repo.save_json(result.run_id, result.model_dump())
    return result.model_dump()


@router.get("/{run_id}")
def get_evaluation(run_id: str, request: Request) -> dict:
    repo = EvaluationRepository(request.app.state.db)
    payload = repo.get_json(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return payload
