from fastapi import FastAPI

from app.api.routes_demo import demo_static, router as demo_router
from app.api.routes_eval import router as eval_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_specs import router as specs_router
from app.api.routes_system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.storage.db import Database

setup_logging()

app = FastAPI(title="Instruction Following Evaluator")
app.mount("/demo/assets", demo_static, name="demo-assets")
app.include_router(system_router)
app.include_router(specs_router)
app.include_router(eval_router)
app.include_router(simulation_router)
app.include_router(demo_router)

settings = get_settings()
db = Database(settings.database_path)
db.init()
app.state.db = db
