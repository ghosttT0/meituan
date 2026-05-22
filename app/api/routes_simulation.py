from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class SimulationRequest(BaseModel):
    spec_id: str
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    model_config = ConfigDict(populate_by_name=True)


router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/run")
def run_simulation(_: SimulationRequest) -> None:
    raise HTTPException(status_code=501, detail="simulation runner not implemented in prototype")
