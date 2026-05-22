from fastapi import FastAPI

from app.api.routes_system import router as system_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.include_router(system_router)
