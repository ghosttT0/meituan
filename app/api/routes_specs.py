from fastapi import APIRouter, HTTPException, Request

from app.domain.eval_spec import EvalSpec
from app.domain.task_instruction import TaskInstruction
from app.spec.compiler import SpecCompiler
from app.storage.repo_task import SpecRepository

router = APIRouter(prefix="/specs", tags=["specs"])
compiler = SpecCompiler()


@router.post("/compile", response_model=EvalSpec)
def compile_spec(payload: TaskInstruction) -> EvalSpec:
    return compiler.compile(payload)


@router.post("", response_model=EvalSpec)
def save_spec(payload: EvalSpec, request: Request) -> EvalSpec:
    repo = SpecRepository(request.app.state.db)
    repo.save(payload)
    return payload


@router.get("/{spec_id}", response_model=EvalSpec)
def get_spec(spec_id: str, request: Request) -> EvalSpec:
    repo = SpecRepository(request.app.state.db)
    spec = repo.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="spec not found")
    return spec
