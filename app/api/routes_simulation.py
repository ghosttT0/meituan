from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.domain.eval_spec import EvalSpec
from app.simulators.conversation_runner import ConversationRunner


class AdapterConfig(BaseModel):
    type: str = "mock"
    endpoint: str | None = None


class SimulationConfig(BaseModel):
    profile_id: str = "cooperative"
    primary_branch: str = "cooperative"
    max_turns: int = 8


class SimulationRequest(BaseModel):
    spec: EvalSpec
    task_instruction_text: str = ""
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    model_config = ConfigDict(populate_by_name=True)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run")
async def run_simulation(payload: SimulationRequest) -> dict:
    runner = ConversationRunner()

    if payload.adapter.type == "mock":
        result = await runner.run_mock(
            spec=payload.spec,
            profile_id=payload.simulation.profile_id,
            primary_branch=payload.simulation.primary_branch,
            max_turns=payload.simulation.max_turns,
            task_instruction_text=payload.task_instruction_text,
        )
        return result.model_dump()

    if payload.adapter.type == "http" and payload.adapter.endpoint:
        result = await runner.run_http(
            spec=payload.spec,
            profile_id=payload.simulation.profile_id,
            primary_branch=payload.simulation.primary_branch,
            endpoint=payload.adapter.endpoint,
            max_turns=payload.simulation.max_turns,
            task_instruction_text=payload.task_instruction_text,
        )
        return result.model_dump()

    raise HTTPException(status_code=400, detail="unsupported simulation adapter")
