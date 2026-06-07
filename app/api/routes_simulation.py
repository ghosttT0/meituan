from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.domain.eval_spec import EvalSpec
from app.simulators.conversation_runner import ConversationRunner
from app.simulators.model_probe import ModelProbeService


class AdapterConfig(BaseModel):
    type: str = "mock"
    endpoint: str | None = None
    api_key: str = ""
    model: str = ""
    auth_type: str = "bearer"
    protocol_mode: str = "auto"


class SimulationConfig(BaseModel):
    profile_id: str = "cooperative"
    primary_branch: str = "cooperative"
    scenario_key: str | None = None
    batch_runs: int = 1
    random_seed: int | None = None
    max_turns: int = 8


class SimulationRequest(BaseModel):
    evaluation_mode: str = "dual_arbitration"
    spec: EvalSpec
    task_instruction_text: str = ""
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    model_config = ConfigDict(populate_by_name=True)


class ModelConfigRequest(BaseModel):
    name: str = ""
    api_url: str
    api_key: str
    model: str = ""
    protocol_mode: str = "auto"
    auth_type: str = "bearer"


router = APIRouter(prefix="/simulations", tags=["simulations"])
probe_service = ModelProbeService()


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
            scenario_key=payload.simulation.scenario_key,
            batch_runs=payload.simulation.batch_runs,
            random_seed=payload.simulation.random_seed,
            evaluation_mode=payload.evaluation_mode,
        )
        return result.model_dump()

    if payload.adapter.type == "http" and payload.adapter.endpoint:
        result = await runner.run_http(
            spec=payload.spec,
            profile_id=payload.simulation.profile_id,
            primary_branch=payload.simulation.primary_branch,
            endpoint=payload.adapter.endpoint,
            api_key=payload.adapter.api_key,
            model=payload.adapter.model,
            auth_type=payload.adapter.auth_type,
            protocol_mode=payload.adapter.protocol_mode,
            max_turns=payload.simulation.max_turns,
            task_instruction_text=payload.task_instruction_text,
            scenario_key=payload.simulation.scenario_key,
            batch_runs=payload.simulation.batch_runs,
            random_seed=payload.simulation.random_seed,
            evaluation_mode=payload.evaluation_mode,
        )
        return result.model_dump()

    raise HTTPException(status_code=400, detail="unsupported simulation adapter")


@router.post("/check-model")
async def check_model(payload: ModelConfigRequest) -> dict:
    return await probe_service.check_model(
        api_url=payload.api_url,
        api_key=payload.api_key,
        model=payload.model,
        protocol_mode=payload.protocol_mode,
        auth_type=payload.auth_type,
    )


@router.post("/list-models")
async def list_models(payload: ModelConfigRequest) -> dict:
    return await probe_service.list_models(
        api_url=payload.api_url,
        api_key=payload.api_key,
        auth_type=payload.auth_type,
    )
